import viztracer
import os
import sys
from typing import Tuple

import moderngl as gl
import imgui
from pygame import Vector2

from utils import imgui_window_base, shader_reload_observer
import settings
from settings import Settings
import fractal_render
import fractals
import audio

import random_fractal_expression_generator

USE_VIZTRACER = False

os.environ["MODERNGL_WINDOW"] = "pyglet"

class FractalWindow(imgui_window_base.ImGuiWindowBase):
    title = "Fractal Explorer"
    # gl_version = (4, 3)
    window_size = (1280, 720)
    fullscreen = False
    resizable = True
    vsync = True
    samples = 4

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.settings = Settings()
        
        self.rndr = fractal_render.Renderer(self.ctx, self.wnd, self.settings)
        self.syn = audio.Synthesizer(self.settings)
        self.do_audio_fade = False
        self.rainbow_path = False
        self.path_follow_audio_speed = True

        self._generated_fractal_cnt = 0

        self.mouse_pos = (0, 0)
        self.dragging = False
        self.mouse_dragging_delta_for_audio_trigger = Vector2()

        self.history_dts = []
        self.render_time = 0.0

    def render(self, frame_time, dt):
        with self.ctx.query(time=True) as gl_query:
            self.rndr.frame(frame_time, dt)
            self.renderImGui(frame_time, dt)
        self.render_time = gl_query.elapsed

        if self.rainbow_path:
            self.settings.path_color = (*imgui.color_convert_hsv_to_rgb(frame_time / 5, 1, 1), 1)

        if self.mouse_dragging_delta_for_audio_trigger.length_squared() > 10*10:
            self._fractalInteract(self.mouse_pos)
            self.mouse_dragging_delta_for_audio_trigger.update(0, 0)

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
        py_exp, gl_exp = random_fractal_expression_generator.genFractalExpression(1, 0.96)
        print(py_exp)
        print(gl_exp)
        print("-"*30)
        with open("generated_fractal_functions.txt", "a") as f:
            f.write(f"{py_exp}\n{gl_exp}\n\n")

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

    # noinspection PyArgumentList
    def buildImGui(self, frame_time: float, dt: float):
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, 8)
        imgui.push_style_color(imgui.COLOR_WINDOW_BACKGROUND, .059, .059, .059, .8)
        imgui.set_next_window_position(0, self.wnd.height / 2, condition=imgui.ALWAYS, pivot_y=.5)
        imgui.begin("Settings", flags=imgui.WINDOW_ALWAYS_AUTO_RESIZE | imgui.WINDOW_NO_SAVED_SETTINGS)

        indent = 8

        # ---------- Fractal ----------
        imgui.set_next_item_open(True, condition=imgui.FIRST_USE_EVER)
        if imgui.collapsing_header("Fractal")[0]:
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

            if imgui.button("Reset Camera"):
                self.rndr.resetTransformation()
            imgui.unindent(indent)
            imgui.separator()

        item_width = 55

        # ---------- Rendering ----------
        imgui.set_next_item_open(False, condition=imgui.FIRST_USE_EVER)
        if imgui.collapsing_header("Rendering")[0]:
            imgui.indent(indent)
            imgui.push_item_width(item_width)
            self.reChTrig, self.settings.iterations = imgui.drag_int("Iters", self.settings.iterations, min_value=1, max_value=32768, change_speed=15, flags=imgui.SLIDER_FLAGS_LOGARITHMIC)
            self.reChTrig, self.settings.render_escape_threshold = imgui.drag_float("Esc. TH.", self.settings.render_escape_threshold, min_value=0.01, max_value=1E7, change_speed=10000, format=f"%.{0 if self.settings.render_escape_threshold > 100 else 3}f", flags=imgui.SLIDER_FLAGS_LOGARITHMIC)
            switched_prec, self.settings.double_precision = imgui.checkbox("64bit Prec.", self.settings.double_precision)
            if switched_prec:
                self.rndr.reloadShaders(reload_source=False)
            self.reChTrig, self.settings.render_samples = imgui.drag_int("Samples", self.settings.render_samples, min_value=1, max_value=10, change_speed=.05)
            self.reChTrig, self.settings.static_frame_mix = imgui.drag_float("St. Frame Mix", self.settings.static_frame_mix, min_value=0, max_value=2, change_speed=.005)

            imgui.separator()
            imgui.text(f"Static Frames: {self.rndr.static_frames if self.rndr.static_frames <= 1000 else '>1000'}")
            imgui.text(f"Anti-Aliasing: {self.rndr.should_apply_aa}")
            imgui.text(f"Rendering: {self.rndr.rendered}")
            self.history_dts.append(dt)
            if sum(self.history_dts) > .1:
                self.history_dts.pop(0)
                avg_dt = sum(self.history_dts) / len(self.history_dts)
                imgui.text("%.1f fps" % (1 / max(avg_dt, .001)))
                imgui.text("%.3f ms" % (self.render_time / 1E6))
            if imgui.button("Reset Settings##render"):
                self.settings.resetRenderSettings()
                self.rndr.reloadShaders(reload_source=False)
            imgui.pop_item_width()
            imgui.unindent(indent)
            imgui.separator()

        # ---------- Path ----------
        imgui.set_next_item_open(False, condition=imgui.FIRST_USE_EVER)
        if imgui.collapsing_header("Path")[0]:
            imgui.indent(indent)
            imgui.push_item_width(item_width)
            imgui.align_text_to_frame_padding()
            imgui.text("Path Speed")
            imgui.same_line()
            _, self.path_follow_audio_speed = imgui.checkbox("##path_speed_follow_audio", self.path_follow_audio_speed)
            if imgui.is_item_hovered():
                imgui.set_tooltip("Follow Audio Settings")
            if self.path_follow_audio_speed:
                self.settings.path_speed = self.settings.sample_freq
            else:
                imgui.same_line()
                imgui.set_next_item_width(item_width - 10)
                _, self.settings.path_speed = imgui.drag_int("##path_speed_drag", self.settings.path_speed, min_value=0,
                                                             max_value=10000, change_speed=100,
                                                             flags=imgui.SLIDER_FLAGS_LOGARITHMIC)
            _, self.settings.path_segments = imgui.drag_int("Path Segments", self.settings.path_segments, min_value=1,
                                                            max_value=10000, change_speed=100,
                                                            flags=imgui.SLIDER_FLAGS_LOGARITHMIC)

            imgui.set_next_item_width(item_width + 20)
            _, self.settings.path_width = imgui.slider_float("Path Width", self.settings.path_width, min_value=1.,
                                                             max_value=10.)
            imgui.align_text_to_frame_padding()
            imgui.text("Path Color")
            imgui.same_line()
            _, self.settings.path_color = imgui.color_edit4("##path_color", *self.settings.path_color,
                                                            flags=imgui.COLOR_EDIT_ALPHA_PREVIEW_HALF | imgui.COLOR_EDIT_NO_INPUTS)
            imgui.same_line()
            # imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND, *imgui.color_convert_hsv_to_rgb(frame_time / 5, .6, .6), .54)
            # imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND_HOVERED, *imgui.color_convert_hsv_to_rgb(frame_time / 5, .7, .7), .4)
            # imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND_ACTIVE, *imgui.color_convert_hsv_to_rgb(frame_time / 5, .8, .8), .67)
            changed, self.rainbow_path = imgui.checkbox("##rainbow_color", self.rainbow_path)
            # imgui.pop_style_color(3)
            if imgui.is_item_hovered():
                imgui.set_tooltip("Rainbow Color")

            imgui.separator()
            imgui.text(f"Path Length: {len(self.rndr.path_buffer) - 1}")
            imgui.text(f"Path Iters: {self.rndr.path_current_iters}")
            imgui.text(f"Path Generation: {self.rndr.path_should_generate}")

            if imgui.button("Reset Settings##path"):
                self.settings.resetPathSettings()
                self.path_follow_audio_speed = True
                self.rainbow_path = False
            imgui.pop_item_width()
            imgui.unindent(indent)
            imgui.separator()

        # ---------- Audio ----------
        item_width = 100
        imgui.set_next_item_open(False, condition=imgui.FIRST_USE_EVER)
        if imgui.collapsing_header("Audio")[0]:
            imgui.indent(indent)
            imgui.push_item_width(item_width)
            _, self.settings.volume = imgui.slider_float("Volume", self.settings.volume, 0., 1.)

            changed, self.do_audio_fade = imgui.checkbox("Fade", self.do_audio_fade)
            if changed:
                self.settings.audio_fade = 7 if self.do_audio_fade else 0
                self.syn.updateFadeMode()
            if self.do_audio_fade:
                changed, self.settings.audio_fade = imgui.slider_float("Fade Factor", self.settings.audio_fade, 2., 10., flags=imgui.SLIDER_FLAGS_LOGARITHMIC)
                if changed:
                    self.syn.updateFadeMode()

            _, self.settings.sample_freq = imgui.drag_int("Freq.", self.settings.sample_freq, min_value=200, max_value=10000, change_speed=100)
            _, self.settings.audio_buffer_size = imgui.drag_int("Buffer Size", self.settings.audio_buffer_size, min_value=16, max_value=16384, change_speed=100, flags=imgui.SLIDER_FLAGS_LOGARITHMIC)
            _, self.settings.max_sources = imgui.slider_int("Max Sources", self.settings.max_sources, min_value=1, max_value=10)
            changed, new_interp = imgui.combo("Interp.", self.settings.interpolation.value[0], settings.INTERP_NAMES)
            if changed:
                self.settings.interpolation = settings.AudioInterpolations[settings.INTERP_NAMES[new_interp]]
            _, self.settings.audio_escape_threshold = imgui.drag_float("Esc. TH.", self.settings.audio_escape_threshold, min_value=0.01, max_value=1E5, change_speed=100, format=f"%.{0 if self.settings.render_escape_threshold > 100 else 3}f", flags=imgui.SLIDER_FLAGS_LOGARITHMIC)
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
        if shader_reload_observer.should_reload:
            print("File change detected, reloading shaders.")
            try:
                self.rndr.reloadShaders(reload_source=True)
            except gl.Error as e:
                print(e)
            shader_reload_observer.should_reload = False

    def _fractalInteract(self, pixel_pos: Tuple[int, int]):
        pos = self.rndr.transform(self.rndr.toNDR(pixel_pos))

        self.rndr.startPathVisualization(pixel_pos)

        if not self.syn.should_fade:
            self.syn.stopSound()
        self.syn.playFractal(self.settings.fractal, complex(pos.x, pos.y), None, 1.0)

    def mouse_scroll_event(self, x_offset, y_offset):
        super().mouse_scroll_event(x_offset, y_offset)
        if not imgui.get_io().want_capture_mouse:
            self.rndr.scroll(y_offset, self.rndr.toNDR(self.mouse_pos))

    def mouse_drag_event(self, x, y, dx, dy):
        super().mouse_drag_event(x, y, dx, dy)
        self.mouse_pos = (x, y)
        if not imgui.get_io().want_capture_mouse:
            if self.wnd.mouse_states.left:
                self.dragging = True
                self.rndr.drag((dx, dy))
            if self.wnd.mouse_states.middle:
                self.mouse_dragging_delta_for_audio_trigger.x += dx
                self.mouse_dragging_delta_for_audio_trigger.y += dy

    def mouse_press_event(self, x, y, button):
        super().mouse_press_event(x, y, button)
        # if not imgui.get_io().want_capture_mouse:
        #     if button == 1:
        #         self.playAudio((x, y))

    def mouse_release_event(self, x: int, y: int, button: int):
        super().mouse_release_event(x, y, button)
        if not imgui.get_io().want_capture_mouse:
            if button == 1:
                if not self.dragging:
                    self._fractalInteract((x, y))
                self.dragging = False
            elif button == 2:
                self.syn.stopSound()
                self.rndr.stopPathVisualization()

    def key_event(self, key, action, modifiers):
        super().key_event(key, action, modifiers)
        if not imgui.get_io().want_capture_mouse:
            if key == self.wnd.keys.R and action == self.wnd.keys.ACTION_PRESS:
                self.rndr.resetTransformation()

    def mouse_position_event(self, x, y, dx, dy):
        super().mouse_position_event(x, y, dx, dy)
        self.mouse_pos = (x, y)

    def resize(self, width: int, height: int):
        super().resize(width, height)
        self.rndr.onResize((width, height))

    def close(self):
        self.syn.terminate()

if USE_VIZTRACER:
    vt = viztracer.viztracer.VizTracer()
    vt.start()

FractalWindow.run()

if USE_VIZTRACER:
    vt.stop()
    vt.save()

sys.exit()
