from typing import Callable, Optional
from math import sin, cos, tan, sinh, cosh, exp, e

class FractalType:
    def __init__(self, name: str, shader_func: str, py_func: Callable[[complex, complex], complex], glsl_source: Optional[str] = None):
        """glsl_source: if non-None, this gets inserted into 'PY_INSERT_RANDOMLY_GENERATED_FUNCTIONS;' part of main.frag, for randomly generated expressions."""
        self.name = name
        self.shader_func = shader_func
        self.py_func = py_func
        self.glsl_source = glsl_source

def cir_dot(a: complex, b: complex) -> complex:
    return complex(a.real*b.real, a.imag*b.imag)

def dot(a: complex, b: complex) -> float:
    return a.real*b.real + a.imag*b.imag

def _ikeda(z, c):
    t = 0.4 - 6.0 / (1.0 + dot(z, z))
    st = sin(t)
    ct = cos(t)
    return complex(1.0 + c.real * (z.real * ct - z.imag * st), c.imag * (z.real * st + z.imag * ct))
def _chirikov(z, c):
    zi_plus = c.imag*sin(z.real)
    return complex(z.real + c.real*(z.imag + zi_plus), z.imag + zi_plus)

FRACTALS = [
    FractalType("Mandelbrot", "mandelbrot", lambda z,c: z*z + c),
    FractalType("Burning Ship", "burning_ship", lambda z,c: complex(abs(z.real), abs(z.imag))**2 + c),
    FractalType("Feather", "feather", lambda z,c: (z**3) / (1 + cir_dot(z, z)) + c),
    FractalType("SFX", "sfx", lambda z,c: z * dot(z,z) - z * cir_dot(c,c)),
    FractalType("Henon", "henon", lambda z,c: complex(1 - c.real*z.real*z.real + z.imag, c.imag * z.real)),
    FractalType("Duffing", "duffing", lambda z,c: complex(z.imag, -c.imag*z.real + c.real*z.imag - z.imag*z.imag*z.imag)),
    FractalType("Ikeda", "ikeda", _ikeda),
    FractalType("Chirikov", "chirikov", _chirikov),
    FractalType("Chirikov Mutate", "chirikov_mutate", lambda z,c: complex(z.real + c.real*z.imag, z.imag + c.imag*sin(z.real))),
]

FRACTAL_NAMES = [f.name for f in FRACTALS]

def addRuntimeFractalType(name: str, glsl_func_name: str, py_expression: str, glsl_expression: str) -> FractalType:
    """Adds fractal types at runtime."""
    FRACTALS.append(new_frac := FractalType(
        name=name,
        shader_func=glsl_func_name,
        py_func=eval(f"lambda z,c: {py_expression}\n"),
        glsl_source=f"VEC2 {glsl_func_name}(VEC2 z,VEC2 c){{return {glsl_expression.replace(' ', '')};}}"
    ))
    FRACTAL_NAMES.append(name)
    return new_frac

def byName(name: str):
    for f in FRACTALS:
        if f.name == name:
            return f
    return None
