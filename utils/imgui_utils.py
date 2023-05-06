from typing import List, Tuple
from dataclasses import dataclass

from imgui_bundle import imgui
from pygame.math import Vector2

if __name__ == '__main__':
    from color_utils import Color, ColorGradient, getColorInGradient
else:
    from utils.color_utils import Color, ColorGradient, getColorInGradient

def colorU32(color: Color):
    if len(color) == 3:
        color = (*color, 1)
    return imgui.color_convert_float4_to_u32(color)

def get_style_color_u32(idx: int):
    return colorU32(imgui.get_style_color_vec4(idx))

@dataclass
class _ColorMark:
    pos: float
    color: Color


# noinspection PyTypeChecker
def drawGradient(gradient: ColorGradient, repeating: bool, x0, y0, x1, y1, border: bool = True):
    draw_list = imgui.get_window_draw_list()
    width = x1 - x0
    last_color = None
    last_pos = None
    for mark in gradient:
        if last_color is not None:
            # Draw gradient rects
            col0 = colorU32(last_color)
            col1 = colorU32(mark[1])
            draw_list.add_rect_filled_multi_color(
                (x0 + width * last_pos, y0),
                (x0 + width * mark[0], y1),
                col0, col1, col1, col0)
        last_color = mark[1]
        last_pos = mark[0]

    # Draw the last part of the gradient
    col0 = colorU32(last_color)
    col1 = col0 if not repeating else colorU32(gradient[0][1])
    draw_list.add_rect_filled_multi_color(
        (x0 + width * last_pos, y0),
        (x1, y1),
        col0, col1, col1, col0)

    # Draw outer frame of the gradient
    if border:
        draw_list.add_rect((x0, y0), (x1, y1), get_style_color_u32(imgui.Col_.border))

