import colorsys
import logging
import weakref

import sdl2
import sdl2.touch
import os
import sys
from typing import Tuple

import moderngl as gl
import moderngl_window
from moderngl_window.timers.clock import Timer
from imgui_bundle import imgui
from gdmath import Vec2, Vec2i

from utils import imgui_utils
try:
    from utils import shader_reload_observer
except ImportError:
    pass
import utils.window
import settings
from settings import Settings
import fractal_render
import fractals
import audio
import gui.gui

import random_fractal_expression_generator

USE_VIZTRACER = False

os.environ["MODERNGL_WINDOW"] = "pyglet"

sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)

def default_window_size() -> Tuple[int, int]:
    screen_size = sdl2.SDL_Rect()
    sdl2.SDL_GetDisplayUsableBounds(0, screen_size)
    screen_size = Vec2i(screen_size.w, screen_size.h)

    i = 1
    while True:
        size = Vec2i(16 * i, 9 * i)
        if size.x > screen_size.x * 0.9 or size.y > screen_size.y * 0.9:
            break
        i += 1

    i -= 1

    result = (16 * i, 9 * i)
    print(f"Choosing window size: {result}")

    return result

class FractalWindow(moderngl_window.WindowConfig):
    title = "Fractal Explorer - By shBLOCK"
    gl_version = (4, 0)
    window_size = default_window_size()
    fullscreen = False
    resizable = True
    vsync = True
    aspect_ratio = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.wnd.exit_key = None
        self.wnd.sdl_event_func = self.sdl_event

        self.gui = gui.gui.Gui(self)
        self.settings = Settings()

        self.rndr = fractal_render.FractalRenderer(self.ctx, self.wnd, self.settings)
        self.syn = audio.Synthesizer(self.settings)
        self._do_audio_fade = False
        self._rainbow_path = False
        self._path_follow_audio_speed = True
        self._lock_transform = False
        self._show_coordinate_axis = ~False

        self._generated_fractal_cnt = 0

        # self.mouse_pos = (0, 0)
        self._dragging = False
        self._mouse_dragging_delta_for_audio_trigger = Vec2()
        self._color_gradient_edit = imgui_utils.ColorGradientEdit(
            identifier="##fractal_color_palette",
            gradient=self.settings.color_palette,
            repeating=True
        )

        self._history_dts = []
        self.render_time = 0.0

    def render(self, frame_time, dt):
        with self.ctx.query(time=True) as gl_query:
            self.rndr.frame(frame_time, dt)
        self.render_time = gl_query.elapsed

        self.buildImGui(frame_time, dt)
        if self._show_coordinate_axis:
            self.rndr.drawCoordinateAxis()

        self.gui.build()

        if self._rainbow_path:
            self.settings.path_color = (*colorsys.hsv_to_rgb(frame_time / 5, 1, 1), 1)

        if self._mouse_dragging_delta_for_audio_trigger.length_sqr > 10*10:
            self._fractalInteract(self.mouse_pos)
            self._mouse_dragging_delta_for_audio_trigger = Vec2(0)

        self.syn.update()

        self.detectDebugShaderReload()

    @property
    def reChTrig(self):
        return None
    # Re-Render trigger helper property
    @reChTrig.setter
    def reChTrig(self, changed: bool):
        if changed:
            self.rndr.reRender()

    def _generateRandomFractalExpression(self):
        py_exp, gl_exp = random_fractal_expression_generator.genFractalExpression(1, 0.8)
        print(py_exp)
        print(gl_exp)
        print("-"*30)
        try:
            with open("generated_fractal_functions.txt", "a") as f:
                f.write(f"{py_exp}\n{gl_exp}\n\n")
        except IOError as e:
            print(f"Failed to save generated fractal function: {e}")

        self._generated_fractal_cnt += 1
        new_frac = fractals.addRuntimeFractalType(
            name=f"Generated {self._generated_fractal_cnt}",
            glsl_func_name=f"frac_generated_{self._generated_fractal_cnt}",
            py_expression=py_exp,
            glsl_expression=gl_exp
        )
        self.rndr.setFractal(new_frac)
        self.rndr.resetTransformation()
        self.syn.stopSound()

    # def buildFractalUI(self):
    #     imgui.begin("Fractal", flags=imgui.WindowFlags_.no_saved_settings)
    #     imgui.combo()
    #     imgui.input_text_multiline()
    #     imgui.end()

    # noinspection PyArgumentList,PyTypeChecker
    def buildImGui(self, frame_time: float, dt: float):
        imgui.push_style_var(imgui.StyleVar_.window_rounding, 8.)
        imgui.push_style_color(imgui.Col_.window_bg, (.059, .059, .059, .8))
        # imgui.set_next_window_pos((0, self.wnd.height / 2), imgui.Cond_.always, (0, .5))
        window_visible, _ = imgui.begin("Settings", flags=imgui.WindowFlags_.always_auto_resize.value | imgui.WindowFlags_.no_saved_settings.value)
        if not window_visible:
            imgui.end()
            imgui.pop_style_color()
            imgui.pop_style_var()
            return

        indent = 8

        # ---------- Fractal ----------
        imgui.set_next_item_open(True, imgui.Cond_.first_use_ever)
        if imgui.collapsing_header("Fractal"):
            imgui.indent(indent)
            pos = self.rndr.transform(self.rndr.toNDR(self.mouse_pos))
            imgui.text("X: %.8f" % pos.x)
            imgui.text("Y: %.8f" % pos.y)
            imgui.text("%.2f + %.2fi" % (pos.x, pos.y))
            scale = 1 / self.rndr.scale
            if scale < 1E7:
                scale_text = "%.1f" % scale
            else:
                scale_text = "%.2e" % scale
            imgui.text("Scale: %s" % scale_text)

            _, self._show_coordinate_axis = imgui.checkbox("Show Axis", self._show_coordinate_axis)

            imgui.set_next_item_width(100)
            changed, new_ft = imgui.combo("##Type", fractals.FRACTAL_NAMES.index(self.settings.fractal.name), list(
                fractals.FRACTAL_NAMES))
            if changed:
                self.rndr.setFractal(fractals.byName(fractals.FRACTAL_NAMES[new_ft]))
                self.rndr.resetTransformation()
                self.syn.stopSound()

            if imgui.button("Gen"):
                self._generateRandomFractalExpression()
            if imgui.is_item_hovered():
                imgui.set_tooltip("Randomly generate a fractal function!")

            changed, self._lock_transform = imgui.checkbox("Lock View", self._lock_transform)
            if changed:
                self._dragging = False

            if imgui.button("Reset View"):
                self.rndr.resetTransformation()
            imgui.unindent(indent)
            imgui.separator()

        item_width = 55

        # ---------- Rendering ----------
        imgui.set_next_item_open(False, cond=imgui.Cond_.first_use_ever)
        if imgui.collapsing_header("Rendering"):
            imgui.indent(indent)
            imgui.push_item_width(item_width)
            self.reChTrig, self.settings.iterations = imgui.drag_int("Iters", self.settings.iterations, v_min=1, v_max=32768, v_speed=15, flags=imgui.SliderFlags_.logarithmic)
            self.reChTrig, self.settings.render_escape_threshold = imgui.drag_float("Esc. TH.", self.settings.render_escape_threshold, v_min=0.01, v_max=1E7, v_speed=10000, format=f"%.{0 if self.settings.render_escape_threshold > 100 else 3}f", flags=imgui.SliderFlags_.logarithmic)
            switched_prec, self.settings.double_precision = imgui.checkbox("64bit Prec.", self.settings.double_precision)
            if switched_prec:
                self.rndr.reloadShaders(reload_source=False)
            self.reChTrig, self.settings.render_samples = imgui.drag_int("Samples", self.settings.render_samples, v_min=1, v_max=10, v_speed=.05)
            self.reChTrig, self.settings.static_frame_mix = imgui.drag_float("St. Frame Mix", self.settings.static_frame_mix, v_min=0, v_max=2, v_speed=.005)

            imgui.text("Color Palette:")
            imgui.set_next_item_width(-1)
            if self._color_gradient_edit.build():
                self.settings.color_palette = self._color_gradient_edit.gradient
                self.rndr.reloadColorPalette()
            self.reChTrig, self.settings.color_change_speed = imgui.drag_float("Color Speed", self.settings.color_change_speed, v_min=0, v_max=1, v_speed=.005, flags=imgui.SliderFlags_.logarithmic)

            imgui.separator()
            imgui.text(f"Static Frames: {self.rndr.static_frames if self.rndr.static_frames <= 1000 else '>1000'}")
            imgui.text(f"Anti-Aliasing: {self.rndr.should_apply_aa}")
            imgui.text(f"Rendering: {self.rndr.rendered}")
            self._history_dts.append(dt)
            if sum(self._history_dts) > .1:
                self._history_dts.pop(0)
                avg_dt = 0 if len(self._history_dts) == 0 else sum(self._history_dts) / len(self._history_dts)
                imgui.text("%.1f fps" % (1 / max(avg_dt, .001)))
                imgui.text("%.3f ms" % (self.render_time / 1E6))
            if imgui.button("Reset Settings##render"):
                self.settings.resetRenderSettings()
                self.rndr.reloadShaders(reload_source=False)
                self._color_gradient_edit.gradient = self.settings.color_palette
                self.rndr.reloadColorPalette()
            imgui.pop_item_width()
            imgui.unindent(indent)
            imgui.separator()

        # ---------- Path ----------
        imgui.set_next_item_open(False, cond=imgui.Cond_.first_use_ever)
        if imgui.collapsing_header("Path"):
            imgui.indent(indent)
            imgui.push_item_width(item_width)
            imgui.align_text_to_frame_padding()
            imgui.text("Path Speed")
            imgui.same_line()
            _, self._path_follow_audio_speed = imgui.checkbox("##path_speed_follow_audio", self._path_follow_audio_speed)
            if imgui.is_item_hovered():
                imgui.set_tooltip("Follow Audio Settings")
            if self._path_follow_audio_speed:
                self.settings.path_speed = self.settings.sample_freq
            else:
                imgui.same_line()
                imgui.set_next_item_width(item_width - 10)
                _, self.settings.path_speed = imgui.drag_int("##path_speed_drag", self.settings.path_speed, v_min=0,
                                                             v_max=10000, v_speed=100,
                                                             flags=imgui.SliderFlags_.logarithmic)
            _, self.settings.path_segments = imgui.drag_int("Path Segments", self.settings.path_segments, v_min=1,
                                                            v_max=10000, v_speed=100,
                                                            flags=imgui.SliderFlags_.logarithmic)

            imgui.set_next_item_width(item_width + 20)
            _, self.settings.path_width = imgui.slider_float("Path Width", self.settings.path_width, v_min=1.,
                                                             v_max=10.)
            imgui.align_text_to_frame_padding()
            imgui.text("Path Color")
            imgui.same_line()
            _, self.settings.path_color = imgui.color_edit4("##path_color", self.settings.path_color,
                                                            flags=imgui.ColorEditFlags_.alpha_preview_half.value | imgui.ColorEditFlags_.no_inputs)
            imgui.same_line()
            # imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND, *imgui.color_convert_hsv_to_rgb(frame_time / 5, .6, .6), .54)
            # imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND_HOVERED, *imgui.color_convert_hsv_to_rgb(frame_time / 5, .7, .7), .4)
            # imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND_ACTIVE, *imgui.color_convert_hsv_to_rgb(frame_time / 5, .8, .8), .67)
            changed, self._rainbow_path = imgui.checkbox("##rainbow_color", self._rainbow_path)
            # imgui.pop_style_color(3)
            if imgui.is_item_hovered():
                imgui.set_tooltip("Rainbow Color")

            imgui.separator()
            imgui.text(f"Path Length: {len(self.rndr.path_buffer) - 1}")
            imgui.text(f"Path Iters: {self.rndr.path_current_iters}")
            imgui.text(f"Path Generation: {self.rndr.path_should_generate}")

            if imgui.button("Reset Settings##path"):
                self.settings.resetPathSettings()
                self._path_follow_audio_speed = True
                self._rainbow_path = False
            imgui.pop_item_width()
            imgui.unindent(indent)
            imgui.separator()

        # ---------- Audio ----------
        item_width = 100
        imgui.set_next_item_open(False, cond=imgui.Cond_.first_use_ever)
        if imgui.collapsing_header("Audio"):
            imgui.indent(indent)
            imgui.push_item_width(item_width)
            _, self.settings.volume = imgui.slider_float("Volume", self.settings.volume, 0., 1.)

            changed, self._do_audio_fade = imgui.checkbox("Fade", self._do_audio_fade)
            if changed:
                self.settings.audio_fade = 7 if self._do_audio_fade else 0
                self.syn.updateFadeMode()
            if self._do_audio_fade:
                changed, self.settings.audio_fade = imgui.slider_float("Fade Factor", self.settings.audio_fade, 2., 10., flags=imgui.SliderFlags_.logarithmic)
                if changed:
                    self.syn.updateFadeMode()

            _, self.settings.sample_freq = imgui.drag_int("Freq.", self.settings.sample_freq, v_min=200, v_max=10000, v_speed=100)
            _, self.settings.audio_buffer_size = imgui.drag_int("Buffer Size", self.settings.audio_buffer_size, v_min=16, v_max=16384, v_speed=100, flags=imgui.SliderFlags_.logarithmic)
            _, self.settings.max_sources = imgui.slider_int("Max Sources", self.settings.max_sources, v_min=1, v_max=10)
            changed, new_interp = imgui.combo("Interp.", self.settings.interpolation.value[0], settings.INTERP_NAMES)
            if changed:
                self.settings.interpolation = settings.AudioInterpolations[settings.INTERP_NAMES[new_interp]]
            _, self.settings.audio_escape_threshold = imgui.drag_float("Esc. TH.", self.settings.audio_escape_threshold, v_min=0.01, v_max=1E5, v_speed=100, format=f"%.{0 if self.settings.render_escape_threshold > 100 else 3}f", flags=imgui.SliderFlags_.logarithmic)
            if imgui.button("Reset Settings##audio"):
                self.settings.resetAudioSettings()
            imgui.separator()
            imgui.text(f"Sources: {len(self.syn.sources)}")
            if imgui.button("Stop Sound"):
                self.syn.stopSound()
            imgui.pop_item_width()
            imgui.unindent(indent)

        imgui.end()
        imgui.pop_style_color()
        imgui.pop_style_var()

    # noinspection PyArgumentList
    def detectDebugShaderReload(self):
        if "shader_reload_observer" not in globals():
            return

        if shader_reload_observer.should_reload:
            print("File change detected, reloading shaders.")
            try:
                self.rndr.reloadShaders(reload_source=True)
            except gl.Error as e:
                print(e)
            shader_reload_observer.should_reload = False

    def _fractalInteract(self, pixel_pos: Tuple[int, int]):
        pixel_pos = pixel_pos
        pos = self.rndr.transform(self.rndr.toNDR(pixel_pos))

        if not self.syn.should_fade:
            self.syn.stopSound()
        self.syn.playFractal(self.settings.fractal, complex(pos.x, pos.y), None, 1.0)

        self.rndr.startPathVisualization(pos)

    def mouse_scroll_event(self, x_offset, y_offset):
        super().mouse_scroll_event(x_offset, y_offset)
        if not imgui.get_io().want_capture_mouse:
            if not self._lock_transform:
                self.rndr.scroll(y_offset, self.rndr.toNDR(self.mouse_pos))

    @property
    def mouse_pos(self) -> Tuple[float, float]:
        mp = imgui.get_mouse_pos()
        wp = imgui.get_main_viewport().pos
        # noinspection PyRedundantParentheses
        return (mp.x - wp.x, mp.y - wp.y)

    def mouse_drag_event(self, x, y, dx, dy):
        super().mouse_drag_event(x, y, dx, dy)
        # self.mouse_pos = (x, y)
        if not imgui.get_io().want_capture_mouse:
            device = sdl2.touch.SDL_GetTouchDevice(0)
            fingers = sdl2.touch.SDL_GetNumTouchFingers(device)
            if self.wnd.mouse_states.left:
                if (not self._lock_transform) and fingers <= 1:
                    self._dragging = True
                    self.rndr.drag((dx, dy))
                else:
                    self._dragging = False
            if self.wnd.mouse_states.middle:
                self._mouse_dragging_delta_for_audio_trigger.x += dx
                self._mouse_dragging_delta_for_audio_trigger.y += dy

    def mouse_press_event(self, x, y, button):
        super().mouse_press_event(x, y, button)
        # if not imgui.get_io().want_capture_mouse:
        #     if button == 1:
        #         self.playAudio((x, y))

    def mouse_release_event(self, x: int, y: int, button: int):
        super().mouse_release_event(x, y, button)
        if not imgui.get_io().want_capture_mouse:
            if button == 1:
                if not self._dragging:
                    self._fractalInteract(self.mouse_pos)
                self._dragging = False
            elif button == 2:
                self.syn.stopSound()
                self.rndr.stopPathVisualization()

    def key_event(self, key, action, modifiers):
        super().key_event(key, action, modifiers)
        if not imgui.get_io().want_capture_mouse:
            if key == self.wnd.keys.R and action == self.wnd.keys.ACTION_PRESS:
                if not self._lock_transform:
                    self.rndr.resetTransformation()

    def mouse_position_event(self, x, y, dx, dy):
        super().mouse_position_event(x, y, dx, dy)
        # self.mouse_pos = (x, y)

    def resize(self, width: int, height: int):
        super().resize(width, height)
        self.rndr.onResize((width, height))

    def sdl_event(self, event):
        if event.type == sdl2.SDL_MULTIGESTURE:
            if not self._lock_transform:
                center = Vec2(event.mgesture.x * 2 - 1, event.mgesture.y * -2 + 1)
                delta = event.mgesture.dDist
                self.rndr.scroll(delta * 30, center)

    def close(self):
        self.syn.terminate()

def main():
    logger = logging.getLogger(__name__)

    config_cls = FractalWindow
    moderngl_window.setup_basic_logging(config_cls.log_level)

    # Calculate window size
    size = config_cls.window_size
    size = int(size[0]), int(size[1])

    # Resolve cursor
    show_cursor = config_cls.cursor

    window = utils.window.SDL2ModernGLImGuiWindow(
        title=config_cls.title,
        size=size,
        fullscreen=config_cls.fullscreen,
        resizable=config_cls.resizable,
        gl_version=config_cls.gl_version,
        aspect_ratio=config_cls.aspect_ratio,
        vsync=config_cls.vsync,
        samples=config_cls.samples,
        cursor=show_cursor if show_cursor is not None else True,
        multi_viewport=True,
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
    # This can trigger additional resize events reporting
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

if USE_VIZTRACER:
    import viztracer
    vt = viztracer.viztracer.VizTracer()
    vt.start()

main()

if USE_VIZTRACER:
    vt.stop()
    vt.save()

sys.exit()
