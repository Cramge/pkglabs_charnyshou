import binascii
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from infrastructure.parsers import parse_image


def png_chunk(name, data):
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", binascii.crc32(name + data) & 0xFFFFFFFF)


def make_png():
    ihdr = struct.pack(">IIBBBBB", 3, 2, 8, 6, 0, 0, 0)
    pixels = b"\x00" + b"\xff\x00\x00\xff" * 3
    pixels += b"\x00" + b"\x00\xff\x00\xff" * 3
    phys = struct.pack(">IIB", 3780, 3780, 1)
    return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) + png_chunk(b"pHYs", phys) + png_chunk(b"IDAT", zlib.compress(pixels)) + png_chunk(b"IEND", b"")


def make_gif():
    return bytes.fromhex("47494638396101000100800000000000ffffff2c00000000010001000002024401003b")


def make_bmp():
    width, height, bits = 2, 2, 24
    stride = ((width * bits + 31) // 32) * 4
    pixels = b"\x00" * (stride * height)
    size = 54 + len(pixels)
    file_header = b"BM" + struct.pack("<IHHI", size, 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, width, height, 1, bits, 0, len(pixels), 3780, 3780, 0, 0)
    return file_header + dib + pixels


def make_jpeg():
    app0 = b"JFIF\x00\x01\x02\x01" + struct.pack(">HH", 96, 96) + b"\x00\x00"
    sof = b"\x08" + struct.pack(">HHB", 2, 3, 3) + b"\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    sos = b"\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00"
    return b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", len(app0) + 2) + app0 + b"\xff\xc0" + struct.pack(">H", len(sof) + 2) + sof + b"\xff\xda" + struct.pack(">H", len(sos) + 2) + sos + b"\x00\xff\xd9"


def make_exif_jpeg():
    count = 3
    xres_offset = 8 + 2 + count * 12 + 4
    yres_offset = xres_offset + 8
    entries = [
        tiff_entry(282, 5, 1, xres_offset),
        tiff_entry(283, 5, 1, yres_offset),
        tiff_entry(296, 3, 1, 2),
    ]
    tiff = b"II*\x00\x08\x00\x00\x00" + struct.pack("<H", count) + b"".join(entries) + b"\x00\x00\x00\x00"
    tiff += struct.pack("<II", 300, 1) + struct.pack("<II", 300, 1)
    app1 = b"Exif\x00\x00" + tiff
    sof = b"\x08" + struct.pack(">HHB", 2, 3, 3) + b"\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    sos = b"\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00"
    return b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xc0" + struct.pack(">H", len(sof) + 2) + sof + b"\xff\xda" + struct.pack(">H", len(sos) + 2) + sos + b"\x00\xff\xd9"


def tiff_entry(tag, type_code, count, value):
    if type_code == 3 and count == 1:
        field = struct.pack("<H", value) + b"\x00\x00"
    else:
        field = struct.pack("<I", value)
    return struct.pack("<HHI", tag, type_code, count) + field


def make_tiff():
    count = 12
    data_offset = 8 + 2 + count * 12 + 4
    xres_offset = data_offset
    yres_offset = xres_offset + 8
    pixel_offset = yres_offset + 8
    entries = [
        tiff_entry(256, 4, 1, 3),
        tiff_entry(257, 4, 1, 2),
        tiff_entry(258, 3, 1, 8),
        tiff_entry(259, 3, 1, 1),
        tiff_entry(262, 3, 1, 1),
        tiff_entry(273, 4, 1, pixel_offset),
        tiff_entry(277, 3, 1, 1),
        tiff_entry(278, 4, 1, 2),
        tiff_entry(279, 4, 1, 1),
        tiff_entry(282, 5, 1, xres_offset),
        tiff_entry(283, 5, 1, yres_offset),
        tiff_entry(296, 3, 1, 2),
    ]
    return b"II*\x00\x08\x00\x00\x00" + struct.pack("<H", count) + b"".join(entries) + b"\x00\x00\x00\x00" + struct.pack("<II", 300, 1) + struct.pack("<II", 300, 1) + b"\x7f"


def big_tiff_entry(tag, type_code, count, value):
    if type_code == 3 and count == 1:
        field = struct.pack("<H", value) + b"\x00" * 6
    elif type_code == 4 and count == 1:
        field = struct.pack("<I", value) + b"\x00" * 4
    else:
        field = struct.pack("<Q", value)
    return struct.pack("<HHQ", tag, type_code, count) + field


def make_big_tiff():
    count = 8
    pixel_offset = 16 + 8 + count * 20 + 8
    entries = [
        big_tiff_entry(256, 16, 1, 4),
        big_tiff_entry(257, 16, 1, 3),
        big_tiff_entry(258, 3, 1, 8),
        big_tiff_entry(259, 3, 1, 1),
        big_tiff_entry(262, 3, 1, 1),
        big_tiff_entry(273, 16, 1, pixel_offset),
        big_tiff_entry(277, 3, 1, 1),
        big_tiff_entry(279, 16, 1, 12),
    ]
    header = b"II+\x00\x08\x00\x00\x00" + struct.pack("<Q", 16)
    return header + struct.pack("<Q", count) + b"".join(entries) + b"\x00" * 8 + b"\x7f" * 12


def make_pcx():
    header = bytearray(128)
    header[0:4] = bytes((0x0A, 5, 0, 8))
    struct.pack_into("<HHHHHH", header, 4, 0, 0, 0, 0, 96, 96)
    header[65] = 1
    struct.pack_into("<H", header, 66, 2)
    struct.pack_into("<H", header, 68, 1)
    return bytes(header) + b"\x01\x00" + b"\x0c" + bytes(768)


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_all_formats(self):
        cases = [
            ("sample.png", make_png(), "PNG", (3, 2), "32 бит", "Deflate"),
            ("sample.gif", make_gif(), "GIF", (1, 1), "1 бит", "LZW"),
            ("sample.bmp", make_bmp(), "BMP", (2, 2), "24 бит", "BI_RGB"),
            ("sample.jpg", make_jpeg(), "JPEG", (3, 2), "24 бит", "Baseline"),
            ("sample.tif", make_tiff(), "TIFF", (3, 2), "8 бит", "без сжатия"),
            ("sample.pcx", make_pcx(), "PCX", (1, 1), "8 бит", "без сжатия"),
        ]
        for name, data, format_name, dimensions, depth, compression in cases:
            with self.subTest(name=name):
                item = parse_image(self.write(name, data))
                self.assertEqual("Готово", item.status)
                self.assertEqual(format_name, item.format_name)
                self.assertEqual(dimensions, (item.width, item.height))
                self.assertIn(depth, item.color_depth)
                self.assertIn(compression, item.compression)
                self.assertLessEqual(item.bytes_read, item.file_size)

    def test_resolution(self):
        png = parse_image(self.write("resolution.png", make_png()))
        jpeg = parse_image(self.write("resolution.jpg", make_jpeg()))
        tiff = parse_image(self.write("resolution.tif", make_tiff()))
        bmp = parse_image(self.write("resolution.bmp", make_bmp()))
        self.assertAlmostEqual(96.012, png.dpi_x, places=2)
        self.assertEqual(96.0, jpeg.dpi_x)
        self.assertEqual(300.0, tiff.dpi_x)
        self.assertAlmostEqual(96.012, bmp.dpi_x, places=2)

    def test_jpeg_exif_resolution(self):
        jpeg = parse_image(self.write("exif-resolution.jpg", make_exif_jpeg()))
        self.assertEqual("Готово", jpeg.status)
        self.assertEqual(300.0, jpeg.dpi_x)
        self.assertEqual(300.0, jpeg.dpi_y)

    def test_big_tiff_ifd(self):
        item = parse_image(self.write("sample.tif", make_big_tiff()))
        self.assertEqual("Готово", item.status)
        self.assertEqual("TIFF", item.format_name)
        self.assertEqual((4, 3), (item.width, item.height))
        self.assertEqual("8 бит (8)", item.color_depth)

    def test_signature_has_priority_over_extension(self):
        item = parse_image(self.write("renamed.jpg", make_png()))
        self.assertEqual("PNG", item.format_name)
        self.assertTrue(item.status.startswith("Предупреждение"))

    def test_fake_image_extension(self):
        item = parse_image(self.write("text.jpg", b"this is not an image"))
        self.assertEqual("Подменённое расширение или неизвестный формат", item.status)

    def test_missing_png_iend(self):
        item = parse_image(self.write("broken.png", make_png()[:-12]))
        self.assertEqual("Файл повреждён", item.status)

    def test_missing_jpeg_eoi(self):
        item = parse_image(self.write("broken.jpg", make_jpeg()[:-2]))
        self.assertEqual("Файл повреждён", item.status)

    def test_declared_bmp_size(self):
        data = bytearray(make_bmp())
        struct.pack_into("<I", data, 2, len(data) + 100)
        item = parse_image(self.write("broken.bmp", data))
        self.assertEqual("Файл повреждён", item.status)

    def test_truncated_tiff_strip(self):
        item = parse_image(self.write("broken.tif", make_tiff()[:-1]))
        self.assertEqual("Файл повреждён", item.status)

    def test_truncated_pcx_data(self):
        data = make_pcx()[:128]
        item = parse_image(self.write("broken.pcx", data))
        self.assertEqual("Файл повреждён", item.status)


class VerificationArchiveTests(unittest.TestCase):
    def test_external_bmp_set(self):
        location = os.environ.get("LAB2_CHECK_DIR")
        if not location:
            self.skipTest("LAB2_CHECK_DIR is not set")
        files = sorted(Path(location).glob("*"))
        self.assertGreaterEqual(len(files), 20)
        for path in files:
            with self.subTest(path=path.name):
                item = parse_image(path)
                self.assertEqual("Готово", item.status, item.details)
                self.assertEqual("BMP", item.format_name)
                self.assertGreater(item.width, 0)
                self.assertGreater(item.height, 0)


if __name__ == "__main__":
    unittest.main()

