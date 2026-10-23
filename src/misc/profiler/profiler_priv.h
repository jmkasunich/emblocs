#ifndef PROFILER_PRIV_H
#define PROFILER_PRIV_H

// this header is included in both C and assembly files, so it
// contains only preprocessor directives.

// state names
#define PROFILER_RESET      0
#define PROFILER_READY      1
#define PROFILER_RUNNING    2
#define PROFILER_FULL       3
#define PROFILER_READOUT    4

// structure member offsets

#define PROFILER_BASE_ADDR_OFFSET        0
#define PROFILER_SHIFT_COUNT_OFFSET      4
#define PROFILER_STATE_OFFSET            5
#define PROFILER_TOTAL_SAMPLES_OFFSET    8
#define PROFILER_BINS_OFFSET             12

#endif // PROFILER_PRIV_H