# noinspection PyTypeChecker
class ColorGradientEdit:
    """
    A widget for editing a multipart color gradient.
    Can be set to repeating mode to make it gradient across the start and the end
    Controls:
        Hold the Marks to drag them.
        Double click or Right click them to open the gui for the mark, and remove them if shift is pressed.
        Click on the gradient to add Marks.
    """

    def __init__(self, identifier: str, gradient: ColorGradient, repeating: bool = False, alpha=False,
                 color_edit_flags: int = imgui.ColorEditFlags_.uint8.value | imgui.ColorEditFlags_.display_rgb.value | imgui.ColorEditFlags_.input_rgb.value | imgui.ColorEditFlags_.picker_hue_bar.value):
        """:param gradient: the initial gradient, there must be at least one element in it, and there must be one at position 0. If not repeating, there must also be one at position 1."""

        # assert len(gradient) >= 1
        #
        # has_alpha = gradient[0][1] == 4
        # for c in gradient:
        #     c_has_alpha = len(c[1]) == 4
        #     assert c_has_alpha == has_alpha, "Color alpha channel mismatch"
        # if has_alpha:
        #     raise NotImplementedError("Alpha channel isn't supported yet!")
        self._alpha_mode = alpha

        self._id = identifier
        self._repeating = repeating
        self._color_edit_flags = color_edit_flags | imgui.ColorEditFlags_.no_side_preview

        self._marks: List[_ColorMark] = []
        self.gradient = gradient
        assert self._marks[0].pos == 0
        if not repeating:
            assert self._marks[-1].pos == 1

        self._dragging_begin_pos = None
        self._dragging_mark = None
        self._editing_mark = None

        self._clicked_pos = None

    @property
    def gradient(self) -> ColorGradient:
        g = [(h.pos, h.color) for h in self._marks]
        g.sort(key=lambda v: v[0])
        return g

    @gradient.setter
    def gradient(self, gradient: ColorGradient):
        assert len(gradient) >= 1
        self._dragging_mark = None
        self._marks.clear()
        self._marks = []
        for m in gradient:
            pos = m[0]
            color_cns = len(m[1])
            assert color_cns == 3 or color_cns == 4
            color = m[1] if color_cns == 4 else (*m[1], 1)
            self._marks.append(_ColorMark(pos, color))
        self._sortHandles()
        assert self._marks[0].pos == 0
        if not self._repeating:
            assert self._marks[-1].pos == 1

    def _sortHandles(self):
        self._marks.sort(key=lambda h: h.pos)

    def _tooltipPosColor(self, pos: float, color: Color):
        imgui.begin_tooltip()
        imgui.text("Pos: %.2f" % pos)
        imgui.separator()
        size = imgui.get_text_line_height_with_spacing() * 2
        imgui.color_button(f"##{self._id}.tooltip.color_display",
                           color, size=(size, size))
        imgui.same_line()
        imgui.begin_group()
        if len(color) == 3:
            imgui.text("%.2f %.2f %.2f" % color)
        else:
            imgui.text("%.2f %.2f %.2f %.2f" % color)
        hex_color = colorU32(color)
        hex_color = ((hex_color & 0x0000FF) << 16) | (hex_color & 0x00FF00) | ((hex_color & 0xFF0000) >> 16)
        imgui.text("#%06X" % hex_color)
        imgui.end_group()
        imgui.end_tooltip()

    # noinspection PyArgumentList
    def _processHandle(self, mark: _ColorMark, io, draw_list, pos0: Vector2, pos1: Vector2, width: float, mark_size: float) -> Tuple[bool, bool]:
        """:returns if this mark should get removed and if this mark was modified"""

        x = pos0.x + mark.pos * width
        color = colorU32(mark.color)
        rect_x = x - mark_size / 2
        rect_y = pos1.y + mark_size / 2
        rect_x1 = rect_x + mark_size
        rect_y1 = rect_y + mark_size

        hovering = imgui.is_mouse_hovering_rect((rect_x, rect_y), (rect_x1, rect_y1))

        # ---------- Interaction ----------
        modified = False
        can_move = mark != self._marks[0]
        popup_id = f"{self._id}.popup_{id(mark)}"

        if self._dragging_mark == mark:
            delta = imgui.get_mouse_drag_delta(0)
            mark.pos = self._dragging_begin_pos + (delta.x / width)
            mark.pos = max(min(mark.pos, 1), 0)
            modified = True
        if hovering:
            if can_move and self._dragging_mark is None and imgui.is_mouse_clicked(imgui.MouseButton_.left):
                self._dragging_mark = mark
                self._dragging_begin_pos = mark.pos
            if imgui.is_mouse_double_clicked(0) or imgui.is_mouse_released(imgui.MouseButton_.right):
                self._dragging_mark = None
                if can_move and io.key_shift:
                    return True, modified  # remove mark
                else:
                    imgui.open_popup(popup_id)
                    self._editing_mark = mark

        # Display tooltip
        if self._editing_mark != mark and (hovering or self._dragging_mark == mark):
            self._tooltipPosColor(mark.pos, mark.color)

        should_remove = False
        # Avoid displaying twice for repeating gradient's first color mark
        if not (self._repeating and mark == self._marks[0] and mark.pos == 1):
            if imgui.begin_popup(popup_id):
                changed, new_color = imgui.color_picker4(f"##{self._id}.color_edit", list(float(v) for v in mark.color), self._color_edit_flags, ref_col=0)
                if changed:
                    mark.color = new_color
                    modified = True
                imgui.separator()
                if can_move:
                    imgui.push_style_color(imgui.Col_.header_hovered, (.9, .1, .1, 1))
                    if imgui.menu_item("Remove", None, False)[0]:
                        should_remove = True
                    imgui.pop_style_color()
                imgui.end_popup()
            else:
                if self._editing_mark == mark:
                    self._editing_mark = None
        if should_remove:
            return True, modified

        # ---------- Drawing ----------
        if hovering:
            bg_color = imgui.Col_.scrollbar_grab_active if imgui.is_mouse_down(imgui.MouseButton_.left) else imgui.Col_.scrollbar_grab_hovered
        else:
            bg_color = imgui.Col_.scrollbar_grab
        bg_color = get_style_color_u32(bg_color)

        # Tag shape
        draw_list.path_clear()
        draw_list.path_line_to((x, pos1.y))
        draw_list.path_line_to((rect_x1, rect_y))
        draw_list.path_line_to((rect_x1, rect_y1))
        draw_list.path_line_to((rect_x, rect_y1))
        draw_list.path_line_to((rect_x, rect_y))
        draw_list.path_fill_convex(bg_color)
        draw_list.path_line_to((x, pos1.y))
        draw_list.path_line_to((rect_x1, rect_y))
        draw_list.path_line_to((rect_x1, rect_y1))
        draw_list.path_line_to((rect_x, rect_y1))
        draw_list.path_line_to((rect_x, rect_y))
        draw_list.path_stroke(get_style_color_u32(imgui.Col_.border), flags=imgui.ImDrawFlags_.closed)

        # Color rect
        padding = 1
        draw_list.add_rect_filled((rect_x + padding, rect_y + padding), (rect_x1 - padding, rect_y1 - padding), color)

        return False, modified

    def build(self) -> bool:
        """:returns was gradient modified"""
        draw_list = imgui.get_window_draw_list()

        style = imgui.get_style()
        window_padding = style.window_padding
        mark_size = style.grab_min_size

        width = imgui.calc_item_width()
        height = imgui.get_frame_height()
        imgui.invisible_button("##tet", (width, height + mark_size * 1.5))
        pos0 = Vector2(*imgui.get_item_rect_min())
        pos0.x += max(mark_size / 2 - window_padding.x + 5, 0)
        pos1 = Vector2(*imgui.get_item_rect_max())
        pos1.x -= max(mark_size / 2 - window_padding.x + 5, 0)
        pos1.y = pos0.y + height
        width = pos1.x - pos0.x

        io = imgui.get_io()
        modified = False

        gradient = self.gradient
        drawGradient(gradient, self._repeating, *pos0, *pos1)

        # To avoid deadlocks
        if imgui.is_mouse_released(imgui.MouseButton_.left):
            self._dragging_mark = None

        to_remove = []
        for mark in self._marks:
            # Draw color mark
            remove_mark, mark_modified = self._processHandle(mark, io, draw_list, pos0, pos1, width, mark_size)
            if remove_mark:
                to_remove.append(mark)
            if mark_modified or remove_mark:
                modified = True

        for h in to_remove:
            self._marks.remove(h)
            if self._dragging_mark == h:
                self._dragging_mark = None
            if self._editing_mark == h:
                self._editing_mark = None

        # Draw one color mark identical to the first one on the left side if this is a repeating gradient
        if self._repeating:
            mark = self._marks[0]
            mark.pos = 1
            self._processHandle(mark, io, draw_list, pos0, pos1, width, mark_size)
            mark.pos = 0

        # Handle interactions with the gradient rect
        popup_id = f"{self._id}.gradient_popup"
        hovering_grad = imgui.is_mouse_hovering_rect((*pos0,), (*pos1,))
        hovering_pos = (imgui.get_mouse_pos().x - pos0.x) / width
        hovering_color = getColorInGradient(gradient, hovering_pos, self._repeating)
        if self._dragging_mark is None and self._editing_mark is None:
            if hovering_grad:
                # Addd new mark
                if imgui.is_mouse_clicked(imgui.MouseButton_.left):
                    self._marks.append(_ColorMark(hovering_pos, hovering_color))
                    modified = True
                # Open popup
                if imgui.is_mouse_clicked(imgui.MouseButton_.right):
                    imgui.open_popup(popup_id)
                    self._clicked_pos = hovering_pos

        if imgui.begin_popup(popup_id):
            if imgui.menu_item("Add Mark", None, False)[0]:
                self._marks.append(_ColorMark(self._clicked_pos, getColorInGradient(gradient, self._clicked_pos, self._repeating)))
                modified = True
            if imgui.menu_item("Spread Evenly", None, False)[0]:
                total = len(self._marks) + (0 if self._repeating else -1)
                for i,m in enumerate(self._marks):
                    m.pos = i / total
                modified = True
            imgui.end_popup()
        elif hovering_grad:
            self._tooltipPosColor(hovering_pos, hovering_color)

        if modified:
            self._sortHandles()
        return modified

