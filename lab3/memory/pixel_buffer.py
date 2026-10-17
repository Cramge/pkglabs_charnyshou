from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(slots=True)
class PixelBuffer:
    width: int
    height: int
    channels: int
    data: bytearray

    def __post_init__(self):
        expected = self.width * self.height * self.channels
        if self.width <= 0 or self.height <= 0 or self.channels not in {1, 3}:
            raise ValueError("Некорректные параметры пиксельного буфера")
        if len(self.data) != expected:
            raise ValueError("Размер буфера не соответствует изображению")

    @classmethod
    def from_file(cls, path: str | Path):
        with Image.open(path) as source:
            image = source.convert("RGB")
            return cls(image.width, image.height, 3, bytearray(image.tobytes()))

    @classmethod
    def from_image(cls, image: Image.Image):
        converted = image.convert("RGB")
        return cls(converted.width, converted.height, 3, bytearray(converted.tobytes()))

    def copy(self):
        return PixelBuffer(self.width, self.height, self.channels, bytearray(self.data))

    def to_image(self):
        mode = "L" if self.channels == 1 else "RGB"
        return Image.frombytes(mode, (self.width, self.height), bytes(self.data))

    def save(self, path: str | Path):
        self.to_image().save(path)

    def _coordinate(self, value: int, limit: int, edge: str):
        if edge == "Clamp":
            return min(limit - 1, max(0, value))
        if edge != "Reflect":
            raise ValueError("Неизвестная стратегия обработки краев")
        if limit == 1:
            return 0
        while value < 0 or value >= limit:
            if value < 0:
                value = -value - 1
            else:
                value = 2 * limit - value - 1
        return value

    def get(self, x: int, y: int, channel: int = 0, edge: str = "Clamp"):
        x = self._coordinate(x, self.width, edge)
        y = self._coordinate(y, self.height, edge)
        return self.data[(y * self.width + x) * self.channels + channel]

    def grayscale(self):
        if self.channels == 1:
            return self.copy()
        result = bytearray(self.width * self.height)
        source = self.data
        for index in range(self.width * self.height):
            offset = index * 3
            result[index] = (77 * source[offset] + 150 * source[offset + 1] + 29 * source[offset + 2] + 128) >> 8
        return PixelBuffer(self.width, self.height, 1, result)

    def histogram(self):
        gray = self.grayscale()
        result = [0] * 256
        for value in gray.data:
            result[value] += 1
        return result
