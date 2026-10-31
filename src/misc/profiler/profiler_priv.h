#ifndef PROFILER_PRIV_H
#define PROFILER_PRIV_H

/* this header is included in both C and assembly files,
   so it contains only preprocessor directives. */

/* state name - this must match histogram_state_t enum,
   and is checked by a static assert in profiler.c */
#define PROFILER_STATE_FULL       2

/* structure member offsets - these must match profile_t
   and are checked by static asserts in profiler.c */
#define PROFILER_STATE_OFFSET            2
#define PROFILER_SHIFT_COUNT_OFFSET      40
#define PROFILER_PACKED_VALS_OFFSET      44
#define PROFILER_MAGIC_NUMBER_OFFSET     48
#define PROFILER_ABOVE_COUNT_OFFSET      24
#define PROFILER_BELOW_COUNT_OFFSET      28
#define PROFILER_BINS_OFFSET             52

#endif /* PROFILER_PRIV_H */
