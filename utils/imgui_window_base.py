import imgui
import moderngl_window as mglw
from moderngl_window.integrations.imgui import ModernglWindowRenderer
from abc import ABC, abstractmethod

class ImGuiWindowBase(mglw.WindowConfig, ABC):
    aspect_ratio = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        imgui.create_context()
        self.imgui = ModernglWindowRenderer(self.wnd)

    @abstractmethod
    def buildImGui(self, frame_time: float, dt: float):
        pass

    def renderImGui(self, frame_time: float, dt: float):
        imgui.new_frame()
        self.buildImGui(frame_time, dt)
        imgui.render()
        self.imgui.render(imgui.get_draw_data())

    def resize(self, width: int, height: int):
        self.imgui.resize(width, height)

    def key_event(self, key, action, modifiers):
        self.imgui.key_event(key, action, modifiers)

        self.imgui.io.key_shift = modifiers.shift
        self.imgui.io.key_ctrl = modifiers.ctrl
        self.imgui.io.key_alt = modifiers.alt

    def mouse_position_event(self, x, y, dx, dy):
        self.imgui.mouse_position_event(x, y, dx, dy)

    def mouse_drag_event(self, x, y, dx, dy):
        self.imgui.mouse_drag_event(x, y, dx, dy)
        if not imgui.get_io().want_capture_mouse:
            pass

    def mouse_scroll_event(self, x_offset, y_offset):
        self.imgui.mouse_scroll_event(x_offset, y_offset)
        if not imgui.get_io().want_capture_mouse:
            pass

    def mouse_press_event(self, x, y, button):
        self.imgui.mouse_press_event(x, y, button)
        if not imgui.get_io().want_capture_mouse:
            pass

    def mouse_release_event(self, x: int, y: int, button: int):
        self.imgui.mouse_release_event(x, y, button)
        if not imgui.get_io().want_capture_mouse:
            pass

    def unicode_char_entered(self, char):
        self.imgui.unicode_char_entered(char)
