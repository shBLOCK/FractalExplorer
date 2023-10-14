from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import win32gui

MONITORED_FILES = (
    "shaders\\main.vert",
    "shaders\\main.frag",
    "shaders\\path.vert",
    "shaders\\path.frag",
)

should_reload = False
class ShaderReloadListener(FileSystemEventHandler):
    def __init__(self):
        self.should_reload = False
    def on_modified(self, e):
        global should_reload
        if e.src_path in MONITORED_FILES:
            should_reload = True
shader_reload_observer = Observer()
shader_reload_observer.schedule(ShaderReloadListener(), "shaders")
shader_reload_observer.start()

def bringToFront():
    window = pg.display.get_wm_info()["window"]
    win32gui.SetForegroundWindow(window)
