#! /usr/bin/env python3
# linear_axis.py
"""
LinearAxis is a class for mapping values to pixels on a
display.  It includes value-to-pixel and pixel-to-value
mapping methods, and calculates the values for major
and minor divisions or tick-marks using a 1-2-5-10
sequence as is common for oscilloscopes and other
instruments.
"""

import math

def step_125(value: float) -> tuple[float, float]:
    """Returns a tuple of the smallest 1-2-5 major step that is greater
    than or equal to value, and its corresponding minor step.
    """
    if not (math.isfinite(value) and value > 0):
        raise ValueError("value must be finite and positive")
    decade = math.floor(math.log10(value))
    scale = 10.0 ** decade
    for step in (1, 2, 5, 10):
        major = step * scale
        if major >= value:
            if step == 2:
                return (major, major / 4)
            else:
                return (major, major / 5)
    raise AssertionError(f"should never get here, input was {value}")


class LinearAxis:
    def __init__(self, *, value_min: float, value_max: float,
                 pixel_min: int = 0, pixel_max: int = 1,
                 major_spacing: int = 20):
        self._observers = []
        self._value_min = None
        self._value_max = None
        self._pixel_min = 0
        self._pixel_max = 0
        self._major_spacing = None
        self._conv_stale = False
        self._div_steps_stale = False
        self._div_values_stale = False
        # derived and cached fields set by _calculate_xxx():
        #  _p2v_mul, _p2v_add, _v2p_mul, _v2p_add,
        #  _major_step, _minor_step, _major_values, _minor_values
        # validate and save data
        self._set_range(value_min, value_max)
        self._set_location(pixel_min, pixel_max)
        self._set_major_spacing(major_spacing)
        # compute cached data
        self._calculate_conversion()
        self._calculate_div_steps(self._major_spacing)
        self._calculate_div_values()

    @property
    def pixel_min(self):
        return self._pixel_min

    @property
    def pixel_max(self):
        return self._pixel_max

    @property
    def pixel_span(self):
        return self._pixel_max - self._pixel_min

    @property
    def value_min(self):
        return self._value_min

    @property
    def value_max(self):
        return self._value_max

    @property
    def value_span(self):
        return self._value_max - self._value_min

    @property
    def center(self) -> float:
        return self._value_min + self.value_span / 2

    @property
    def major_step(self):
        return self._major_step

    @property
    def minor_step(self):
        return self._minor_step


    def p2v(self, pixel: int) -> float:
        """ Takes a pixel, returns the corresponding value on the axis
        """
        return pixel * self._p2v_mul + self._p2v_add

    def dp2dv(self, pixels: int) -> float:
        """ Takes a delta in pixels, returns the corresponding delta value
        """
        return pixels * self._p2v_mul

    def v2p(self, value: float) -> int:
        """ Takes a value, returns the nearest integer pixel on the axis
        Use for drawing, mouse hit testing, etc.
        """
        return round(value * self._v2p_mul + self._v2p_add)

    def v2p_f(self, value: float) -> float:
        """ Takes a value, returns the corresponding pixel as a float
        Use where exact round-trip conversions are needed.
        """
        return value * self._v2p_mul + self._v2p_add

    def get_major_values(self) -> list[float]:
        """ Returns a list of values for major ticks and/or labels
        Computed on demand, then cached
        """
        if self._div_values_stale:
            self._calculate_div_values()
        return self._major_values

    def get_minor_values(self) -> list[float]:
        """ Returns a list of values for minor ticks
        Computed on demand, then cached
        """
        if self._div_values_stale:
            self._calculate_div_values()
        return self._minor_values

    def _dirty_conv(self):
        if not self._conv_stale:
            self._conv_stale = True

    def _dirty_divs(self):
        if not self._div_steps_stale:
            self._div_steps_stale = True
        if not self._div_values_stale:
            self._div_values_stale = True

    def add_observer(self, callback):
        self._observers.append(callback)

    def _refresh(self):
        """
        Calculates conversion and/or div steps if dirty.
        Does not calculate div values; they are done on demand.
        Calls observers, if any, after stale data is updated.
        """
        stale = ( self._conv_stale or self._div_steps_stale )
        # refresh cached data
        if self._conv_stale:
            self._calculate_conversion()
        if self._div_steps_stale:
            self._calculate_div_steps(self._major_spacing)
        if stale:
            for observer in self._observers:
                observer()

    def _set_range(self, value_min: float, value_max: float):
        """ helper for set_range()
        Validates and saves data, but does not drive updates.
        Can be called from __init__() when object is not fully ready.
        """
        if not ( isinstance(value_min, float) and
                 isinstance(value_max, float) ):
            raise TypeError("'value_min' and 'value_max' must be float")
        if not ( math.isfinite(value_min) and
                 math.isfinite(value_max) ):
            raise ValueError("'value_min' and 'value_max' must be finite")
        value_span = value_max - value_min
        if not value_span > 0:
            raise ValueError("value_max must be greater than value_min")
        # require at least 16-bits of resolution within the span
        min_span = 65536 * math.ulp(max(abs(value_min), abs(value_max)))
        if not value_span > min_span:
            raise ValueError("span too small for reliable arithmetic")
        # inputs are valid, check for changes
        if ( value_min != self._value_min ) or \
           ( value_max != self._value_max ):
            self._dirty_conv()
            self._dirty_divs()
        # save new data
        self._value_min = value_min
        self._value_max = value_max

    def set_range(self, value_min: float, value_max: float):
        """ Determines the range of values that are mapped to an axis.
        value_min must be less than value_max; both must be float
        """
        # validate and store data
        self._set_range(value_min, value_max)
        self._refresh()

    def _set_location(self, pixel_min: int, pixel_max: int):
        """ helper for set_location()
        Validates and saves data, but does not drive updates.
        Can be called from __init__() when object is not fully ready.
        """
        if not isinstance(pixel_min, int) or \
           not isinstance(pixel_max, int):
            raise TypeError("pixel_min and pixel_max must be int")
        pixel_span = pixel_max - pixel_min
        if pixel_span == 0:
            raise ValueError("pixel_min and pixel_max must be different")
        # inputs are valid, check for changes
        if pixel_span != self.pixel_span:
            self._dirty_divs()
        if ( pixel_min != self._pixel_min ) or \
           ( pixel_max != self._pixel_max ):
            self._dirty_conv()
        # save new data
        self._pixel_min = pixel_min
        self._pixel_max = pixel_max

    def set_location(self, pixel_min: int, pixel_max: int):
        """ Determines on-screen location of an axis.
        pixel_min and pixel_max must not be the same; both must be ints.
        """
        # validate and store data
        self._set_location(pixel_min, pixel_max)
        self._refresh()

    def _set_major_spacing(self, major_spacing: int):
        """ helper for set_major_spacing()
        Validates and saves data, but does not drive updates.
        Can be called from __init__() when object is not fully ready.
        """
        if not isinstance(major_spacing, int):
            raise TypeError("major_spacing must be int")
        if major_spacing < 1:
            raise ValueError("major_spacing must be at least 1")
        # inputs are valid, check for changes
        if major_spacing != self._major_spacing:
            self._dirty_divs()
        # save new data
        self._major_spacing = major_spacing

    def set_major_spacing(self, major_spacing: int):
        """ Sets minimum spacing between major ticks in pixels
        """
        # validate and store data
        self._set_major_spacing(major_spacing)
        self._refresh()

    def _calculate_conversion(self):
        """ Calculate coefficients used to convert from value to pixel
        space and back.
        """
        self._p2v_mul = self.value_span / self.pixel_span
        self._p2v_add = self._value_min - (self._pixel_min * self._p2v_mul)
        self._v2p_mul = self.pixel_span / self.value_span
        self._v2p_add = self._pixel_min - (self._value_min * self._v2p_mul)
        self._conv_stale = False

    def _calculate_div_steps(self, major_spacing: int):
        """Choose "nice" tick spacings for an axis.
        'major_spacing' is the minimum distance in pixels between major ticks.
    
        Sets self._major_step and self._minor_step, which are used by
        _calculate_div_values() to determine where ticks and/or labels
        should go for a "nice" display.
        """
        max_labels = max(abs(self.pixel_span) // major_spacing, 1)
        min_major_step = self.value_span / max_labels
        self._major_step, self._minor_step = step_125(min_major_step)
        self._div_values_stale = True
        self._div_steps_stale = False

    def _calculate_div_values(self):
        """Compute tick/label positions for an axis.
        Generates self._major_values and self._minor_values.
        '_major_values' is a list of major tick/label values,
        '_minor_values' is a list of minor tick values; either
        list may be empty.  Tick values are floats.
        """
        major_list = []
        minor_list = []
        major_index = math.ceil(self._value_min / self._major_step)
        major = major_index * self._major_step
        while major <= self._value_max:
            major_list.append(major)
            major_index += 1
            major = major_index * self._major_step
        major_minor_ratio = round(self._major_step / self._minor_step)
        minor_index = math.ceil(self._value_min / self._minor_step)
        minor = minor_index * self._minor_step
        while minor <= self._value_max:
            if minor_index % major_minor_ratio != 0:
                minor_list.append(minor)
            minor_index += 1
            minor = minor_index * self._minor_step
        self._major_values = major_list
        self._minor_values = minor_list
        self._div_values_stale = False

    def zoom(self, factor: float, around: float,
                   min_span=None, max_span=None):
        """ Zoom the axis by 'factor', centered on 'around'.
        If 'factor' is < 1.0, zooms in, > 1.0 zooms out.
        Overall span is clamped by 'min_span' and 'max_span'.
        """
        factor = float(factor)
        around = float(around)
        if not ( math.isfinite(factor) and factor > 0.0 ):
            raise ValueError("zoom factor must be positive and finite")
        if not math.isfinite(around):
            raise ValueError("around must be finite")
        new_span = self.value_span * factor
        if min_span is not None:
            new_span = max(new_span, min_span)
        if max_span is not None:
            new_span = min(new_span, max_span)
        factor = new_span / self.value_span
        new_min = around + factor * (self._value_min - around)
        new_max = around + factor * (self._value_max - around)
        try:
            self.set_range(new_min, new_max)
        except ValueError:
            # tried to zoom in too far?
            pass

    def pan(self, amount, min_value=None, max_value=None):
        """ Pan the X axis by 'amount'.
        If 'amount' is positive, pan right; if negative, left.
        Overall range is clamped by min_value and max_value.
        """
        if not math.isfinite(amount):
            raise ValueError("amount must be finite")
        if amount > 0 and max_value is not None:
            amount = min(amount, max_value - self._value_max)
        elif amount < 0 and min_value is not None:
            amount = max(amount, min_value - self._value_min)
        new_min = self._value_min + amount
        new_max = self._value_max + amount
        try:
            self.set_range(new_min, new_max)
        except ValueError:
            # tried to pan too far?
            pass
