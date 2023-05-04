import colorsys
from typing import Tuple, Sequence, Callable

Color = Tuple[float, float, float, float] | Tuple[float, float, float]

ColorGradient = Sequence[Tuple[float, Color]]
ColorGradient.__doc__ = """List of color \"Key Frames\", which is a tuple of (<position> (0 to 1), <color> (tuple of 3 or 4 floats))."""

def lerpColor(color_a: Color, color_b: Color, t: float) -> Color:
    t = max(min(t, 1), 0)
    # noinspection PyTypeChecker
    return tuple(a+(b-a)*t for a,b in zip(color_a, color_b))

def getColorInGradient(gradient: ColorGradient, pos: float, repeating: bool) -> Color:
    if not repeating:
        if pos < 0 or pos > 1:
            raise ValueError(f"Position out of range ({pos})")
    else:
        pos %= 1

    if len(gradient) == 1:
        return gradient[0][1]

    last_mark = gradient[0]
    for m in gradient[1:]:
        if last_mark[0] <= pos <= m[0]:
            return lerpColor(last_mark[1], m[1], (pos - last_mark[0]) / (m[0] - last_mark[0]) if m[0] != last_mark[0] else 0)
        last_mark = m
    if repeating:
        return lerpColor(last_mark[1], gradient[0][1], (pos - last_mark[0]) / ((gradient[0][0] + 1) - last_mark[0]))

def generateRainbowGradient(marks: int = 6) -> ColorGradient:
    return [(i/marks, colorsys.hsv_to_rgb(i/marks, 1, 1)) for i in range(marks)]

def gradientFromFunc(marks: int, repeating: bool, func: Callable[[float], Color]):
    div = marks if repeating else (marks - 1)
    return [(i/div, func(i/div)) for i in range(marks)]
