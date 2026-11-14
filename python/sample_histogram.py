import math
import sys
from collections import deque
from histogram import Histogram

class SampleHistogram:
    def __init__(self, *, range_min=None, range_max=None,
                          bin_width=None, num_bins=None, window_size=None):
        self.fifo = deque()
        self.window_size = None
        self.set_range(range_min = range_min, range_max = range_max,
                       bin_width = bin_width, num_bins = num_bins)
        self.set_window_size(window_size)

    def set_range(self, *, range_min=None, range_max=None,
                           bin_width=None, num_bins=None):
        """Set the range and clear all counts.
        Give exactly three of the four arguments.  The fourth
        will be calculated, and bin_width or range_max may be
        adjusted so that the range is covered by an integer
        number of bins."""
        given = 0
        value_type = int
        # helper for input validation
        def _check_value(name, value):
            nonlocal value_type, given
            if isinstance(value, float):
                value_type = float
                if not math.isfinite(value):
                    raise ValueError(f"{name} must be finite")
            elif not isinstance(value, int):
                raise TypeError(f"{name} must be an int or float")
            given += 1
        # validate inputs
        if range_min is not None:
            _check_value("range_min", range_min)
        if range_max is not None:
            _check_value("range_max", range_max)
        if bin_width is not None:
            _check_value("bin_width", bin_width)
            if not bin_width > 0:
                raise ValueError("bin_width must be positive")
        if num_bins is not None:
            if not isinstance(num_bins, int):
                raise TypeError("num_bins must be an integer")
            if num_bins < 1:
                raise ValueError("num_bins must be at least 1")
            given += 1
        if range_min is not None and range_max is not None:
            if not range_max > range_min:
                raise ValueError("range_max must be greater than range_min")
        if given != 3:
            raise TypeError("Must provide exactly three of 'range_min', "
                             "'range_max', 'bin_width' and 'num_bins'")
        # compute the three we need (range_min, bin_width, num_bins)
        # from whatever three we were given
        if range_min is None:
            if value_type is int:
                range_min = range_max - bin_width * num_bins + 1
            else:
                # range_min must be inside the range
                range_min = math.nextafter(range_max - bin_width * num_bins, math.inf)
        elif bin_width is None:
            if value_type is int:
                # ceiling division
                span = range_max - range_min + 1
                bin_width = -(-span // num_bins)
            else:
                span = range_max - range_min
                # compute bin width so num_bins fit in the desired span
                bin_width = span / num_bins
        elif num_bins is None:
            if value_type is int:
                # ceiling division
                span = range_max - range_min + 1
                num_bins = -(-span // bin_width)
            else:
                # ceiling division
                span = range_max - range_min
                num_bins = math.ceil(span / bin_width)
                # check for rounding impact
                if (num_bins - 1) * bin_width >= span:
                    num_bins -= 1
                # recompute bin width so num_bins fit in the desired span
                bin_width = span / num_bins
        # perform final validation
        if value_type is float:
            range_min = float(range_min)
            if bin_width < sys.float_info.min:
                raise ValueError(f"bin_width too small: {bin_width}")
            bin_width = float(bin_width)
        self.value_type = value_type
        self.range_min = range_min
        self.bin_width = bin_width
        self.num_bins = num_bins
        # cache derived value
        self.range_max = Histogram.range_max_for(value_type=value_type,
                                                 range_min=range_min,
                                                 bin_width=bin_width,
                                                 num_bins=num_bins)
        self.reset_counts()

    def reset_counts(self):
        self.counts = [0] * self.num_bins
        self.fifo.clear()
        self.above_count = 0
        self.below_count = 0

    def _remove_oldest(self, n=1):
        """Remove the n oldest windowed samples from the fifo and their counters."""
        for _ in range(n):
            old = self.fifo.popleft()
            if old == "below":
                self.below_count -= 1
            elif old == "above":
                self.above_count -= 1
            else:
                self.counts[old] -= 1

    def count_sample(self, value):
        if not isinstance(value, self.value_type):
            raise TypeError("bad sample type")
        if self.value_type is float and not math.isfinite(value):
            # ignore NaN, infinity
            return
        # classify the symbol and update the histogram
        if value < self.range_min:
            self.below_count+= 1
            bin_num = "below"
        elif value > self.range_max:
            self.above_count+= 1
            bin_num = "above"
        else:
            if self.value_type is int:
                bin_num = (value - self.range_min) // self.bin_width
            else:
                bin_num = int((value - self.range_min) / self.bin_width)
                if bin_num >= self.num_bins:
                    bin_num = self.num_bins -1
            self.counts[bin_num] += 1
        # manage windowed histogram data
        if self.window_size is not None:
            self.fifo.append(bin_num)
            if len(self.fifo) > self.window_size:
                self._remove_oldest()

    def set_window_size(self, window_size):
        if window_size is None:
            # switching from windowed mode, discard old samples
            self.window_size = None
            self.fifo.clear()
            return
        if not isinstance(window_size, int):
            raise TypeError("window size must be an integer")
        if window_size < 10:
            raise ValueError("window size must be at least 10")
        if self.window_size is None:
            # switching to windowed mode, must clear old histogram
            self.reset_counts()
        excess = len(self.fifo) - window_size
        if excess > 0:
            # shrinking the window
            self._remove_oldest(excess)
        self.window_size = window_size

    def get_snapshot(self):
        """Creates a Histogram object reflecting the current counts and range.
        The snapshot is a copy taken at the time of the call.  Later samples
        do not change it.
        """
        return Histogram(
            value_type=self.value_type,
            range_min=self.range_min,
            bin_width=self.bin_width,
            counts=self.counts,
            above_count=self.above_count,
            below_count=self.below_count,
        )

    def get_total(self):
        return self.above_count + self.below_count + sum(self.counts)
