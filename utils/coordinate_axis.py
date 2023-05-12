from imgui_bundle import imgui
from pygame.math import Vector2, clamp
from utils.imgui_utils import colorU32, Color
import math

# noinspection PyTypeChecker
def _label(draw_list: imgui.ImDrawList, num: float, pos: Vector2, align: Vector2, extra_offset: float, col: int):
    text = "{:.15g}".format(num)

    size = Vector2(imgui.calc_text_size(text))
    pos -= size / 2
    pos += Vector2(size.x / 2 * align.x, size.y / 2 * align.y)
    pos += 4 * align
    pos += extra_offset * align
    draw_list.add_text((*pos,), col, text)

# noinspection PyTypeChecker
def drawCoordinateAxis(translation: Vector2, scale: float, line_col: Color, text_col: Color):
    # TODO: why bg draw list doesn't work when window is small??
    draw_list = imgui.get_background_draw_list()
    viewport = imgui.get_main_viewport()
    pos = Vector2(viewport.pos)
    size = Vector2(viewport.size)
    pos1 = pos + size
    line_col = colorU32(line_col)
    text_col = colorU32(text_col)

    origin = -translation / scale
    origin.x /= (size.x / size.y)
    origin.y /= -1
    origin = (origin + Vector2(1)) / 2
    origin.x *= size.x
    origin.y *= size.y
    origin += pos
    x_axis_pos = clamp(origin.y, pos.y, pos1.y)
    y_axis_pos = clamp(origin.x, pos.x, pos1.x)
    draw_list.add_line((pos.x, x_axis_pos), (pos1.x, x_axis_pos), line_col, 1)
    draw_list.add_line((y_axis_pos, pos.y), (y_axis_pos, pos1.y), line_col, 1)
    grid_log = math.log10(scale/2)
    grid_log_int = math.floor(grid_log)
    grid = 10 ** grid_log_int
    if grid_log - grid_log_int < .5:
        grid /= 2
    grid_pix = grid / scale * size.y

    i = 1
    label_size = 8
    while True:
        num = grid * i
        off = grid_pix * i
        xn = origin.x - off
        xp = origin.x + off
        # y is reversed
        yn = origin.y + off
        yp = origin.y - off
        if xn < pos.x and xp > pos1.x and yn > pos1.y and yp < pos.y:
            break

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

        draw_list.add_line((xp, x_axis_pos), (xp, x_axis_pos - label_size * x_axis_align), line_col, 1)
        _label(draw_list, num, (xp, x_axis_pos), Vector2(0, x_axis_align_text), x_text_extra_offset, text_col)

        draw_list.add_line((xn, x_axis_pos), (xn, x_axis_pos - label_size * x_axis_align), line_col, 1)
        _label(draw_list, -num, (xn, x_axis_pos), Vector2(0, x_axis_align_text), x_text_extra_offset, text_col)

        draw_list.add_line((y_axis_pos, yp), (y_axis_pos - label_size * y_axis_align, yp), line_col, 1)
        _label(draw_list, num, (y_axis_pos, yp), Vector2(y_axis_align_text, 0), y_text_extra_offset, text_col)

        draw_list.add_line((y_axis_pos, yn), (y_axis_pos - label_size * y_axis_align, yn), line_col, 1)
        _label(draw_list, -num, (y_axis_pos, yn), Vector2(y_axis_align_text, 0), y_text_extra_offset, text_col)

        i += 1
