import logging
import math
from math import floor
import random
from typing import Tuple
import numpy as np
import moderngl as gl
from moderngl_window.context.base import BaseWindow
from gdmath import Vec2
from pyrr import Matrix44

import fractals
from settings import Settings
from utils import color_utils

COLOR_PALETTE_SAMPLES = 1024

class Renderer:
    # noinspection PyTypeChecker
    def __init__(self, ctx: gl.Context, wnd: BaseWindow, settings: Settings):
        self._ctx = ctx
        self._window = wnd
        self._settings = settings
        self.frame_time = 0

        # ----- Camera -----
        self.scale = 100
        self.translation = Vec2(0, 0)
        self.target_scale = 1.5
        self.target_translation = Vec2(0, 0)

        # ----- Fractal image rendering -----
        self._screen_quad_vbo = self._ctx.buffer(np.array([
            -1, 1, 0, 0,
            1, 1, 1, 0,
            -1, -1, 0, 1,
            1, -1, 1, 1
        ], dtype=np.float32))
        self._main_vao: gl.VertexArray = None
        self._vsh_source = None
        self._fsh_source = None
        self._main_program: gl.Program = None
        self._last_frame: gl.Texture = None
        self._last_frame_fbo: gl.Framebuffer = None
        self.onResize(self._window.size)
        self.static_frames = 1
        self.rendered = True
        self.should_apply_aa = True
        self._color_palette_tex: gl.Texture = None
        self.reloadColorPalette()

        # ----- Path rendering -----
        self._path_program: gl.Program = None
        self._path_begin_time = None
        self.path_buffer = []
        self._path_c_point = None  # c
        self._path_current_z = None  # z
        self.path_current_iters = 0
        self.path_should_generate = False  # should continue to generate the path (stop when escaped)

        self.reloadShaders(reload_source=True)

    def _preProcessMainFragmentShader(self, source: str):
        source = source.replace("PY_FRACTAL_FUNC", self._settings.fractal.shader_func)
        source = source.replace("PY_PRECISION_DEFINE", "define" if self._settings.double_precision else "undef")
        source = source.replace(
            "PY_INSERT_RANDOMLY_GENERATED_FUNCTIONS;",
            "".join(f.glsl_source for f in fractals.FRACTALS if f.glsl_source is not None)
        )
        return source

    def reloadShaders(self, reload_source: bool):
        v_source, f_source = self._vsh_source, self._fsh_source
        if reload_source:
            with open("shaders/main.vert") as vsh_file, open("shaders/main.frag") as fsh_file:
                v_source, f_source = vsh_file.read(), fsh_file.read()
        org_v_source, org_f_source = v_source, f_source
        f_source = self._preProcessMainFragmentShader(f_source)
        new_program = self._ctx.program(vertex_shader=v_source, fragment_shader=f_source)

        new_render_obj = self._ctx.vertex_array(new_program, [(self._screen_quad_vbo, "2f 2f", "vert", "texCoord")])
        if self._main_vao is not None:
            self._main_program.release()
            self._main_vao.release()
        self._main_program = new_program
        self._main_vao = new_render_obj

        self._vsh_source, self._fsh_source = org_v_source, org_f_source

        self.reRender()

        if reload_source:
            with open("shaders/path.vert") as path_vsh, open("shaders/path.geom") as path_gsh, open(
                    "shaders/path.frag") as path_fsh:
                new_path_program = self._ctx.program(vertex_shader=path_vsh.read(), geometry_shader=path_gsh.read(), fragment_shader=path_fsh.read())
                if self._path_program is not None:
                    self._path_program.release()
                self._path_program = new_path_program

    def reloadColorPalette(self):
        data = np.full(shape=COLOR_PALETTE_SAMPLES*4, fill_value=255, dtype=np.uint8)
        gradient = self._settings.color_palette
        for i in range(COLOR_PALETTE_SAMPLES):
            color = color_utils.getColorInGradient(gradient, i / COLOR_PALETTE_SAMPLES, True)
            data[i*4+0] = min(max(floor(color[0]*255), 0), 255)
            data[i*4+1] = min(max(floor(color[1]*255), 0), 255)
            data[i*4+2] = min(max(floor(color[2]*255), 0), 255)

        if self._color_palette_tex is not None:
            self._color_palette_tex.release()
        self._color_palette_tex = self._ctx.texture((COLOR_PALETTE_SAMPLES, 1), components=4, dtype="nu1", data=data)
        self._color_palette_tex.filter = (gl.LINEAR, gl.NEAREST)
        self._color_palette_tex.repeat_x = True

        self.reRender()

    def reRender(self):
        self.static_frames = 1

    def setFractal(self, fractal: fractals.FractalType):
        self._settings.fractal = fractal
        self.reloadShaders(reload_source=False)
        self.stopPathVisualization()

    def toNDR(self, pixel_pos: Tuple[float, float]):
        return Vec2(pixel_pos[0] / self._window.width, -pixel_pos[1] / self._window.height) * 2 - Vec2(1, -1)

    def transform(self, ndr: Vec2):
        return Vec2(ndr.x * self._window.aspect_ratio, ndr.y) * self.scale + self.translation

    def scroll(self, delta: float, ndr: Vec2):
        ndr = Vec2(-ndr.x * self._window.aspect_ratio, -ndr.y)
        delta_scale = -delta * self.target_scale / 5
        self.target_scale += delta_scale
        delta = ndr * delta_scale
        self.target_translation += delta

    def drag(self, rel: Tuple[float, float]):
        self.target_translation += Vec2(-rel[0], rel[1]) / self._window.height * 2 * self.scale

    def resetTransformation(self):
        self.target_translation = Vec2(0)
        self.target_scale = 1.5

    def _updateTransformation(self, dt: float):
        spd = 10
        dt = min(dt, 1/(spd+.1))

        self.target_scale = max(self.target_scale, 1E-16 if self._settings.double_precision else 1E-7)

        if (self.target_translation - self.translation).length_sqr < (self.scale / self._window.width * 2)**2:
            self.translation = +self.target_translation
        if abs(self.target_scale - self.scale) < self.target_scale * (2 / self._window.width):
            self.scale = self.target_scale

        self.scale += (self.target_scale - self.scale) * dt * 10
        self.translation += (self.target_translation - self.translation) * dt * 10

    def onResize(self, size: Tuple[int, int]):
        if self._last_frame is not None:
            self._last_frame.release()
            self._last_frame_fbo.release()
        self._last_frame = self._ctx.texture(size, components=4)
        self._last_frame.filter = (gl.NEAREST, gl.NEAREST)
        self._last_frame_fbo = self._ctx.framebuffer(
            self._last_frame,
            self._ctx.depth_renderbuffer(size))

        self.reRender()

    def _applyCameraUniforms(self, program: gl.Program):
        program["uScale"] = self.scale
        program["uTranslation"] = self.translation

    def _renderFractalImage(self):
        if self.scale == self.target_scale and self.translation == self.target_translation:
            self.static_frames += 1
            if self._settings.static_frame_mix == 0:
                old_frame_mix = 0
            else:
                old_frame_mix = (1 - (1 / (self.static_frames * self._settings.static_frame_mix)))
        else:
            self.static_frames = 1
            old_frame_mix = 0
        ulp_mul = 1 if self._settings.double_precision else (2 ** 27)
        ulp = max(math.ulp(self.translation.x), math.ulp(self.translation.y)) * ulp_mul
        self.should_apply_aa = (self._settings.static_frame_mix != 0) and self.scale / self._window.aspect_ratio > ulp * self._window.width
        if not self.should_apply_aa:
            old_frame_mix = 0

        if old_frame_mix > .95:
            self._ctx.copy_framebuffer(src=self._last_frame_fbo, dst=self._ctx.screen)
            self.rendered = False
            return
        self.rendered = True

        self._last_frame.use(0)
        self._main_program["uLastFrame"] = 0
        self._main_program["uOldFramesMixFactor"] = old_frame_mix
        self._main_program["uHashSeed"] = random.randint(-(2 ** 31), (2 ** 31) - 1)
        # self.main_program["uTime"] = frame_time

        self._applyCameraUniforms(self._main_program)
        try:
            self._main_program["uAspectRatio"] = self._window.aspect_ratio
        except KeyError as e:
            print("uAspectRatio doesn't exist in main program???")

        swizzle = self.scale / self._window.height
        if not self.should_apply_aa:
            swizzle = 0
        self._main_program["uSwizzleMultiplier"] = swizzle if self.static_frames > 1 else 0

        self._color_palette_tex.use(1)
        self._main_program["uColorPalette"] = 1
        self._main_program["uColorChangeSpeed"] = self._settings.color_change_speed
        self._main_program["uSamples"] = self._settings.render_samples
        self._main_program["uIters"] = self._settings.iterations
        self._main_program["uEscapeThreshold"] = self._settings.render_escape_threshold ** 2

        # noinspection PyTypeChecker
        self._main_vao.render(mode=gl.TRIANGLE_STRIP)

        self._ctx.copy_framebuffer(src=self._ctx.screen, dst=self._last_frame_fbo)

    def startPathVisualization(self, pos: Vec2):
        self.path_buffer.clear()
        self._path_c_point = complex(pos.x, pos.y)
        self._path_current_z = complex(pos.x, pos.y)
        self.path_buffer.append(self._path_current_z)

        self._path_begin_time = self.frame_time
        self.path_current_iters = 0
        self.path_should_generate = True

    def stopPathVisualization(self):
        self._path_current_z = None
        self.path_should_generate = False
        self.path_current_iters = 0
        self.path_buffer.clear()

    def _updatePath(self, frame_time: float):
        # ----- Generation -----
        if self.path_should_generate:
            target_iters = int((frame_time - self._path_begin_time) * self._settings.path_speed)
            missing_iters = target_iters - self.path_current_iters
            if missing_iters > 0:
                for i in range(missing_iters):
                    try:
                        next_z = self._settings.fractal.py_func(self._path_current_z, self._path_c_point)
                    except ArithmeticError as e:
                        logging.error(f"Path gen failed: {e}")
                        self.path_should_generate = False
                        break
                    delta = next_z - self._path_current_z
                    if abs(delta.real)+abs(delta.imag) < .0000001 or next_z.real*next_z.real + next_z.imag*next_z.imag > self._settings.audio_escape_threshold ** 2:
                        self.path_should_generate = False
                        break
                    # print(self._path_current_z)
                    self._path_current_z = next_z
                    self.path_buffer.append(next_z)
                    self.path_current_iters += 1

        # ----- Removing Excess -----
        to_remove = len(self.path_buffer) - self._settings.path_segments - 1
        if to_remove > 0:
            del self.path_buffer[:to_remove]

    def _buildPathRenderBuffers(self):
        """Prepare the buffers for multi-polyline rendering. Closed polyline must have their
            last point identical to their first point."""

        line_complex = np.array(self.path_buffer)
        line_xs = np.real(line_complex)
        line_ys = np.imag(line_complex)
        line = np.dstack((line_xs, line_ys)).astype("f4")[0]

        indices = []

        idx = np.arange(len(line) + 2) - 1
        idx[0], idx[-1] = 0, len(line) - 1

        indices.append(idx)
        indices.append([-1])

        return line, np.concatenate(indices).astype("i4")

    # noinspection PyTypeChecker
    def _renderPaths(self, frame_time: float):
        if self._path_current_z is None:
            return

        self._updatePath(frame_time)

        vert_buf, index_buf = self._buildPathRenderBuffers()
        vbo = self._ctx.buffer(vert_buf)
        ibo = self._ctx.buffer(index_buf)

        path_vao = self._ctx.simple_vertex_array(self._path_program, vbo, "vPos", index_buffer=ibo)

        self._applyCameraUniforms(self._path_program)
        self._path_program["uAspectRatio"] = self._window.aspect_ratio
        self._path_program["uScreenSize"] = self._window.size

        self._path_program["color"] = self._settings.path_color
        self._path_program["antialias"] = 1
        self._path_program["linewidth"] = self._settings.path_width
        self._path_program["miter_limit"] = -1
        self._path_program["projection"].write(
            Matrix44.orthogonal_projection(0, self._window.width, self._window.height, 0, 0.5, -0.5, dtype="f4")
        )

        self._ctx.disable(gl.CULL_FACE)
        self._ctx.enable(gl.BLEND)
        path_vao.render(mode=gl.LINE_STRIP_ADJACENCY)

        vbo.release()
        ibo.release()
        path_vao.release()

    def frame(self, frame_time: float, dt: float):
        self.frame_time = frame_time
        self._updateTransformation(dt)
        try:
            self._renderFractalImage()
        except Exception as e:
            logging.error(f"Fractal render failed: {e}")
        self._renderPaths(frame_time)
