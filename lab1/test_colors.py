import random
import unittest
from color_models import *

class ConversionTests(unittest.TestCase):
    def close(self, actual, expected, delta=0.001):
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, delta=delta)

    def test_reference_lab(self):
        cases = [((0,0,0), (0,0,0)), ((1,1,1), (100,0,0)),

                 ((1,0,0), (53.2371,80.0901,67.2033)),
                 ((0,1,0), (87.7355,-86.1816,83.1866)),
                 ((0,0,1), (32.3009,79.1953,-107.8555))]
        for rgb, lab in cases:
            with self.subTest(rgb=rgb):
                self.close(rgb_to_lab(rgb), lab)

    def test_random_roundtrips(self):
        rng = random.Random(10)
        for _ in range(2000):
            rgb = tuple(rng.random() for _ in range(3))
            self.close(lab_to_rgb(rgb_to_lab(rgb)), rgb, 2e-6)
            self.close(to_rgb('CMYK', from_rgb('CMYK', rgb)), rgb, 1e-12)

    def test_black_and_cmyk(self):
        self.close(from_rgb('CMYK', (0,0,0)), (0,0,0,100))
        self.close(to_rgb('CMYK', (0,100,100,0)), (1,0,0))
        self.close(to_rgb('CMYK', (20,40,60,50)), (.4,.3,.2))

    def test_gamut(self):
        rgb, clipped = display_rgb(lab_to_rgb((60,120,120)))
        self.assertTrue(clipped)
        self.assertTrue(all(0 <= v <= 1 for v in rgb))
        for rgb in ((1,1,1), (1,0,0), (0,1,0), (0,0,1), (0,0,0)):
            self.assertFalse(display_rgb(lab_to_rgb(rgb_to_lab(rgb)))[1])

    def test_transfer_boundaries(self):
        for v in (0, .003, .04045, .5, 1):
            self.assertAlmostEqual(encode(linearize(v)), v, delta=3e-8)

    def test_invalid_numbers(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.assertRaises(ValueError):
                to_rgb('RGB', (value,0,0))

    def test_hex(self):
        self.assertEqual(hex_color((1,0,.5)), '#FF0080')

if __name__ == '__main__':
    unittest.main(verbosity=2)
