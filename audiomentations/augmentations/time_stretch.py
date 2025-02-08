import random

import librosa
import numpy as np
from numpy.typing import NDArray
import python_stretch

from audiomentations.core.transforms_interface import BaseWaveformTransform


class TimeStretch(BaseWaveformTransform):
    """Time stretch the signal without changing the pitch"""

    supports_multichannel = True

    def __init__(
        self,
        min_rate: float = 0.8,
        max_rate: float = 1.25,
        leave_length_unchanged: bool = True,
        method: str = "signalsmith_stretch",
        p: float = 0.5,
    ):
        """
        :param min_rate: Minimum rate of change of total duration of the signal. A rate below 1 means the audio is slowed down.
        :param max_rate: Maximum rate of change of total duration of the signal. A rate greater than 1 means the audio is sped up.
        :param leave_length_unchanged: The rate changes the duration and effects the samples.
            This flag is used to keep the total length of the generated output to be same as that of the input signal.
        :param method: "librosa_phase_vocoder" or "signalsmith_stretch"
        :param p: The probability of applying this transform.
        """
        super().__init__(p)
        if min_rate < 0.1:
            raise ValueError("min_rate must be >= 0.1")
        if max_rate > 10:
            raise ValueError("max_rate must be <= 10")
        if min_rate > max_rate:
            raise ValueError("min_rate must not be greater than max_rate")

        self.min_rate = min_rate
        self.max_rate = max_rate
        self.leave_length_unchanged = leave_length_unchanged

        if method not in ("librosa_phase_vocoder", "signalsmith_stretch"):
            raise ValueError(
                'method must be set to either "librosa_phase_vocoder" or "signalsmith_stretch"'
            )
        self.method = method

    def randomize_parameters(self, samples: NDArray[np.float32], sample_rate: int):
        super().randomize_parameters(samples, sample_rate)
        if self.parameters["should_apply"]:
            """
            If rate > 1, then the signal is sped up.
            If rate < 1, then the signal is slowed down.
            """
            self.parameters["rate"] = random.uniform(self.min_rate, self.max_rate)

    def apply(self, samples: NDArray[np.float32], sample_rate: int) -> NDArray[np.float32]:
        original_shape = samples.shape
        if self.method == "signalsmith_stretch":
            original_ndim = samples.ndim
            if original_ndim == 1:
                samples = samples[np.newaxis, :]

            stretch = python_stretch.Signalsmith.Stretch()
            stretch.preset(samples.shape[0], sample_rate)
            stretch.setTimeFactor(self.parameters["rate"])
            time_stretched_samples = stretch.process(samples)

            if time_stretched_samples.ndim > original_ndim:
                time_stretched_samples = time_stretched_samples[0]

        else:  # method == "librosa_phase_vocoder"
            try:
                time_stretched_samples = librosa.effects.time_stretch(
                    samples, rate=self.parameters["rate"]
                )
            except librosa.util.exceptions.ParameterError:
                # In librosa<0.9.0 time_stretch doesn't natively support multichannel audio.
                # Here we use a workaround that simply loops over the channels instead.
                # TODO: Remove this workaround when we remove support for librosa<0.9.0
                time_stretched_channels = []
                for i in range(samples.shape[0]):
                    time_stretched_samples_ch = librosa.effects.time_stretch(
                        samples[i], rate=self.parameters["rate"]
                    )
                    time_stretched_channels.append(time_stretched_samples_ch)
                time_stretched_samples = np.array(
                    time_stretched_channels, dtype=samples.dtype
                )

        if self.leave_length_unchanged:
            # Apply zero padding if the time stretched audio is not long enough to fill the
            # whole space, or crop the time stretched audio if it ended up too long.
            padded_samples = np.zeros(shape=original_shape, dtype=samples.dtype)
            window = time_stretched_samples[..., : samples.shape[-1]]
            actual_window_length = window.shape[-1]
            padded_samples[..., :actual_window_length] = window
            time_stretched_samples = padded_samples

        return time_stretched_samples
