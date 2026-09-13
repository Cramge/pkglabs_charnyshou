"""GUI integration checks. Run explicitly: python -m unittest -v test_ui.

Needs Windows/Tk display; no OS input injection or screenshot dependencies.
"""
import unittest
from types import SimpleNamespace
from main import ColorLab

class ViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ColorLab()
        cls.app.withdraw()
        cls.errors = []
        cls.app.report_callback_exception = lambda *e: cls.errors.append(e)

    @classmethod
    def tearDownClass(cls): cls.app.destroy()

    def setUp(self):
        self.app.controller.settings('D65','GCR','Clipping')
        self.app.illuminant.set('D65')
        self.app.separation.set('GCR')
        self.app.gamut.set('Clipping')
        self.app.update_color('RGB',(79,69,230))

    def test_field_slider_palette_handlers(self):
        a = self.app
        for e,text in zip(a.entries['RGB'],('255','0','0')):
            e.delete(0,'end'); e.insert(0,text)
        a.read_fields('RGB')
        self.assertEqual(a.hex_label.cget('text'),'#FF0000')
        self.assertEqual(a.entries['CMYK'][1].get(),'100.000')
        a.change_component('RGB',1,128)
        self.assertEqual(a.entries['RGB'][1].get(),'128.000')
        for model,canvas in a.palettes.items():
            a.pick(model,SimpleNamespace(x=0,y=0,widget=canvas))
            self.assertEqual(a.controller.source,model)

    def test_options_and_live_matrices(self):
        a = self.app
        a.show_matrices()
        a.illuminant.set('D50'); a.separation.set('UCR'); a.gamut.set('Scaling')
        a.change_settings()
        self.assertEqual(a.controller.engine.illuminant,'D50')
        self.assertIn('D50',a.matrix_box.get('1.0','end'))
        self.assertEqual(a.controller.engine.separation,'UCR')
        self.assertEqual(a.controller.engine.gamut,'Scaling')
        a.matrix_window.destroy()

    def test_gradients_render_and_change(self):
        a = self.app
        a.draw_colors()
        old = a.sliders['RGB'][1].samples
        a.change_component('RGB',0,255)
        a.draw_colors()
        self.assertNotEqual(old,a.sliders['RGB'][1].samples)
        for model,sliders in a.sliders.items():
            for slider in sliders:
                self.assertIsNotNone(slider.photo)
                self.assertTrue(slider.find_withtag('marker'))
            self.assertIsNotNone(a.palettes[model].photo)
        a.update()
        self.assertFalse(self.errors)

    def test_keyboard_slider(self):
        slider = self.app.sliders['RGB'][0]
        before = slider.value
        slider.step(1)
        self.assertGreater(slider.value,before)
        self.assertEqual(slider.value,self.app.controller.values['RGB'][0])

    def test_invalid_text_stays_visible(self):
        a = self.app
        entry = a.entries['RGB'][0]
        entry.delete(0,'end'); entry.insert(0,'abc')
        before = a.controller.rgb
        a.read_fields('RGB')
        self.assertEqual(entry.get(),'abc')
        self.assertEqual(a.controller.rgb,before)
        self.assertIn('конечные',a.status.cget('text'))

if __name__ == '__main__': unittest.main(verbosity=2)
