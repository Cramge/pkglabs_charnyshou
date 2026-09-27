import os
import struct
from pathlib import Path


class ParseError(Exception):
    pass


class DamagedFile(ParseError):
    pass


class UnsupportedFile(ParseError):
    pass


class BinaryReader:
    def __init__(self, path: Path):
        self.path = path
        self.size = os.path.getsize(path)
        self.bytes_read = 0
        self.ranges = []
        self.stream = None

    def __enter__(self):
        self.stream = open(self.path, "rb", buffering=64 * 1024)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.stream is not None:
            self.stream.close()

    def tell(self) -> int:
        return self.stream.tell()

    def seek(self, offset: int, whence: int = 0) -> int:
        return self.stream.seek(offset, whence)

    def read(self, count: int) -> bytes:
        start = self.stream.tell()
        data = self.stream.read(count)
        self._record(start, start + len(data))
        return data

    def _record(self, start: int, end: int) -> None:
        if end <= start:
            return
        merged = []
        for left, right in sorted(self.ranges + [(start, end)]):
            if merged and left <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], right))
            else:
                merged.append((left, right))
        self.ranges = merged
        self.bytes_read = sum(right - left for left, right in merged)

    def exact(self, count: int, label: str = "данные") -> bytes:
        data = self.read(count)
        if len(data) != count:
            raise DamagedFile(f"Недостаточно байтов: {label}")
        return data

    def at(self, offset: int, count: int, label: str = "данные") -> bytes:
        self.ensure(offset, count, label)
        self.seek(offset)
        return self.exact(count, label)

    def ensure(self, offset: int, count: int, label: str = "данные") -> None:
        if offset < 0 or count < 0 or offset + count > self.size:
            raise DamagedFile(f"Смещение выходит за размер файла: {label}")

    def unpack_at(self, fmt: str, offset: int, label: str = "структура"):
        size = struct.calcsize(fmt)
        return struct.unpack(fmt, self.at(offset, size, label))

