import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Callable, Iterable

from .models import ImageMetadata, ScanSummary


Parser = Callable[[Path], ImageMetadata]
ResultCallback = Callable[[ImageMetadata, int, int], None]
StateCallback = Callable[[str, int], None]


class ScanEngine:
    def __init__(self, parser: Parser, max_files: int = 100000):
        self.parser = parser
        self.max_files = max_files

    def collect_files(self, folder: Path, recursive: bool, stop: threading.Event) -> list[Path]:
        result: list[Path] = []
        pending = [folder]
        while pending and not stop.is_set() and len(result) < self.max_files:
            current = pending.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        if stop.is_set() or len(result) >= self.max_files:
                            break
                        try:
                            if entry.is_file(follow_symlinks=False):
                                result.append(Path(entry.path))
                            elif recursive and entry.is_dir(follow_symlinks=False):
                                pending.append(Path(entry.path))
                        except OSError:
                            continue
            except OSError:
                continue
        return result

    def scan(
        self,
        folder: Path,
        recursive: bool,
        stop: threading.Event,
        on_result: ResultCallback,
        on_state: StateCallback,
        workers: int | None = None,
    ) -> ScanSummary:
        started = time.perf_counter()
        on_state("Подготовка списка файлов", 0)
        paths = self.collect_files(folder, recursive, stop)
        total = len(paths)
        on_state("Чтение заголовков", total)
        if not total or stop.is_set():
            return ScanSummary(total, 0, 0, 0, 0, time.perf_counter() - started, 0, 0, stop.is_set())
        workers = workers or min(32, max(4, (os.cpu_count() or 4) * 4))
        completed = valid = damaged = unsupported = total_size = bytes_read = 0
        iterator = iter(paths)
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="image-header") as pool:
            pending = set()
            for _ in range(min(total, workers * 4)):
                try:
                    pending.add(pool.submit(self.parser, next(iterator)))
                except StopIteration:
                    break
            while pending:
                if stop.is_set():
                    for future in pending:
                        future.cancel()
                    break
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    if future.cancelled():
                        continue
                    item = future.result()
                    completed += 1
                    total_size += item.file_size
                    bytes_read += item.bytes_read
                    if item.status == "Готово" or item.status.startswith("Предупреждение"):
                        valid += 1
                    elif item.status == "Файл повреждён":
                        damaged += 1
                    else:
                        unsupported += 1
                    on_result(item, completed, total)
                    try:
                        pending.add(pool.submit(self.parser, next(iterator)))
                    except StopIteration:
                        pass
        return ScanSummary(
            total,
            completed,
            valid,
            damaged,
            unsupported,
            time.perf_counter() - started,
            total_size,
            bytes_read,
            stop.is_set(),
        )

