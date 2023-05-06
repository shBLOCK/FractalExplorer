from math import floor, ceil
from typing import Optional, List
import time
import miniaudio
import numpy as np
from scipy.interpolate import interp1d
import logging

import fractals
from fractals import FractalType
from settings import Settings

AUDIO_SAMPLE_RATE = 44100
AUDIO_FADE_CUTOFF = .001

class FracAudioSource:
    # use Julia mode if julia_point is not None
    def __init__(self, syn: "Synthesizer", fractal: FractalType, point: complex, julia_point: Optional[complex], amp: float):
        self.syn = syn
        self.settings = syn.settings

        self.fractal = fractal
        self.is_julia = julia_point is not None
        self.frac_c = julia_point if self.is_julia else point  # c
        self.frac_z = point  # z
        self.sample_id = -1  # the id of the sample self.frac_z
        self.sample_sum = complex(0, 0)  # sum of all samples, for finding the center point
        self.iter_stopped = False
        self._generating = True

        self.sample_buffer = []
        self.sample_buffer_first_id = -1

        self.amp = amp

        self.frame = 0
        self.total_time = 0.

        self.stream = miniaudio.PlaybackDevice(
            output_format=miniaudio.SampleFormat.FLOAT32,
            nchannels=2,
            sample_rate=AUDIO_SAMPLE_RATE,
            buffersize_msec=100,
            callback_periods=0,
            thread_prio=miniaudio.ThreadPriority.REALTIME,
            app_name="Fractal Explorer",
        )

        gen = self._audioGenerator()
        next(gen)
        self.stream.start(gen)

    # Make sure the sample buffer has the samples from sample_id_start to sample_id_end
    # (remove extras from the head and add missing ones to the tail)
    # If the z escapes or converged to a point, returns the amount of samples that could not be obtained
    def _manageSampleBuffer(self, sample_id_start: int, sample_id_end: int) -> int:
        extras = sample_id_start - self.sample_buffer_first_id
        del self.sample_buffer[:extras]

        max_squared = self.settings.audio_escape_threshold ** 2

        for i in range(sample_id_end - self.sample_id):
            # time.sleep(.1)
            # print(self.frac_z)
            try:
                new_z = self.fractal.py_func(self.frac_z, self.frac_c)
            except ArithmeticError as e:
                logging.warning(f"Audio sample gen failed: {e}")
                return sample_id_end - self.sample_id
            if abs(new_z - self.frac_z) < 1E-6 or new_z.real*new_z.real + new_z.imag*new_z.imag > max_squared:
                self.iter_stopped = True
                break
            self.frac_z = new_z
            self.sample_sum += self.frac_z
            self.sample_buffer.append(self.frac_z)
            self.sample_id += 1

        self.sample_buffer_first_id = sample_id_start

        return sample_id_end - self.sample_id

    def _audioGenerator(self):
        frame_count = yield b""  # generator initialization

        try:
            while True:
                if self.iter_stopped or not self._generating:
                    self._generating = False
                    return

                # gen_start_time = time.perf_counter()

                start_frame = self.frame
                end_frame = self.frame + frame_count
                sample_to_frame_scale = AUDIO_SAMPLE_RATE / self.settings.sample_freq

                sample_id_start = max(floor(start_frame / sample_to_frame_scale) - 3, 0)
                sample_id_end = ceil(end_frame / sample_to_frame_scale) + 3
                skipped_samples = self._manageSampleBuffer(sample_id_start, sample_id_end)
                if skipped_samples > 0:
                    self._generating = False
                    sample_id_end -= skipped_samples
                    end_frame = floor(sample_id_end * sample_to_frame_scale)
                    frame_count = end_frame - self.frame
                    if frame_count < 0:
                        return
                    # Need at least 4 sample points for interpolation to work
                    for i in range(4 - (sample_id_end - sample_id_start)):
                        sample_id_end += 1
                        self.sample_buffer.append(self.frac_z)

                sample_buffer_arr = np.array(self.sample_buffer)
                # Relative to avg midpoint
                mid_point = (self.sample_sum / self.sample_id) if self.sample_id != 0 else 0
                sample_buffer_arr -= mid_point
                sample_buffer_arr_x = np.real(sample_buffer_arr)
                sample_buffer_arr_y = np.imag(sample_buffer_arr)

                # Normalize samples
                sample_max = np.max(np.abs(sample_buffer_arr_x))
                sample_max = max(np.max(np.abs(sample_buffer_arr_y)), sample_max)
                sample_buffer_arr_x /= sample_max
                sample_buffer_arr_y /= sample_max

                sample_ids_arr = np.arange(start=self.sample_buffer_first_id, stop=self.sample_buffer_first_id + len(self.sample_buffer), dtype=np.float32)
                audio_sample_points_arr = np.linspace(start=start_frame / sample_to_frame_scale, stop=(end_frame - 1) / sample_to_frame_scale, num=frame_count)
                interp_kind = self.settings.interpolation.value[1]
                interpolator_x = interp1d(sample_ids_arr, sample_buffer_arr_x, kind=interp_kind, copy=False, fill_value=0.)
                interpolator_y = interp1d(sample_ids_arr, sample_buffer_arr_y, kind=interp_kind, copy=False, fill_value=0.)
                sample_buffer_arr_x = interpolator_x(audio_sample_points_arr)
                sample_buffer_arr_y = interpolator_y(audio_sample_points_arr)

                if self.syn.should_fade:
                    sub_fade_buffer = self.syn.fade_buffer[start_frame : end_frame]
                    if sub_fade_buffer.size < frame_count:
                        self._generating = False
                        frame_count = sub_fade_buffer.size
                        end_frame = self.frame + frame_count
                        sample_buffer_arr_x = sample_buffer_arr_x[:frame_count] * sub_fade_buffer
                        sample_buffer_arr_y = sample_buffer_arr_y[:frame_count] * sub_fade_buffer
                    else:
                        sample_buffer_arr_x = sample_buffer_arr_x * sub_fade_buffer
                        sample_buffer_arr_y = sample_buffer_arr_y * sub_fade_buffer

                data = np.array((sample_buffer_arr_x, sample_buffer_arr_y), dtype=np.float32)
                data = data.flatten("F") * self.amp * self.settings.volume

                self.frame += frame_count
                self.total_time = self.frame / AUDIO_SAMPLE_RATE

                frame_count = yield data
        except (ArithmeticError, ValueError) as e:
            logging.warning(f"Audio synthesize failed: {e}")
            return

    @property
    def playing(self):
        return self.stream.callback_generator is not None

    def stop(self):
        self.stream.close()

