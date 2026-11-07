#! /usr/bin/env python3
# oscillgram.py - immutable oscillogram data

from dataclasses import dataclass
from typing import Optional, Sequence, Union


OscillogramValue = Union[int, float]

@dataclass(frozen=True)
class Oscillogram:
    """A snapshot of an Oscillogram: configuration plus sample values.

    Instances are immutable.  Sample values are copied on construction,
    so later changes to the source never affect an Oscillogram.  Sample
    values can be int or float.  Time (including sample interval) is
    always passed and stored as float.
    """
    sample_type: type   # int or float
    sample_interval: float
    samples: Sequence[OscillogramValue]    # one int or float per sample
    samples_since_trigger: Optional[int] = None

    def __post_init__(self):
        if self.sample_type not in ( int, float ):
            raise TypeError(f"sample_type must be int or float, not {self.sample_type!r}")
        if not isinstance(self.sample_interval, float):
            raise TypeError("sample_interval must be float")
        if not self.sample_interval > 0:
            raise ValueError("sample interval must be positive")
        if not isinstance(self.samples, tuple):
            # frozen dataclass: use object.__setattr__ to normalize
            object.__setattr__(self, "samples", tuple(self.samples))
        if len(self.samples) == 0:
            raise ValueError("oscillogram must have at least one sample")
        if not isinstance(self.samples[0], self.sample_type ):
            raise TypeError(f"samples must be {self.sample_type.__name__}")
        if self.samples_since_trigger is not None and \
           not isinstance(self.samples_since_trigger, int):
            raise TypeError("samples_since_trigger must be int")

    @property
    def num_samples(self) -> int:
        return len(self.samples)

    def get_sample(self, sample_num: int) -> \
                   tuple[Optional[float], Optional[OscillogramValue]]:
        """Time and Value of a sample, None if sample_num is out of range.
        Time zero is the trigger sample, or the newest sample if untriggered.
        """
        if 0 <= sample_num < len(self.samples):
            num = sample_num - ( self.num_samples - 1 )
            if self.samples_since_trigger is not None:
                num += self.samples_since_trigger
            return (self.sample_interval * num, self.samples[sample_num])
        return (None, None)

    def get_sample_value(self, sample_num: int) -> Optional[OscillogramValue]:
        """Value of a sample, None if sample_num is out of range"""
        return self.get_sample(sample_num)[1]

    def get_sample_time(self, sample_num: int) -> Optional[float]:
        """Time of a sample, None if sample_num is out of range"""
        return self.get_sample(sample_num)[0]

    def get_samples(self) -> tuple:
        """All sample values.  Python-only convenience; the C API has no equivalent."""
        return self.samples
