#ifndef PROFILER_PRIV_H
#define PROFILER_PRIV_H

// this header is included in both C and assembly files, so it
// contains only preprocessor directives.

// state names
#define PROFILER_READY      0
#define PROFILER_RUNNING    1
#define PROFILER_FULL       2

// structure member offsets

#define PROFILER_STATE_OFFSET            4
#define PROFILER_SHIFT_COUNT_OFFSET      5
#define PROFILER_PACKED_VALS_OFFSET      8
#define PROFILER_MAGIC_NUMBER_OFFSET     12
#define PROFILER_ABOVE_COUNT_OFFSET      16
#define PROFILER_BELOW_COUNT_OFFSET      20
#define PROFILER_BINS_OFFSET             24

#endif // PROFILER_PRIV_H
