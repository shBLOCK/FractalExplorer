from imgui_bundle import imgui
import sdl2
import sdl2.ext
import moderngl as gl
import moderngl_window.context.sdl2.window
from moderngl_window.context.base.window import dummy_func
from abc import ABC, abstractmethod
import ctypes


# class SDL2ModernGLImGuiWindowBase(ABC):
#     # noinspection PyTypeChecker
#     def __init__(self, size=(1280,720),
#                  caption="SDL2 ModernGL ImGui Window",
#                  resizable=True,
#                  window_flags=sdl2.SDL_WINDOW_ALLOW_HIGHDPI,
#                  gl_ver=(3,0),
#                  multi_viewport=False):
#         if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_TIMER | sdl2.SDL_INIT_GAMECONTROLLER) != 0:
#             raise RuntimeError(f"Failed to initialize SDL2: {sdl2.SDL_GetError()}")
#
#         sdl2.SDL_GL_SetAttribute(sdl2.SDL_GL_CONTEXT_FLAGS, 0)
#         sdl2.SDL_GL_SetAttribute(sdl2.SDL_GL_CONTEXT_PROFILE_MASK, sdl2.SDL_GL_CONTEXT_PROFILE_CORE)
#         sdl2.video.SDL_GL_SetAttribute(sdl2.SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, 1)
#         sdl2.SDL_GL_SetAttribute(sdl2.SDL_GL_CONTEXT_MAJOR_VERSION, gl_ver[0])
#         sdl2.SDL_GL_SetAttribute(sdl2.SDL_GL_CONTEXT_MINOR_VERSION, gl_ver[1])
#
#         # Enable native IME
#         sdl2.SDL_SetHint(sdl2.SDL_HINT_IME_SHOW_UI, b"1")
#
#         # Create window with graphics context
#         sdl2.SDL_GL_SetAttribute(sdl2.SDL_GL_DOUBLEBUFFER, 1)
#         sdl2.SDL_GL_SetAttribute(sdl2.SDL_GL_DEPTH_SIZE, 24)
#         sdl2.SDL_GL_SetAttribute(sdl2.SDL_GL_STENCIL_SIZE, 8)
#         window_flags |= sdl2.SDL_WINDOW_OPENGL
#         if resizable:
#             window_flags |= sdl2.SDL_WINDOW_RESIZABLE
#         self._window = sdl2.SDL_CreateWindow(caption.encode(), sdl2.SDL_WINDOWPOS_CENTERED,
#                                        sdl2.SDL_WINDOWPOS_CENTERED, *size, window_flags)
#         self._gl_context = sdl2.SDL_GL_CreateContext(self._window)
#         sdl2.SDL_GL_MakeCurrent(self._window, self._gl_context)
#         sdl2.SDL_GL_SetSwapInterval(1)  # Enable vsync
#
#         gl.create_context()
#
#         imgui.create_context()
#         io = imgui.get_io()
#         imgui.style_colors_dark()
#
#         if multi_viewport:
#             io.config_flags |= imgui.ConfigFlags_.viewports_enable
#             style = imgui.get_style()
#             style.window_rounding = 0.0
#             window_bg_color = style.color_(imgui.Col_.window_bg)
#             window_bg_color.w = 1.0
#             style.set_color_(imgui.Col_.window_bg, window_bg_color)
#
#         window_address = ctypes.cast(self._window, ctypes.c_void_p).value
#         gl_context_address = ctypes.cast(self._gl_context, ctypes.c_void_p).value
#         imgui.backends.sdl2_init_for_opengl(window_address, gl_context_address)
#
#         imgui.backends.opengl3_init(None)
#
#         # Load default font
#         font_atlas = imgui.get_io().fonts
#         font_atlas.add_font_default()
#
#     @abstractmethod
#     def render(self):
#         pass
#
#     def run(self):

