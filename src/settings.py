from enum import Enum

import fractals

class Settings:
    # noinspection PyTypeChecker
    def __init__(self):
        # Fractal Settings
        self.fractal: fractals.FractalType = fractals.byName("Mandelbrot")

        # Render Settings
        self.iterations = None
        self.render_escape_threshold = None
        self.render_samples = None
        self.static_frame_mix = None
        self.double_precision = None
        self.resetRenderSettings()

        # Path Settings
        self.path_width = None
        self.path_color = None
        self.path_speed = None
        self.path_segments = None
        self.resetPathSettings()

        # Audio Settings
        self.volume = None
        self.audio_fade = None
        self.sample_freq = None
        self.audio_buffer_size = None
        self.max_sources = None
        self.interpolation: AudioInterpolations = None
        self.audio_escape_threshold = None
        self.resetAudioSettings()

    def resetRenderSettings(self):
        self.iterations = 2048
        self.render_escape_threshold = 100000.
        self.render_samples = 1
        self.static_frame_mix = .5
        self.double_precision = False

    def resetPathSettings(self):
        self.path_width = 1.
        self.path_color = (1., 0., 0., 1.)
        self.path_speed = 4000
        self.path_segments = 300

    def resetAudioSettings(self):
        self.volume = .5
        self.audio_fade = 0.
        self.sample_freq = 4000
        self.audio_buffer_size = 128
        self.max_sources = 3
        self.interpolation = AudioInterpolations.Cubic
        self.audio_escape_threshold = 10000.

class AudioInterpolations(Enum):
    Nearest = (0, "nearest")
    Linear = (1, "linear")
    Quadratic = (2, "quadratic")
    Cubic = (3, "cubic")

INTERP_NAMES = list(i.name for i in AudioInterpolations)
