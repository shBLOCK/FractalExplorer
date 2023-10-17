from imgui_bundle import imgui
from gdmath import Vec2
from utils.imgui_utils import colorU32, Color
import math

# noinspection PyTypeChecker
def _label(draw_list: imgui.ImDrawList, num: float, pos: Vec2, align: Vec2, extra_offset: float, col: int):
    text = "{:.15g}".format(num)

    size = Vec2(*imgui.calc_text_size(text))
    pos -= size / 2
    pos += Vec2(size.x / 2 * align.x, size.y / 2 * align.y)
    pos += align * 4
    pos += align * extra_offset
    draw_list.add_text((*pos,), col, text)

def _getMinDistToBound(value, small, big):
    return min(abs(small - value), abs(value - big))

# noinspection PyTypeChecker
def drawCoordinateAxis(translation: Vec2, scale: float, line_col: Color, text_col: Color):
    viewport = imgui.get_main_viewport()
    draw_list = imgui.get_background_draw_list(viewport)
    pos = Vec2(*viewport.pos)
    size = Vec2(*viewport.size)
    pos1 = pos + size
    line_col = colorU32(line_col)
    text_col = colorU32(text_col)

    origin = -translation / scale
    origin.x /= (size.x / size.y)
    origin.y /= -1
    origin = (origin + Vec2(1)) / 2
    origin.x *= size.x
    origin.y *= size.y
    origin += pos
    x_axis_pos = min(max(origin.y, pos.y), pos1.y)
    y_axis_pos = min(max(origin.x, pos.x), pos1.x)
    draw_list.add_line((pos.x, x_axis_pos), (pos1.x, x_axis_pos), line_col, 1)
    draw_list.add_line((y_axis_pos, pos.y), (y_axis_pos, pos1.y), line_col, 1)
    grid_log = math.log10(scale/2)
    grid_log_int = math.floor(grid_log)
    grid = 10 ** grid_log_int
    if grid_log - grid_log_int < .5:
        grid /= 2
    grid_pix = grid / scale * size.y

    i = 1
    draws = 0
    label_size = 8
    while True:
        num = grid * i
        off = grid_pix * i
        xn = origin.x - off
        xp = origin.x + off
        # y is reversed
        yn = origin.y + off
        yp = origin.y - off

        gap = 40
        g_pos = pos + Vec2(-gap, -gap)
        g_pos1 = pos1 + Vec2(+gap, +gap)
        drawing_xn = g_pos.x < xn < g_pos1.x
        drawing_xp = g_pos.x < xp < g_pos1.x
        drawing_yn = g_pos.y < yn < g_pos1.y
        drawing_yp = g_pos.y < yp < g_pos1.y

        if xn <= g_pos.x and xp >= g_pos1.x and yn >= g_pos1.y and yp <= g_pos.y:
            break

        if not (drawing_xn or drawing_xp or drawing_yn or drawing_yp):
            min_dist = min(
                _getMinDistToBound(xn, g_pos.x, g_pos1.x) if xn > g_pos.x else math.inf,
                _getMinDistToBound(xp, g_pos.x, g_pos1.x) if xp < g_pos1.x else math.inf,
                _getMinDistToBound(yn, g_pos.y, g_pos1.y) if yn < g_pos1.y else math.inf,
                _getMinDistToBound(yp, g_pos.y, g_pos1.y) if yp > g_pos.y else math.inf,
            )
            increment = int(min_dist / grid_pix)
            if increment > 0:
                i += increment
                continue

        x_axis_align = -1 if (x_axis_pos < size.y / 2 + pos.y) else 1
        x_axis_align_text = x_axis_align
        x_text_extra_offset = 0
        if x_axis_pos == pos.y or x_axis_pos == pos1.y:
            x_axis_align_text *= -1
            x_text_extra_offset = label_size

        y_axis_align = -1 if (y_axis_pos < size.x / 2 + pos.x) else 1
        y_axis_align_text = y_axis_align
        y_text_extra_offset = 0
        if y_axis_pos == pos.x or y_axis_pos == pos1.x:
            y_axis_align_text *= -1
            y_text_extra_offset = label_size

        if drawing_xp:
            draw_list.add_line((xp, x_axis_pos), (xp, x_axis_pos - label_size * x_axis_align), line_col, 1)
            _label(draw_list, num, Vec2(xp, x_axis_pos), Vec2(0, x_axis_align_text), x_text_extra_offset, text_col)

        if drawing_xn:
            draw_list.add_line((xn, x_axis_pos), (xn, x_axis_pos - label_size * x_axis_align), line_col, 1)
            _label(draw_list, -num, Vec2(xn, x_axis_pos), Vec2(0, x_axis_align_text), x_text_extra_offset, text_col)

        if drawing_yp:
            draw_list.add_line((y_axis_pos, yp), (y_axis_pos - label_size * y_axis_align, yp), line_col, 1)
            _label(draw_list, num, Vec2(y_axis_pos, yp), Vec2(y_axis_align_text, 0), y_text_extra_offset, text_col)

        if drawing_yn:
            draw_list.add_line((y_axis_pos, yn), (y_axis_pos - label_size * y_axis_align, yn), line_col, 1)
            _label(draw_list, -num, Vec2(y_axis_pos, yn), Vec2(y_axis_align_text, 0), y_text_extra_offset, text_col)

        i += 1
        draws += 1