if __name__ == "__main__":
    import moderngl_window
    import window as utils_window
    import logging
    import weakref
    from moderngl_window.timers.clock import Timer

    # noinspection PyTypeChecker
    class TestWindow(moderngl_window.WindowConfig):
        title = "Widget Test"
        clear_color = (.3,.3,.3,1)

        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            self.gradient_edit = ColorGradientEdit(
                identifier="##test_gradient_edit",
                gradient=[(0, (1,0,0)), (.3, (0,1,0)), (.8, (0,0,1))],
                repeating=True
            )

        def render(self, frame_time: float, dt: float):
            self.buildImGui(frame_time, dt)

        def buildImGui(self, frame_time: float, dt: float):
            imgui.show_demo_window(False)

            if imgui.begin("Test", flags=imgui.WindowFlags_.no_saved_settings)[0]:
                imgui.text("Widget Test")
                self.gradient_edit.build()
                gradient = self.gradient_edit.gradient
                t = frame_time / 3
                imgui.color_button("##color_display", getColorInGradient(gradient, t, True))
                imgui.same_line()
                imgui.text("%.2f - %.2f" % (t % 1, t))
                imgui.end()

    def main():
        logger = logging.getLogger(__name__)

        config_cls = TestWindow
        moderngl_window.setup_basic_logging(config_cls.log_level)
        window_cls = utils_window.SDL2ModernGLImGuiWindow

        # Calculate window size
        size = config_cls.window_size
        size = int(size[0]), int(size[1])

        # Resolve cursor
        show_cursor = config_cls.cursor

        window = window_cls(
            title=config_cls.title,
            size=size,
            fullscreen=config_cls.fullscreen,
            resizable=config_cls.resizable,
            gl_version=config_cls.gl_version,
            aspect_ratio=config_cls.aspect_ratio,
            vsync=config_cls.vsync,
            samples=config_cls.samples,
            cursor=show_cursor if show_cursor is not None else True,
        )
        window.print_context_info()
        moderngl_window.activate_context(window=window)
        timer = Timer()
        config = config_cls(ctx=window.ctx, wnd=window, timer=timer)
        # Avoid the event assigning in the property setter for now
        # We want the even assigning to happen in WindowConfig.__init__
        # so users are free to assign them in their own __init__.
        window._config = weakref.ref(config)

        # Swap buffers once before staring the main loop.
        # This can trigged additional resize events reporting
        # a more accurate buffer size
        window.swap_buffers()
        window.set_default_viewport()

        timer.start()

        while not window.is_closing:
            current_time, delta = timer.next_frame()

            if config.clear_color is not None:
                window.clear(*config.clear_color)

            # Always bind the window framebuffer before calling render
            window.use()

            window.render(current_time, delta)
            if not window.is_closing:
                window.swap_buffers()

        _, duration = timer.stop()
        window.destroy()
        if duration > 0:
            logger.info(
                "Duration: {0:.2f}s @ {1:.2f} FPS".format(
                    duration, window.frames / duration
                )
            )

    main()
