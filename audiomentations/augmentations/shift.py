import random
from typing import Union

import numpy as np

from audiomentations.core.transforms_interface import BaseWaveformTransform

# 0.00025 seconds corresponds to 2 samples at 8000 Hz
DURATION_EPSILON = 0.00025


class Shift(BaseWaveformTransform):
    """
    Shift the samples forwards or backwards, with or without rollover
    """

    supports_multichannel = True

    def __init__(
        self,
        min_shift: Union[float, int] = -0.5,
        max_shift: Union[float, int] = 0.5,
        shift_unit: str = "fraction",
        rollover: bool = True,
        fade_duration: float = 0.005,
        p: float = 0.5,
    ):
        """
        :param min_shift: minimum amount of shifting in time. See also shift_unit.
        :param max_shift: maximum amount of shifting in time. See also shift_unit.
        :param shift_unit: Defines the unit of the value of min_shift and max_shift.
            "fraction": Fraction of the total sound length
            "samples": Number of audio samples
            "seconds": Number of seconds
        :param rollover: When set to True, samples that roll beyond the first or last position
            are re-introduced at the last or first. When set to False, samples that roll beyond
            the first or last position are discarded. In other words, rollover=False results in
            an empty space (with zeroes).
        :param fade_duration: If you set this to a positive number (in seconds), there
            will be a fade in and/or out at the "stitch" (that was the start or the end
            of the audio before the shift). This can smooth out an unwanted abrupt
            change between two consecutive samples (which sounds like a
            transient/click/pop). This parameter denotes the duration of the fade in
            seconds. To disable the fading feature, set this parameter to 0.0.
        :param p: The probability of applying this transform
        """
        super().__init__(p)

        if min_shift > max_shift:
            raise ValueError("min_shift must not be greater than max_shift")
        if shift_unit not in ("fraction", "samples", "seconds"):
            raise ValueError('shift_unit must be "fraction", "samples" or "seconds"')
        if shift_unit == "fraction":
            if min_shift < -1:
                raise ValueError(
                    'min_shift must be >= -1 when shift_unit is "fraction"'
                )
            if max_shift > 1:
                raise ValueError('max_shift must be <= 1 when shift_unit is "fraction"')

        if fade_duration == 0.0:
            self.fade = False
        elif fade_duration < 0.0:
            raise ValueError("fade_duration must not be negative")
        elif fade_duration < DURATION_EPSILON:
            raise ValueError(
                "When fade_duration is set to a positive number, it must be >="
                f" {DURATION_EPSILON}"
            )
        else:
            self.fade = True

        self.min_shift = min_shift
        self.max_shift = max_shift
        self.shift_unit = shift_unit
        self.rollover = rollover
        self.fade_duration = fade_duration

    def randomize_parameters(self, samples: np.ndarray, sample_rate: int):
        super().randomize_parameters(samples, sample_rate)
        if self.parameters["should_apply"]:
            if self.shift_unit == "samples":
                min_shift_in_samples = self.min_shift
                max_shift_in_samples = self.max_shift
            elif self.shift_unit == "fraction":
                min_shift_in_samples = int(round(self.min_shift * samples.shape[-1]))
                max_shift_in_samples = int(round(self.max_shift * samples.shape[-1]))
            elif self.shift_unit == "seconds":
                min_shift_in_samples = int(round(self.min_shift * sample_rate))
                max_shift_in_samples = int(round(self.max_shift * sample_rate))
            else:
                raise ValueError("invalid shift_unit")

            self.parameters["num_samples_to_shift"] = random.randint(
                min_shift_in_samples, max_shift_in_samples
            )

    def apply(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        num_places_to_shift = self.parameters["num_samples_to_shift"]
        shifted_samples = np.roll(samples, num_places_to_shift, axis=-1)

        if not self.rollover:
            if num_places_to_shift > 0:
                shifted_samples[..., :num_places_to_shift] = 0.0
            elif num_places_to_shift < 0:
                shifted_samples[..., num_places_to_shift:] = 0.0

        if self.fade:
            fade_length = int(sample_rate * self.fade_duration)

            # TODO: Use smooth fade!
            fade_in = np.linspace(0, 1, num=fade_length)
            fade_out = np.linspace(1, 0, num=fade_length)

            if num_places_to_shift > 0:
                fade_in_start = num_places_to_shift
                fade_in_end = min(
                    num_places_to_shift + fade_length, shifted_samples.shape[-1]
                )
                fade_in_length = fade_in_end - fade_in_start

                shifted_samples[
                    ...,
                    fade_in_start:fade_in_end,
                ] *= fade_in[:fade_in_length]

                if self.rollover:
                    fade_out_start = max(num_places_to_shift - fade_length, 0)
                    fade_out_end = num_places_to_shift
                    fade_out_length = fade_out_end - fade_out_start

                    shifted_samples[..., fade_out_start:fade_out_end] *= fade_out[
                        -fade_out_length:
                    ]

            elif num_places_to_shift < 0:
                positive_num_places_to_shift = (
                    shifted_samples.shape[-1] + num_places_to_shift
                )

                fade_out_start = max(positive_num_places_to_shift - fade_length, 0)
                fade_out_end = positive_num_places_to_shift
                fade_out_length = fade_out_end - fade_out_start

                shifted_samples[..., fade_out_start:fade_out_end] *= fade_out[
                    -fade_out_length:
                ]

                if self.rollover:
                    fade_in_start = positive_num_places_to_shift
                    fade_in_end = min(
                        positive_num_places_to_shift + fade_length,
                        shifted_samples.shape[-1],
                    )
                    fade_in_length = fade_in_end - fade_in_start
                    shifted_samples[
                        ...,
                        fade_in_start:fade_in_end,
                    ] *= fade_in[:fade_in_length]

        return shifted_samples
