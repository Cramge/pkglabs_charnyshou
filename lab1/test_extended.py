"""Independent references and invariants for all assignment modes."""
import random
import unittest
from color_models import ColorEngine, SPECS, ILLUMINANTS, matvec, matmul, inverse, linearize
from controller import ColorController

class MathTests(unittest.TestCase):
    def close(self, a, b, tolerance=1e-8):
        self.assertEqual(len(a), len(b))
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, delta=tolerance)

    def test_published_srgb_matrix(self):
        # W3C CSS Color 4 lin_sRGB_to_XYZ rational reference, test data only.
        reference = ((506752/1228815,87881/245763,12673/70218),
                     (87098/409605,175762/245763,12673/175545),
                     (7918/409605,87881/737289,1001167/1053270))
        for actual, expected in zip(ColorEngine().rgb_xyz, reference):
            self.close(actual, expected, 1e-12)

    def test_d50_red_reference(self):
        self.close(ColorEngine('D50').rgb_to_lab((1,0,0)), (54.2905,80.8049,69.8910), .002)

    def test_illuminant_white_and_black(self):
        for name in ILLUMINANTS:
            e = ColorEngine(name)
            self.close(e.rgb_to_xyz((1,1,1)), e.white)
            self.close(e.rgb_to_lab((1,1,1)), (100,0,0))
            self.close(e.rgb_to_lab((0,0,0)), (0,0,0))
            self.close(e.lab_to_rgb((100,0,0)), (1,1,1))

    def test_matrix_inverse_all_whites(self):
        matrices = []
        for name in ILLUMINANTS:
            e = ColorEngine(name)
            matrices.append(e.rgb_xyz)
            product = matmul(e.rgb_xyz, e.xyz_rgb)
            for i, row in enumerate(product):
                self.close(row, tuple(float(i==j) for j in range(3)))
        self.assertEqual(len(set(matrices)), 3)

    def test_matrix_rebuilt_on_switch(self):
        e = ColorEngine()
        before = e.rgb_xyz
        e.set_illuminant('E')
        self.assertNotEqual(before, e.rgb_xyz)
        e.set_illuminant('D65')
        self.assertEqual(before, e.rgb_xyz)

    def test_inverse_pivot_and_singular(self):
        a = ((0,1,0),(1,0,0),(0,0,2))
        self.close(matvec(inverse(a),(2,3,8)),(3,2,4))
        with self.assertRaises(ValueError):
            inverse(((0,0,0),)*3)

    def test_roundtrips_all_modes(self):
        rng = random.Random(2026)
        for name in ILLUMINANTS:
            for separation in ('UCR','GCR'):
                e = ColorEngine(name,separation)
                for _ in range(1000):
                    rgb = tuple(rng.random() for _ in range(3))
                    self.close(e.lab_to_rgb(e.rgb_to_lab(rgb)),rgb)
                    cmyk = e.from_rgb('CMYK',rgb)
                    self.assertTrue(all(0<=v<=100 for v in cmyk))
                    self.close(e.to_rgb('CMYK',cmyk),rgb)

    def test_cmyk_primary_references_both_modes(self):
        cases = [((1,0,0),(0,100,100,0)),((0,1,0),(100,0,100,0)),
                 ((0,0,1),(100,100,0,0)),((0,0,0),(0,0,0,100)),((1,1,1),(0,0,0,0))]
        for mode in ('UCR','GCR'):
            for rgb, expected in cases:
                self.close(ColorEngine(separation=mode).from_rgb('CMYK',rgb),expected)

    def test_ucr_gcr_midgray_and_shadow(self):
        gcr, ucr = ColorEngine(separation='GCR'), ColorEngine(separation='UCR')
        self.close(gcr.from_rgb('CMYK',(.5,.5,.5)), (0,0,0,50))
        self.close(ucr.from_rgb('CMYK',(.5,.5,.5)), (50,50,50,0))
        self.close(ucr.from_rgb('CMYK',(.25,.25,.25)), (60,60,60,37.5))
        self.assertLess(ucr.from_rgb('CMYK',(.25,.1,.1))[3],37.5)

    def test_ucr_continuous_black_generation(self):
        e = ColorEngine(separation='UCR')
        values = [e.from_rgb('CMYK',(v,v,v))[3] for v in (1,.8,.5,.499,.25,.01,0)]
        self.assertEqual(values[:3],[0,0,0])
        self.assertEqual(values, sorted(values))
        self.assertLess(values[3],.001)

    def test_gamut_strategies(self):
        raw = (-.2,.4,1.4)
        self.close(ColorEngine().display_rgb(raw)[0],(0,.4,1))
        scaling = ColorEngine(gamut='Scaling')
        self.close(scaling.display_rgb(raw)[0],(0,.375,1))
        self.close(scaling.display_rgb((.4,.8,1.6))[0],(.25,.5,1))
        for strategy in ('Clipping','Scaling'):
            e = ColorEngine(gamut=strategy)
            self.assertTrue(e.display_rgb(raw)[1])
            self.close(e.display_rgb((.2,.4,.6))[0],(.2,.4,.6))
            self.assertFalse(e.display_rgb((.2,.4,.6))[1])

    def test_invalid_configuration_and_numbers(self):
        for kwargs in ({'illuminant':'X'},{'separation':'X'},{'gamut':'X'}):
            with self.assertRaises(ValueError): ColorEngine(**kwargs)
        e = ColorEngine()
        for values in ((1,2),(1,2,3,4),(float('nan'),0,0),(float('inf'),0,0)):
            for fn in (e.rgb_to_lab,e.lab_to_rgb,e.display_rgb):
                with self.assertRaises(ValueError): fn(values)

