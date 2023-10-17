from utils.assets import assets_path
import moderngl_window as mglw


def _load(name, wnd: mglw.WindowConfig) -> int:
    tex = wnd.load_texture_2d(assets_path(f"assets/textures/{name}.png"), flip=False)
    return tex.glo

class Textures:
    settings: int
    file: int
    info: int
    fractal: int

    @classmethod
    def load(cls, wnd: mglw.WindowConfig):
        cls.settings = _load("settings", wnd)
        cls.file = _load("floppy-disk", wnd)
        cls.info = _load("info", wnd)
        cls.fractal = _load("fractal", wnd)
