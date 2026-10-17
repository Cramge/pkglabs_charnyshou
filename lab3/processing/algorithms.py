import math
from array import array
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from memory.pixel_buffer import PixelBuffer


def _worker_count(height: int):
    return max(1, min(os.cpu_count() or 1, height, 8))


def _ranges(height: int, workers: int):
    step = (height + workers - 1) // workers
    return [(start, min(height, start + step)) for start in range(0, height, step)]


def _run_rows(height, operation, progress=None, cancelled=None):
    workers = _worker_count(height)
    ranges = _ranges(height, workers)
    completed = 0
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(operation, start, end): (start, end) for start, end in ranges}
        for future in as_completed(futures):
            if cancelled and cancelled():
                for pending in futures:
                    pending.cancel()
                raise InterruptedError("Обработка отменена")
            results.append(future.result())
            start, end = futures[future]
            completed += end - start
            if progress:
                progress(completed, height)
    return sorted(results, key=lambda item: item[0])


def rank_filter(buffer: PixelBuffer, radius=1, mode="median", edge="Reflect", progress=None, cancelled=None):
    if radius < 1 or radius > 5:
        raise ValueError("Радиус должен быть от 1 до 5")
    if mode not in {"median", "maximum"}:
        raise ValueError("Неизвестный порядковый фильтр")
    width, height, channels = buffer.width, buffer.height, buffer.channels
    source = buffer.data
    size = (radius * 2 + 1) ** 2

    def process_rows(start, end):
        block = bytearray((end - start) * width * channels)
        target_index = 0
        for y in range(start, end):
            if cancelled and cancelled():
                raise InterruptedError("Обработка отменена")
            for x in range(width):
                for channel in range(channels):
                    values = []
                    for dy in range(-radius, radius + 1):
                        yy = buffer._coordinate(y + dy, height, edge)
                        row = yy * width * channels
                        for dx in range(-radius, radius + 1):
                            xx = buffer._coordinate(x + dx, width, edge)
                            values.append(source[row + xx * channels + channel])
                    values.sort()
                    if mode == "maximum":
                        value = values[-1]
                    else:
                        value = values[size // 2]
                    block[target_index] = value
                    target_index += 1
        return start, block

    result = bytearray(width * height * channels)
    for start, block in _run_rows(height, process_rows, progress, cancelled):
        offset = start * width * channels
        result[offset:offset + len(block)] = block
    return PixelBuffer(width, height, channels, result)




def apply_threshold(gray: PixelBuffer, threshold: float):
    source = gray.grayscale()
    return PixelBuffer(source.width, source.height, 1, bytearray(255 if value > threshold else 0 for value in source.data))


def otsu_threshold(buffer: PixelBuffer):
    gray = buffer.grayscale()
    histogram = gray.histogram()
    count = gray.width * gray.height
    total = sum(level * amount for level, amount in enumerate(histogram))
    background_weight = 0
    background_sum = 0
    best_variance = -1.0
    best_threshold = 0
    for threshold, amount in enumerate(histogram):
        background_weight += amount
        if background_weight == 0:
            continue
        foreground_weight = count - background_weight
        if foreground_weight == 0:
            break
        background_sum += threshold * amount
        background_mean = background_sum / background_weight
        foreground_mean = (total - background_sum) / foreground_weight
        variance = background_weight * foreground_weight * (background_mean - foreground_mean) ** 2
        if variance > best_variance:
            best_variance = variance
            best_threshold = threshold
    return apply_threshold(gray, best_threshold), best_threshold


def iterative_threshold(buffer: PixelBuffer, tolerance=0.5, max_iterations=100):
    gray = buffer.grayscale()
    histogram = gray.histogram()
    threshold = sum(level * amount for level, amount in enumerate(histogram)) / (gray.width * gray.height)
    for _ in range(max_iterations):
        border = max(0, min(255, int(round(threshold))))
        low_count = sum(histogram[:border + 1])
        high_count = sum(histogram[border + 1:])
        if low_count == 0 or high_count == 0:
            break
        low_mean = sum(level * histogram[level] for level in range(border + 1)) / low_count
        high_mean = sum(level * histogram[level] for level in range(border + 1, 256)) / high_count
        updated = (low_mean + high_mean) / 2
        if abs(updated - threshold) <= tolerance:
            threshold = updated
            break
        threshold = updated
    return apply_threshold(gray, threshold), threshold



def _integral_images(gray: PixelBuffer, progress=None, cancelled=None):
    width, height = gray.width, gray.height
    stride = width + 1
    size = stride * (height + 1)
    integral = array("Q", [0]) * size
    squared = array("Q", [0]) * size
    for y in range(1, height + 1):
        if cancelled and cancelled():
            raise InterruptedError("Обработка отменена")
        row_sum = 0
        row_squared = 0
        source_row = (y - 1) * width
        current = y * stride
        previous = (y - 1) * stride
        for x in range(1, width + 1):
            value = gray.data[source_row + x - 1]
            row_sum += value
            row_squared += value * value
            integral[current + x] = integral[previous + x] + row_sum
            squared[current + x] = squared[previous + x] + row_squared
        if progress and (y % 16 == 0 or y == height):
            progress(y, height * 2)
    return integral, squared



def sauvola_threshold(buffer: PixelBuffer, window=25, k=0.2, dynamic_range=128.0, progress=None, cancelled=None):
    if window < 3 or window > 151 or window % 2 == 0:
        raise ValueError("Размер окна должен быть нечетным числом от 3 до 151")
    if not -1.0 <= k <= 1.0 or dynamic_range <= 0:
        raise ValueError("Некорректные параметры Сауволы")
    gray = buffer.grayscale()
    width, height = gray.width, gray.height
    integral, squared = _integral_images(gray, progress, cancelled)
    stride = width + 1
    radius = window // 2

    def process_rows(start, end):
        block = bytearray((end - start) * width)
        target = 0
        for y in range(start, end):
            if cancelled and cancelled():
                raise InterruptedError("Обработка отменена")
            top = max(0, y - radius)
            bottom = min(height - 1, y + radius)
            y1, y2 = top, bottom + 1
            for x in range(width):
                left = max(0, x - radius)
                right = min(width - 1, x + radius)
                x1, x2 = left, right + 1
                area = (x2 - x1) * (y2 - y1)
                total = integral[y2 * stride + x2] - integral[y1 * stride + x2] - integral[y2 * stride + x1] + integral[y1 * stride + x1]
                total_squared = squared[y2 * stride + x2] - squared[y1 * stride + x2] - squared[y2 * stride + x1] + squared[y1 * stride + x1]
                mean = total / area
                variance = max(0.0, total_squared / area - mean * mean)
                deviation = math.sqrt(variance)
                threshold = mean * (1.0 + k * (deviation / dynamic_range - 1.0))
                block[target] = 255 if gray.data[y * width + x] > threshold else 0
                target += 1
        return start, block

    output = bytearray(width * height)
    completed = height

    def report(done, total):
        if progress:
            progress(completed + done, height * 2)

    for start, block in _run_rows(height, process_rows, report, cancelled):
        offset = start * width
        output[offset:offset + len(block)] = block
    return PixelBuffer(width, height, 1, output)

