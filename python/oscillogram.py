#! /usr/bin/env python3
# oscillogram.py - immutable oscillogram data

from dataclasses import dataclass
from typing import Optional, Sequence, Union
import math


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
    samples_since_trigger: int = 0
    triggered: bool = False

    def __post_init__(self):
        if self.sample_type not in ( int, float ):
            raise TypeError(f"sample_type must be int or float, not {self.sample_type!r}")
        if not isinstance(self.sample_interval, float):
            raise TypeError("sample_interval must be float")
        if not (math.isfinite(self.sample_interval) and self.sample_interval > 0):
            raise ValueError("sample interval must be positive")
        if not isinstance(self.samples, tuple):
            # frozen dataclass: use object.__setattr__ to normalize
            object.__setattr__(self, "samples", tuple(self.samples))
        if len(self.samples) == 0:
            raise ValueError("oscillogram must have at least one sample")
        # only typecheck first sample to keep things O(1)
        if not isinstance(self.samples[0], self.sample_type ):
            raise TypeError(f"samples must be {self.sample_type.__name__}")
        if not isinstance(self.samples_since_trigger, int):
            raise TypeError("samples_since_trigger must be int")
        if self.samples_since_trigger < 0:
            raise ValueError("samples_since_trigger must not be negative")
        if not self.triggered and self.samples_since_trigger > 0:
            raise ValueError("samples_since_trigger must be zero when not triggered")

    @property
    def num_samples(self) -> int:
        return len(self.samples)

    def find_sample(self, time: float) -> Optional[int]:
        """ Return the number of the sample corresponding to 'time',
        which is in seconds since trigger, or None if time is outside
        of the oscillogram's range.
        """
        max_sample_num = len(self.samples) - 1
        offset = time / self.sample_interval
        if not math.isfinite(offset):
            return None
        sample_num = max_sample_num - self.samples_since_trigger + round(offset)
        if 0 <= sample_num <= max_sample_num:
            return sample_num
        return None

    def get_sample_value(self, sample_num: int) -> OscillogramValue:
        """ Return the value of the specified sample. """
        if not 0 <= sample_num < len(self.samples):
            raise IndexError(f"Invalid sample number {sample_num}")
        return self.samples[sample_num]

    def get_sample_time(self, sample_num: int) -> float:
        """ Return the time of the specified sample, in seconds
        since trigger.  When untriggered, time is relative to the
        most recent sample. """
        max_sample_num = len(self.samples) - 1
        if not 0 <= sample_num <= max_sample_num:
            raise IndexError(f"Invalid sample number {sample_num}")
        trig_sample_num = max_sample_num - self.samples_since_trigger
        return self.sample_interval * ( sample_num - trig_sample_num)

    def get_sample(self, sample_num: int) -> tuple[float, OscillogramValue]:
        """ Time and Value of the specified sample """
        return (self.get_sample_time(sample_num), self.samples[sample_num])