class ControllerTests(unittest.TestCase):
    def setUp(self): self.c = ColorController()

    def test_rgb_255_red_contract(self):
        self.c.update('RGB',(255,0,0))
        self.assertEqual(self.c.values['CMYK'],(0,100,100,0))
        for actual, expected in zip(self.c.values['LAB'],(53.2371,80.0901,67.2033)):
            self.assertAlmostEqual(actual,expected,delta=.001)

    def test_all_components_synchronize(self):
        for model, specs in SPECS.items():
            for i,(_,lo,hi) in enumerate(specs):
                self.c.change_component(model,i,(lo+hi)/2)
                self.assertEqual(self.c.values[model][i],(lo+hi)/2)
                self.assertTrue(all(0<=v<=1 for v in self.c.rgb))

    def test_invalid_fields_preserve_state(self):
        original = self.c.values.copy()
        for text in ('','abc','nan','inf','1e999'):
            self.assertFalse(self.c.read_fields('RGB',[text,'0','0']))
            self.assertEqual(self.c.values,original)
            self.assertTrue(self.c.warning)

    def test_comma_and_bounds(self):
        self.assertTrue(self.c.read_fields('RGB',['999','12,5','-2']))
        self.assertEqual(self.c.values['RGB'],(255,12.5,0))
        self.assertTrue(self.c.warning)

    def test_no_rounding_on_focus(self):
        self.c.update('RGB',(10.1234567,20.7654321,30.1234567))
        original = self.c.values.copy()
        self.c.read_fields('RGB',[f'{v:.3f}' for v in self.c.values['RGB']])
        self.assertEqual(self.c.values,original)

    def test_palette_all_models(self):
        for model in SPECS:
            self.c.pick(model,1,0)
            for i in self.c.axes(model):
                self.assertEqual(self.c.values[model][i],SPECS[model][i][2])

    def test_untouched_fields_keep_precision(self):
        self.c.update('RGB',(10.1234567,20.7654321,30.1234567))
        self.c.read_fields('RGB',['11.500','20.765','30.123'])
        self.assertEqual(self.c.values['RGB'],(11.5,20.7654321,30.1234567))

    def test_dynamic_gradients(self):
        before = self.c.gradient('RGB',1)
        self.c.change_component('RGB',0,255)
        after = self.c.gradient('RGB',1)
        self.assertNotEqual(before,after)
        self.assertEqual(after[0][0][0],1)
        self.assertEqual(after[-1][0][1],1)
        for model, specs in SPECS.items():
            for i in range(len(specs)):
                self.assertEqual(len(self.c.gradient(model,i)),96)

    def test_illuminant_preserves_rgb(self):
        for source,values in (('RGB',(170,80,30)),('LAB',(50,20,30)),('CMYK',(20,30,40,50))):
            self.c.update(source,values)
            before = self.c.rgb
            lab = self.c.values['LAB']
            self.c.settings('D50','GCR','Clipping')
            for a,b in zip(before,self.c.rgb): self.assertAlmostEqual(a,b,places=10)
            self.assertNotEqual(lab,self.c.values['LAB'])
            self.c.settings('D65','GCR','Clipping')

    def test_algorithm_switch_changes_recipe_not_color(self):
        self.c.update('CMYK',(0,0,0,50))
        self.c.settings('D65','UCR','Clipping')
        self.assertEqual(self.c.values['CMYK'],(50,50,50,0))
        self.assertEqual(self.c.rgb,(.5,.5,.5))

    def test_outside_lab_preserved_when_switching_gamut(self):
        self.c.update('LAB',(60,120,120))
        before = self.c.rgb
        self.c.settings('D65','GCR','Scaling')
        self.assertEqual(self.c.values['LAB'],(60,120,120))
        self.assertNotEqual(before,self.c.rgb)
        self.assertTrue(self.c.warning)

    def test_matrix_inspection(self):
        self.assertIn('D65',self.c.matrix_text())
        self.c.settings('E','GCR','Clipping')
        self.assertIn('XYZ (E)',self.c.matrix_text())

if __name__ == '__main__': unittest.main(verbosity=2)
