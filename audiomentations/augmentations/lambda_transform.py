from typing import Callable

from audiomentations.core.transforms_interface import BaseWaveformTransform


class Lambda(BaseWaveformTransform):
    """
    Apply any choice of operation over the signal at user discretion.
    """

    supports_multichannel = True

    def __init__(self, transform: Callable, p: float = 0.5, **kwargs):
        """
        :param transform: A callable to be applied over samples. It should input
            samples (ndarray), sample_rate (int) and optionally some user-defined
            keyword arguments.
        :param p: The probability of applying this transform
        :param **kwargs: Any extra keyword arguments to be passed to the transform.
        """
        super().__init__(p=p)
        self.transform = transform
        self.kwargs = kwargs

    def apply(self, samples, sample_rate):
        return self.transform(samples, sample_rate, **self.kwargs)
