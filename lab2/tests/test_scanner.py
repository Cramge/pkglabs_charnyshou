import tempfile
import threading
import unittest
from pathlib import Path

from core.scanner import ScanEngine
from infrastructure.parsers import parse_image
from tests.test_parsers import make_bmp, make_png


class ScannerTests(unittest.TestCase):
    def test_parallel_scan_reports_all_files(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            nested = root / "nested"
            nested.mkdir()
            for index in range(30):
                target = root if index % 2 else nested
                (target / f"image_{index}.png").write_bytes(make_png())
            (root / "fake.jpg").write_text("not an image", encoding="utf-8")
            rows = []
            states = []
            summary = ScanEngine(parse_image).scan(
                root,
                True,
                threading.Event(),
                lambda item, done, total: rows.append((item, done, total)),
                lambda text, total: states.append((text, total)),
                workers=8,
            )
            self.assertEqual(31, summary.total)
            self.assertEqual(31, summary.completed)
            self.assertEqual(30, summary.valid)
            self.assertEqual(1, summary.unsupported)
            self.assertEqual(31, len(rows))
            self.assertGreater(summary.total_size, summary.bytes_read)

    def test_limit_is_enforced(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            for index in range(12):
                (root / f"image_{index}.bmp").write_bytes(make_bmp())
            summary = ScanEngine(parse_image, max_files=5).scan(
                root,
                False,
                threading.Event(),
                lambda item, done, total: None,
                lambda text, total: None,
                workers=2,
            )
            self.assertEqual(5, summary.total)
            self.assertEqual(5, summary.completed)


if __name__ == "__main__":
    unittest.main()

