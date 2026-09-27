from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ImageMetadata:
    path: Path
    format_name: str = "—"
    width: int | None = None
    height: int | None = None
    dpi_x: float | None = None
    dpi_y: float | None = None
    color_depth: str = "—"
    compression: str = "—"
    status: str = "Готово"
    details: dict[str, str] = field(default_factory=dict)
    file_size: int = 0
    bytes_read: int = 0

    @property
    def file_name(self) -> str:
        return self.path.name

    @property
    def dimensions(self) -> str:
        if self.width is None or self.height is None:
            return "—"
        return f"{self.width} × {self.height}"

    @property
    def resolution(self) -> str:
        if self.dpi_x is None or self.dpi_y is None:
            return "не задано"
        if abs(self.dpi_x - self.dpi_y) < 0.01:
            return f"{self.dpi_x:.2f} dpi"
        return f"{self.dpi_x:.2f} × {self.dpi_y:.2f} dpi"

    @property
    def read_ratio(self) -> str:
        if not self.file_size:
            return "0 Б"
        percent = min(100.0, self.bytes_read * 100.0 / self.file_size)
        return f"{self.bytes_read} Б ({percent:.2f} %)"


@dataclass(slots=True)
class ScanSummary:
    total: int
    completed: int
    valid: int
    damaged: int
    unsupported: int
    elapsed: float
    total_size: int
    bytes_read: int
    cancelled: bool