class SDL2ModernGLImGuiWindow(moderngl_window.context.sdl2.window.Window):
    # noinspection PyTypeChecker
    def __init__(self, multi_viewport=False, event_callback=dummy_func, **kwargs):
        super().__init__(**kwargs)

        self._process_sdl_event_func = event_callback

        imgui.create_context()
        self.io = imgui.get_io()
        imgui.style_colors_dark()

        if multi_viewport:
            self.io.config_flags |= imgui.ConfigFlags_.viewports_enable
            style = imgui.get_style()
            style.window_rounding = 0.0
            window_bg_color = style.color_(imgui.Col_.window_bg)
            window_bg_color.w = 1.0
            style.set_color_(imgui.Col_.window_bg, window_bg_color)

        window_address = ctypes.cast(self._window, ctypes.c_void_p).value
        gl_context_address = ctypes.cast(self._context, ctypes.c_void_p).value
        imgui.backends.sdl2_init_for_opengl(window_address, gl_context_address)

        imgui.backends.opengl3_init(None)

        # Load default font
        font_atlas = self.io.fonts
        font_atlas.add_font_default()

    def render(self, time=0.0, frame_time=0.0) -> None:
        imgui.backends.opengl3_new_frame()
        imgui.backends.sdl2_new_frame()
        imgui.new_frame()
        super().render(time, frame_time)

    # noinspection PyTypeChecker
    def swap_buffers(self) -> None:
        if self.frames != 0:
            imgui.render()
            imgui.backends.opengl3_render_draw_data(imgui.get_draw_data())

            # Update and Render additional Platform Windows
            # (Platform functions may change the current OpenGL context, so we save/restore it to make it easier to paste this code elsewhere.
            #  For this specific demo app we could also call SDL_GL_MakeCurrent(window, gl_context) directly)
            if self.io.config_flags & imgui.ConfigFlags_.viewports_enable > 0:
                backup_current_window = sdl2.SDL_GL_GetCurrentWindow()
                backup_current_context = sdl2.SDL_GL_GetCurrentContext()
                imgui.update_platform_windows()
                imgui.render_platform_windows_default()
                sdl2.SDL_GL_MakeCurrent(backup_current_window, backup_current_context)

        super().swap_buffers()

    def process_events(self):
        """Handle all queued events in sdl2 dispatching events to standard methods"""
        for event in sdl2.ext.get_events():
            event_address = ctypes.addressof(event)
            imgui.backends.sdl2_process_event(event_address)
            if event.type == sdl2.SDL_MOUSEMOTION:
                if self.mouse_states.any:
                    self._mouse_drag_event_func(
                        event.motion.x,
                        event.motion.y,
                        event.motion.xrel,
                        event.motion.yrel,
                    )
                else:
                    self._mouse_position_event_func(
                        event.motion.x,
                        event.motion.y,
                        event.motion.xrel,
                        event.motion.yrel,
                    )

            elif event.type == sdl2.SDL_MOUSEBUTTONDOWN:
                self._handle_mods()
                button = self._mouse_button_map.get(event.button.button, None)
                if button is not None:
                    self._handle_mouse_button_state_change(button, True)
                    self._mouse_press_event_func(
                        event.motion.x, event.motion.y, button,
                    )

            elif event.type == sdl2.SDL_MOUSEBUTTONUP:
                self._handle_mods()
                button = self._mouse_button_map.get(event.button.button, None)
                if button is not None:
                    self._handle_mouse_button_state_change(button, False)
                    self._mouse_release_event_func(
                        event.motion.x, event.motion.y, button,
                    )

            elif event.type in [sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP]:
                self._handle_mods()

                if (
                        self._exit_key is not None
                        and event.key.keysym.sym == self._exit_key
                ):
                    self.close()

                if self._fs_key is not None and event.key.keysym.sym == self._fs_key and event.type == sdl2.SDL_KEYDOWN:
                    self.fullscreen = not self.fullscreen

                if event.type == sdl2.SDL_KEYDOWN:
                    self._key_pressed_map[event.key.keysym.sym] = True
                elif event.type == sdl2.SDL_KEYUP:
                    self._key_pressed_map[event.key.keysym.sym] = False

                self._key_event_func(event.key.keysym.sym, event.type, self._modifiers)

            elif event.type == sdl2.SDL_TEXTINPUT:
                self._unicode_char_entered_func(event.text.text.decode())

            elif event.type == sdl2.SDL_MOUSEWHEEL:
                self._handle_mods()
                self._mouse_scroll_event_func(
                    float(event.wheel.x), float(event.wheel.y)
                )

            elif event.type == sdl2.SDL_QUIT:
                self.close()

            elif event.type == sdl2.SDL_WINDOWEVENT:
                if event.window.event in [sdl2.SDL_WINDOWEVENT_RESIZED, sdl2.SDL_WINDOWEVENT_SIZE_CHANGED]:
                    if event.window.windowID == 1:
                        self.resize(event.window.data1, event.window.data2)
                elif event.window.event == sdl2.SDL_WINDOWEVENT_MINIMIZED:
                    self._iconify_func(True)
                elif event.window.event == sdl2.SDL_WINDOWEVENT_RESTORED:
                    self._iconify_func(False)
                elif event.window.event == sdl2.SDL_WINDOWEVENT_CLOSE:
                    if event.window.windowID == sdl2.SDL_GetWindowID(self._window):
                        self.close()

            self._process_sdl_event_func(event)

    def destroy(self) -> None:
        """Gracefully close the window"""
        imgui.backends.opengl3_shutdown()
        imgui.backends.sdl2_shutdown()
        imgui.destroy_context()
        sdl2.SDL_GL_DeleteContext(self._context)
        sdl2.SDL_DestroyWindow(self._window)
        sdl2.SDL_Quit()
