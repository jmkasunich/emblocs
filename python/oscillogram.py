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
    values can be int or float.  Times are always passed and stored as
    floats.
    """
    value_type: type   # int or float
    time_min: float
    sample_interval: float
    samples: Sequence[OscillogramValue]       # one int or float per sample

    def __post_init__(self):
        if self.value_type not in ( int, float ):
            raise TypeError(f"value_type must be int or float, not {self.value_type!r}")
        for name in ("time_min", "sample_interval"):
            if not isinstance(getattr(self, name), float):
                raise TypeError(f"{name} must be float")
        if not isinstance(self.samples, tuple):
            # frozen dataclass: use object.__setattr__ to normalize
            object.__setattr__(self, "samples", tuple(self.samples))
        if len(self.samples) == 0:
            raise ValueError("oscillogram must have at least one sample")
        if not isinstance(self.samples[0], self.value_type ):
            raise TypeError(f"samples must be {self.value_type.__name__}")
        if not self.sample_interval > 0:
            raise ValueError("sample interval must be positive")

    @property
    def time_max(self) -> float:
        """ Time of last sample """
        return self.time_min + self.sample_interval * (self.num_samples-1)

    @property
    def num_samples(self) -> int:
        return len(self.samples)

    def get_sample(self, sample_num: int) -> \
                   tuple[Optional[float], Optional[OscillogramValue]]:
        """Time and Value of a sample, None if sample_num is out of range"""
        if 0 <= sample_num < len(self.samples):
            return (self.time_min + self.sample_interval * sample_num,
                    self.samples[sample_num])
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
