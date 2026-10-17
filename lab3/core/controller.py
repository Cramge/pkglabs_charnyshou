import threading
import time
from pathlib import Path

from memory.pixel_buffer import PixelBuffer
from processing.algorithms import iterative_threshold, otsu_threshold, rank_filter, sauvola_threshold


class ProcessingController:
    def __init__(self):
        self.original = None
        self.result = None
        self.path = None
        self.cancel_event = threading.Event()

    def load(self, path):
        self.path = Path(path)
        self.original = PixelBuffer.from_file(path)
        self.result = self.original.copy()
        return self.original

    def reset(self):
        if self.original is None:
            return None
        self.result = self.original.copy()
        return self.result

    def cancel(self):
        self.cancel_event.set()

    def process(self, method, parameters, progress=None):
        if self.original is None:
            raise ValueError("Сначала откройте изображение")
        self.cancel_event.clear()
        started = time.perf_counter()
        source = self.original
        threshold = None
        cancelled = self.cancel_event.is_set
        if method == "Медианный фильтр":
            result = rank_filter(source, parameters["radius"], "median", parameters["edge"], progress=progress, cancelled=cancelled)
        elif method == "Максимальный фильтр":
            result = rank_filter(source, parameters["radius"], "maximum", parameters["edge"], progress=progress, cancelled=cancelled)
        elif method == "Глобальный порог Оцу":
            result, threshold = otsu_threshold(source)
            if progress:
                progress(1, 1)
        elif method == "Итеративный глобальный порог":
            result, threshold = iterative_threshold(source, parameters["tolerance"])
            if progress:
                progress(1, 1)
        elif method == "Адаптивный порог Сауволы":
            result = sauvola_threshold(source, parameters["window"], parameters["k"], 128.0, progress, cancelled)
        else:
            raise ValueError("Неизвестный метод обработки")
        self.result = result
        return result, time.perf_counter() - started, threshold

    def save(self, path):
        if self.result is None:
            raise ValueError("Нет результата для сохранения")
        self.result.save(path)
