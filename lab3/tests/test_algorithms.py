import unittest

from memory.pixel_buffer import PixelBuffer
from processing.algorithms import iterative_threshold, otsu_threshold, rank_filter, sauvola_threshold


class PixelBufferTests(unittest.TestCase):
    def test_edge_modes(self):
        buffer = PixelBuffer(3, 1, 1, bytearray((10, 20, 30)))
        self.assertEqual(10, buffer.get(-1, 0, edge="Clamp"))
        self.assertEqual(10, buffer.get(-1, 0, edge="Reflect"))
        self.assertEqual(20, buffer.get(-2, 0, edge="Reflect"))
        self.assertEqual(20, buffer.get(4, 0, edge="Reflect"))

    def test_grayscale_and_histogram(self):
        buffer = PixelBuffer(2, 1, 3, bytearray((255, 0, 0, 255, 255, 255)))
        gray = buffer.grayscale()
        self.assertEqual(bytearray((77, 255)), gray.data)
        histogram = gray.histogram()
        self.assertEqual(2, sum(histogram))
        self.assertEqual(1, histogram[77])


class RankFilterTests(unittest.TestCase):
    def test_median_removes_impulse(self):
        data = bytearray([100] * 9)
        data[4] = 255
        result = rank_filter(PixelBuffer(3, 3, 1, data), radius=1, mode="median", edge="Clamp")
        self.assertEqual(100, result.data[4])

    def test_maximum(self):
        data = bytearray((10, 20, 30, 40, 50, 60, 70, 80, 90))
        source = PixelBuffer(3, 3, 1, data)
        maximum = rank_filter(source, 1, "maximum", "Clamp")
        self.assertEqual(90, maximum.data[4])



class ThresholdTests(unittest.TestCase):
    def test_otsu_separates_two_classes(self):
        source = PixelBuffer(20, 1, 1, bytearray([20] * 10 + [220] * 10))
        result, threshold = otsu_threshold(source)
        self.assertGreaterEqual(threshold, 20)
        self.assertEqual(bytearray([0] * 10 + [255] * 10), result.data)




    def test_iterative_threshold(self):
        source = PixelBuffer(20, 1, 1, bytearray([30] * 10 + [210] * 10))
        result, threshold = iterative_threshold(source)
        self.assertAlmostEqual(120, threshold)
        self.assertEqual(bytearray([0] * 10 + [255] * 10), result.data)


    def test_sauvola_uses_local_brightness(self):
        width, height = 21, 9
        data = bytearray()
        for y in range(height):
            for x in range(width):
                background = 70 + x * 7
                value = max(0, background - 45) if 3 <= y <= 5 else background
                data.append(value)
        source = PixelBuffer(width, height, 1, data)
        result = sauvola_threshold(source, window=7, k=0.15)
        foreground = sum(result.data[y * width + x] == 0 for y in range(3, 6) for x in range(width))
        self.assertGreater(foreground, width * 2)


if __name__ == "__main__":
    unittest.main()