class Synthesizer:
    def __init__(self, settings: Settings):
        self.settings = settings

        self.should_fade = None
        self.fade_buffer = None
        self.sources: List[FracAudioSource] = []

        self.updateFadeMode()

    def playFractal(self, fractal: FractalType, point: complex, julia_point: Optional[complex], amp: float):
        source = FracAudioSource(self, fractal, point, julia_point, amp)
        self.sources.append(source)

    def stopSound(self):
        for s in self.sources:
            s.stop()
        self.sources.clear()

    def update(self):
        for s in self.sources[::-1]:
            if not s.playing:
                s.stop()
                self.sources.remove(s)
                continue
        if len(self.sources) > self.settings.max_sources:
            for i in range(len(self.sources) - self.settings.max_sources):
                s = self.sources.pop(0)
                s.stop()

    def updateFadeMode(self):
        self.stopSound()

        self.should_fade = self.settings.audio_fade != 0
        if not self.should_fade:
            self.fade_buffer = None
            return

        def fadeValueGenerator(exp: float):
            t = 0
            while True:
                val = (1 + (t / AUDIO_SAMPLE_RATE)) ** exp
                if val < AUDIO_FADE_CUTOFF:
                    return val
                yield val
                t += 1

        exp = -self.settings.audio_fade
        self.fade_buffer = np.array(tuple(fadeValueGenerator(exp)), dtype=np.float32)

    def terminate(self):
        for s in self.sources:
            s.stop()

if __name__ == "__main__":
    setts = Settings()
    syn = Synthesizer(setts)

    # syn.playFractal(fractals.byName("Mandelbrot"), complex(-1, 0), None, 1.0)
    # syn.playFractal(fractals.byName("Mandelbrot"), complex(0.28, 0.53), None, 1.0)
    syn.playFractal(fractals.byName("Mandelbrot"), complex(-0.0355, 0.8), None, 1.0)

    time.sleep(1)

    syn.terminate()
