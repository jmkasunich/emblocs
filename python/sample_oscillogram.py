from collections import deque
from oscillogram import Oscillogram

class SampleOscillogram:
    def __init__(self):
        self.sample_type = None
        self._fifo = None
        self.sample_interval = None
        self.max_samples = None
        self.samples_since_trigger = None

    def start_acquisition(self, max_samples: int, sample_interval: float):
        if not isinstance(max_samples, int):
            raise TypeError("max_samples must be int")
        if not isinstance(sample_interval, float):
            raise TypeError("sample_interval must be float")
        if max_samples < 1:
            raise ValueError("max_samples must be positive")
        if not sample_interval > 0.0:
            raise ValueError("sample_interval must be postive")
        self.sample_type = None # will be set on first sample
        self.sample_interval = sample_interval
        self.max_samples = max_samples
        self.samples_since_trigger = None
        self._fifo = deque(maxlen = self.max_samples)

    def add_sample(self, value):
        if self.sample_type is None:
            if isinstance(value, int):
                self.sample_type = int
            elif isinstance(value, float):
                self.sample_type = float
            else:
                raise TypeError("Samples must be int or float")
        if not isinstance(value, self.sample_type):
            raise TypeError("bad sample type")
        self._fifo.append(value)
        if self.samples_since_trigger is not None:
            self.samples_since_trigger += 1

    def record_triggered(self):
        if self.samples_since_trigger is None:
            self.samples_since_trigger = 0

    def get_snapshot(self):
        """Creates an Oscillogram object reflecting the current samples.
        The snapshot is a copy taken at the time of the call.  Later samples
        do not change it.  Returns None if no samples have been stored.
        """
        if self.sample_type is None:
            return None
        return Oscillogram(
            sample_type=self.sample_type,
            sample_interval=self.sample_interval,
            samples_since_trigger=self.samples_since_trigger,
            samples=tuple(self._fifo)
        )

    def get_num_samples(self):
        if self._fifo is None:
            return 0
        return len(self._fifo)
