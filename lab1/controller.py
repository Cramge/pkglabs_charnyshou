"""Application state and interaction logic, independent of GUI toolkits."""
from color_models import ColorEngine, SPECS, clamp, validate, hex_color

class ColorController:
    def __init__(self):
        self.engine = ColorEngine()
        self.values = {}
        self.update('RGB', (79, 69, 230))

    def update(self, model, values):
        validate(values, len(SPECS[model]))
        bounded = tuple(clamp(v, lo, hi) for v, (_, lo, hi) in zip(values, SPECS[model]))
        self.raw_rgb = self.engine.to_rgb(model, bounded)
        self.rgb, self.outside = self.engine.display_rgb(self.raw_rgb)
        self.source = model
        self.values = {m: bounded if m == model else self.engine.from_rgb(m, self.rgb) for m in SPECS}
        self.warning = self.outside or bounded != tuple(values)
        self.message = 'Модели синхронизированы. Штриховка отмечает цвета вне охвата sRGB.'
        if self.outside:
            self.message = f'LAB вне охвата sRGB: исходные координаты сохранены; RGB, CMYK и образец показаны с {self.engine.gamut}.'
        if bounded != tuple(values):
            self.message += ' Ввод ограничен диапазонами компонент.'

    def read_fields(self, model, texts):
        if texts == [f'{v:.3f}' for v in self.values[model]]:
            return True
        try:
            # Editing one field must not round the untouched coordinates.
            values = tuple(old if t == f'{old:.3f}' else float(t.replace(',', '.'))
                           for t,old in zip(texts,self.values[model]))
            if len(texts) != len(self.values[model]):
                raise ValueError('Неверное число компонент.')
            self.update(model,values)
            return True
        except (ValueError, OverflowError):
            self.warning = True
            self.message = 'Введите конечные числа. Предыдущий цвет сохранён.'
            return False

    def change_component(self, model, index, value):
        values = list(self.values[model])
        values[index] = value
        self.update(model, values)

    def pick(self, model, x, y):
        values = list(self.values[model])
        for index, fraction in zip(self.axes(model), (x, 1-y)):
            _, lo, hi = SPECS[model][index]
            values[index] = lo+clamp(fraction)*(hi-lo)
        self.update(model, values)

    def settings(self, illuminant, separation, gamut):
        source, values = self.source, self.values[self.source]
        old_illuminant, old_separation = self.engine.illuminant, self.engine.separation
        self.engine = ColorEngine(illuminant, separation, gamut)
        if illuminant != old_illuminant and source == 'LAB':
            values = self.engine.from_rgb('LAB', self.raw_rgb)
        if separation != old_separation and source == 'CMYK':
            source, values = 'RGB', tuple(v*255 for v in self.rgb)
        self.update(source, values)

    @staticmethod
    def axes(model):
        return (1, 2) if model == 'LAB' else (0, 1)

    def sample(self, model, replacements):
        values = list(self.values[model])
        for index, fraction in replacements:
            _, lo, hi = SPECS[model][index]
            values[index] = lo+fraction*(hi-lo)
        return self.engine.display_rgb(self.engine.to_rgb(model, values))

    def gradient(self, model, index, count=96):
        return [self.sample(model, [(index, x/(count-1))]) for x in range(count)]

    def palette(self, model, width=64, height=28):
        ix, iy = self.axes(model)
        return [self.sample(model, [(ix, x/(width-1)), (iy, 1-y/(height-1))]) for y in range(height) for x in range(width)]

    @property
    def hex(self):
        return hex_color(self.rgb)

    def matrix_text(self):
        e = self.engine
        def fmt(matrix):
            return '\n'.join('  '.join(f'{v: .8f}' for v in row) for row in matrix)
        return f'Белый {e.illuminant}: {e.white}\n\nЛинейный sRGB → XYZ ({e.illuminant})\n{fmt(e.rgb_xyz)}\n\nXYZ ({e.illuminant}) → линейный sRGB\n{fmt(e.xyz_rgb)}'
