from imgui_bundle import imgui, hello_imgui
from .textures import Textures
import moderngl_window as mglw


# noinspection PyTypeChecker
class Gui:
    def __init__(self, wnd: mglw.WindowConfig):
        Textures.load(wnd)

    def build(self):
        imgui.push_style_var(imgui.StyleVar_.window_rounding, 5.)
        imgui.push_style_color(imgui.Col_.window_bg, (.059, .059, .059, .8))

        imgui.show_demo_window(True)

        self.buildMainToolBar()

        imgui.pop_style_var()
        imgui.pop_style_color()

    def buildMainToolBar(self):
        viewport = imgui.get_main_viewport()
        wnd_flags = imgui.WindowFlags_.no_saved_settings.value | \
                    imgui.WindowFlags_.always_auto_resize.value | \
                    imgui.WindowFlags_.no_title_bar.value
        imgui.set_next_window_pos(viewport.pos, imgui.Cond_.always)
        imgui.begin("toolbar_window", flags=wnd_flags)

        BTN_SIZE = (32,)*2
        imgui.image_button("fractal", Textures.fractal, BTN_SIZE)
        imgui.image_button("settings", Textures.settings, BTN_SIZE)
        imgui.image_button("info", Textures.info, BTN_SIZE)
        imgui.image_button("files", Textures.file, BTN_SIZE)

        imgui.end()
