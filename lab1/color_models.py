import math

SPECS = {
    'CMYK': [('C', 0, 100), ('M', 0, 100), ('Y', 0, 100), ('K', 0, 100)],
    'LAB': [('L*', 0, 100), ('a*', -128, 127), ('b*', -128, 127)],
    'RGB': [('R', 0, 255), ('G', 0, 255), ('B', 0, 255)],
}
ILLUMINANTS = {'D65': (.3127, .3290), 'D50': (.3457, .3585), 'E': (1/3, 1/3)}
PRIMARIES = ((.64, .33), (.30, .60), (.15, .06))

BRADFORD = ((.8951, .2664, -.1614), (-.7502, 1.7135, .0367), (.0389, -.0685, 1.0296))

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))

def validate(values, count):
    if len(values) != count or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        raise ValueError('Требуются конечные числовые значения правильной размерности.')

def matvec(a, v):
    return tuple(sum(x*y for x, y in zip(row, v)) for row in a)

def matmul(a, b):
    return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)) for i in range(3))

def inverse(a):

    rows = [list(row) + [float(i == j) for j in range(3)] for i, row in enumerate(a)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda i: abs(rows[i][col]))
        if abs(rows[pivot][col]) < 1e-14:
            raise ValueError('Вырожденная матрица.')
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [v/divisor for v in rows[col]]
        for i in range(3):
            if i != col:
                factor = rows[i][col]
                rows[i] = [v-factor*w for v, w in zip(rows[i], rows[col])]
    return tuple(tuple(row[3:]) for row in rows)

def white_xyz(xy):
    x, y = xy
    return (x/y, 1., (1-x-y)/y)

def derive_rgb_matrix(primaries, white):
    columns = [white_xyz(p) for p in primaries]
    p = tuple(tuple(columns[j][i] for j in range(3)) for i in range(3))
    scales = matvec(inverse(p), white)
    return tuple(tuple(p[i][j]*scales[j] for j in range(3)) for i in range(3))

def linearize(c):
    return c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4

def encode(c):
    return 12.92*c if c <= .0031308 else 1.055*c**(1/2.4)-.055

class ColorEngine:
    def __init__(self, illuminant='D65', separation='GCR', gamut='Clipping'):
        if separation not in ('UCR', 'GCR') or gamut not in ('Clipping', 'Scaling'):
            raise ValueError('Неизвестный режим преобразования.')
        self.separation, self.gamut = separation, gamut
        self.set_illuminant(illuminant)

    def set_illuminant(self, name):
        if name not in ILLUMINANTS:
            raise ValueError('Неизвестный источник освещения.')
        source, target = white_xyz(ILLUMINANTS['D65']), white_xyz(ILLUMINANTS[name])
        base = derive_rgb_matrix(PRIMARIES, source)
        src_lms, dst_lms = matvec(BRADFORD, source), matvec(BRADFORD, target)
        diagonal = tuple(tuple(dst_lms[i]/src_lms[i] if i == j else 0 for j in range(3)) for i in range(3))
        adaptation = matmul(matmul(inverse(BRADFORD), diagonal), BRADFORD)
        self.rgb_xyz = matmul(adaptation, base)
        self.xyz_rgb = inverse(self.rgb_xyz)
        self.illuminant, self.white = name, target

    def rgb_to_xyz(self, rgb):
        validate(rgb, 3)
        return matvec(self.rgb_xyz, tuple(map(linearize, rgb)))

    def xyz_to_rgb(self, xyz):
        validate(xyz, 3)
        return tuple(map(encode, matvec(self.xyz_rgb, xyz)))

    def rgb_to_lab(self, rgb):
        d = 6/29
        def f(t):
            return t**(1/3) if t > d**3 else t/(3*d*d)+4/29
        x, y, z = (f(v/w) for v, w in zip(self.rgb_to_xyz(rgb), self.white))
        return (116*y-16, 500*(x-y), 200*(y-z))

    def lab_to_rgb(self, lab):
        validate(lab, 3)
        light, a, b = lab
        y, d = (light+16)/116, 6/29
        def inv(t):
            return t**3 if t > d else 3*d*d*(t-4/29)
        return self.xyz_to_rgb(tuple(inv(v)*w for v, w in zip((y+a/500, y, y-b/200), self.white)))

    def to_rgb(self, model, values):
        if model not in SPECS:
            raise ValueError('Неизвестная модель.')
        validate(values, len(SPECS[model]))
        if model == 'RGB':
            return tuple(v/255 for v in values)
        if model == 'LAB':
            return self.lab_to_rgb(values)
        c, m, y, k = (v/100 for v in values)
        return ((1-c)*(1-k), (1-m)*(1-k), (1-y)*(1-k))

    def from_rgb(self, model, rgb):
        validate(rgb, 3)
        if model == 'RGB':
            return tuple(v*255 for v in rgb)
        if model == 'LAB':
            return self.rgb_to_lab(rgb)
        if model != 'CMYK':
            raise ValueError('Неизвестная модель.')
        if any(v < -1e-9 or v > 1+1e-9 for v in rgb):
            raise ValueError('Перед цветоделением требуется привести RGB к охвату.')
        rgb = tuple(map(clamp, rgb))
        gray = 1-max(rgb)

        t = clamp((gray-.5)/.5)
        neutrality = 1-(max(rgb)-min(rgb))
        k = gray if self.separation == 'GCR' else gray*t*t*(3-2*t)*neutrality
        if k >= 1-1e-12:
            return (0., 0., 0., 100.)
        return tuple(clamp((1-v-k)/(1-k))*100 for v in rgb)+(k*100,)

    def display_rgb(self, raw):
        validate(raw, 3)
        outside = any(v < -1e-6 or v > 1+1e-6 for v in raw)
        if self.gamut == 'Scaling' and outside:
            low, high = min(0., min(raw)), max(1., max(raw))
            raw = tuple((v-low)/(high-low) for v in raw)
        return tuple(map(clamp, raw)), outside

def hex_color(rgb):
    validate(rgb, 3)
    return '#' + ''.join(f'{round(clamp(v)*255):02X}' for v in rgb)

_default = ColorEngine()
rgb_to_lab = _default.rgb_to_lab
lab_to_rgb = _default.lab_to_rgb
to_rgb = _default.to_rgb
from_rgb = _default.from_rgb
display_rgb = _default.display_rgb
