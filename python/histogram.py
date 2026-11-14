#! /usr/bin/env python3
# histogram.py - immutable histogram data

from dataclasses import dataclass, field
from typing import Optional, Sequence, Union
import math

HistogramValue = Union[int, float]

@dataclass(frozen=True, kw_only=True)
class Histogram:
    """A snapshot of a histogram: configuration plus bin counts.

    Instances are immutable.  Counts are copied on construction, so later
    changes to the source never affect a Histogram.
    """
    value_type: type   # int or float
    range_min: HistogramValue
    bin_width: HistogramValue
    range_max: HistogramValue = field(init=False)
    counts: Sequence[int]          # one int per bin
    above_count: int = 0
    below_count: int = 0
    counter_width: Optional[int] = None   # None for host-built histograms

    def __post_init__(self):
        if not isinstance(self.counts, tuple):
            # frozen dataclass: use object.__setattr__ to normalize
            object.__setattr__(self, "counts", tuple(self.counts))
        if len(self.counts) == 0:
            raise ValueError("histogram must have at least one bin")
        # only typecheck first count to keep things O(1)
        if not isinstance(self.counts[0], int ):
            raise TypeError("counts must be integers")
        range_max = Histogram.range_max_for(value_type= self.value_type,
                                            range_min= self.range_min,
                                            bin_width= self.bin_width,
                                            num_bins= len(self.counts))
        object.__setattr__(self, "range_max", range_max)
        if self.counter_width is not None and self.counter_width not in (1, 2, 4):
            raise ValueError("counter width must be 1, 2, or 4 bytes")
        if self.above_count < 0 or self.below_count < 0:
            raise ValueError("statistics counts must not be negative")

    @staticmethod
    def range_max_for(*, value_type, range_min, bin_width, num_bins):
        """ range_max is derived; this method provides a consistent way
        of calculating it """
        if value_type not in (int, float):
            raise TypeError(f"value_type must be int or float, not {value_type!r}")
        if not isinstance(range_min, value_type):
            raise TypeError(f"range_min must be {value_type.__name__}")
        if not isinstance(bin_width, value_type):
            raise TypeError(f"bin_width must be {value_type.__name__}")
        if not isinstance(num_bins, int) or num_bins <= 0:
            raise ValueError("num_bins must be a positive integer")
        if value_type is float:
            if not math.isfinite(range_min):
                raise ValueError("range_min must be finite")
            if not (math.isfinite(bin_width) and bin_width > 0):
                raise ValueError("bin_width must be finite and positive")
            range_max = range_min + num_bins * bin_width
            if not math.isfinite(range_max):
                raise ValueError("range overflows")
            return math.nextafter(range_max, -math.inf)
        else:
            if not bin_width > 0:
                raise ValueError("bin_width must be positive")
            return range_min + num_bins * bin_width - 1

    @property
    def num_bins(self) -> int:
        return len(self.counts)

    def get_total(self) -> int:
        """ Exact sum of all bins plus above and below. """
        return sum(self.counts) + self.above_count + self.below_count

    def find_bin(self, value) -> Optional[int]:
        """ Return the number of the bin that contains 'value', or
        None if value is outside of the histogram's range. """
        if self.range_min <= value <= self.range_max:
            if self.value_type is int:
                bin_num = (value - self.range_min) // self.bin_width
            else:
                bin_num = math.floor((value - self.range_min) / self.bin_width)
            return min(bin_num, len(self.counts)-1)
        return None

    def get_bin_count(self, bin_num: int) -> int:
        """ Return the count in the specified bin. """
        if not 0 <= bin_num < len(self.counts):
            raise IndexError(f"Invalid bin number {bin_num}")
        return self.counts[bin_num]

    def get_bin_edges(self, bin_num: int) -> tuple[HistogramValue, HistogramValue]:
        """ Return a tuple containing the edges of the specified bin. """
        if not 0 <= bin_num < len(self.counts):
            raise IndexError(f"Invalid bin number {bin_num}")
        lower = self.range_min + bin_num * self.bin_width
        if self.value_type is int:
            upper = lower + self.bin_width - 1
        else:
            upper = math.nextafter(lower + self.bin_width, -math.inf)
        return (lower, upper)

    def get_bin(self, bin_num: int) -> tuple[HistogramValue, HistogramValue, int]:
        """ Return a 3-tuple containing the edges of the specified bin
        followed by the count for that bin. """
        return (*self.get_bin_edges(bin_num), self.counts[bin_num])

    def get_bin_center(self, bin_num: int) -> HistogramValue:
        """ Return the center of the specified bin """
        if not 0 <= bin_num < len(self.counts):
            raise IndexError(f"Invalid bin number {bin_num}")
        if self.value_type is int:
            half = self.bin_width // 2
        else:
            half = self.bin_width / 2.0
        return self.range_min + self.bin_width * bin_num + half

    # not sure if these will ever be needed

    # def get_all_counts(self) -> tuple:
    #     """ Return all bin counts """
    #     return self.counts

    # def get_all_edges(self) -> list:
    #     """ Return num_bins + 1 edges: start of each bin, then the
    #     end of the last bin. """
    #     edges = [self.range_min + i * self.bin_width for i in range(self.num_bins)]
    #     edges.append(self.range_max)
    #     return edges

    # def get_all_centers(self) -> list:
    #     """ Return centers of all bins """
    #     half = self.bin_width / 2
    #     return [self.range_min + half + i * self.bin_width for i in range(self.num_bins)]
