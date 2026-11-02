#! /usr/bin/env python3
# histogram.py - immutable histogram data

from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Optional, Sequence, Union

HistogramValue = Union[int, float]

@dataclass(frozen=True)
class Histogram:
    """A snapshot of a histogram: configuration plus bin counts.

    Instances are immutable.  Counts are copied on construction, so later
    changes to the source never affect a Histogram.
    """
    value_type: type   # int or float
    range_min: HistogramValue
    range_max: HistogramValue
    bin_width: HistogramValue
    counts: Sequence[int]          # one int per bin
    above_count: int = 0
    below_count: int = 0
    counter_width: Optional[int] = None   # None for host-built histograms

    def __post_init__(self):
        if self.value_type not in ( int, float ):
            raise TypeError(f"value_type must be int or float, not {self.value_type!r}")
        for name in ("range_min", "range_max", "bin_width"):
            if not isinstance(getattr(self, name), self.value_type):
                raise TypeError(f"{name} must be {self.value_type.__name__}")
        if not isinstance(self.counts, tuple):
            # frozen dataclass: use object.__setattr__ to normalize
            object.__setattr__(self, "counts", tuple(self.counts))
        if len(self.counts) == 0:
            raise ValueError("histogram must have at least one bin")
        if not self.bin_width > 0:
            raise ValueError("bin width must be positive")
        if self.counter_width is not None and self.counter_width not in (1, 2, 4):
            raise ValueError("counter width must be 1, 2, or 4 bytes")
        if self.above_count < 0 or self.below_count < 0:
            raise ValueError("statistics counts must not be negative")

    # ---- counts ----------------------------------------------------------

    @property
    def num_bins(self) -> int:
        return len(self.counts)

    def get_bin_count(self, bin_num: int) -> int:
        """Count in one bin, or 0 if bin_num is out of range (matches C)."""
        if 0 <= bin_num < len(self.counts):
            return self.counts[bin_num]
        return 0

    def get_bins(self) -> tuple:
        """All bin counts.  Python-only convenience; the C API has no equivalent."""
        return self.counts

    def get_total(self) -> int:
        """Exact sum of all bins plus above and below.  Python ints don't wrap."""
        return sum(self.counts) + self.above_count + self.below_count

    # ---- geometry --------------------------------------------------------

    def get_bin_edges(self) -> list:
        """num_bins + 1 edges: start of each bin, then the end of the last bin."""
        edges = [self.range_min + i * self.bin_width for i in range(self.num_bins)]
        edges.append(self.range_max)
        return edges

    def get_bin_centers(self) -> list:
        """Center of each bin.  Centers are never needed by the C API."""
        half = self.bin_width / 2
        return [self.range_min + half + i * self.bin_width for i in range(self.num_bins)]
