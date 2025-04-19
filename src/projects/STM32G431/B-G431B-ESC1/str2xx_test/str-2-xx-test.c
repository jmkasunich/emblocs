#include "platform_g431.h"

#include "printing.h"
#include "str_to_xx.h"
#include <float.h>
#include <math.h>
#include <assert.h>

/* each set of test cases is terminated by a case with a NULL string */

typedef struct test_bool_s {
    char *string;
    bool accept;
    bool result;
} test_bool_t;

test_bool_t const bool_tests[] = {
    { "0", 1, 0 },
    { "1", 1, 1 },
    { "a", 0, 0 },
    { "", 0, 0 },
    { " 1", 0, 0 },
    { "1 ", 0, 0 },
    { "3", 0, 0 },
    { NULL, 0, 0 }
};

typedef struct test_u32_s {
    char *string;
    bool accept;
    uint32_t result;
} test_u32_t;

test_u32_t const u32_tests[] = {
    { "0", 1, 0 },
    { "-0", 0, 0 },
    { "1", 1, 1 },
    { "11", 1, 11 },
    { "270", 1, 270 },
    { "10", 1, 10 },
    { "100", 1, 100 },
    { "1000", 1, 1000 },
    { "10000", 1, 10000 },
    { "100000", 1, 100000 },
    { "1000000", 1, 1000000 },
    { "10000000", 1, 10000000 },
    { "100000000", 1, 100000000 },
    { "1000000000", 1, 1000000000 },
    { "10000000000", 0, 0 },
    { "100000000000", 0, 0 },
    { "000000000000000019876", 1, 19876 },
    { "4294967295", 1, 4294967295 },
    { "4294967296", 0, 0 },
    { "4294967299", 0, 0 },
    { "4294967300", 0, 0 },
    { "004294967295", 1, 4294967295 },
    { "2147483648", 1, 2147483648 },
    { "2147483647", 1, 2147483647 },
    { "42949s7295", 0, 0 },
    { NULL, 0, 0 }
};

typedef struct test_s32_s {
    char *string;
    bool accept;
    int32_t result;
} test_s32_t;

test_s32_t const s32_tests[] = {
    { "0", 1, 0 },
    { "-0", 1, 0 },
    { "1", 1, 1 },
    { "11", 1, 11 },
    { "270", 1, 270 },
    { "10", 1, 10 },
    { "100", 1, 100 },
    { "1000", 1, 1000 },
    { "10000", 1, 10000 },
    { "100000", 1, 100000 },
    { "1000000", 1, 1000000 },
    { "10000000", 1, 10000000 },
    { "100000000", 1, 100000000 },
    { "1000000000", 1, 1000000000 },
    { "10000000000", 0, 0 },
    { "100000000000", 0, 0 },
    { "-10", 1, -10 },
    { "-100", 1, -100 },
    { "-1000", 1, -1000 },
    { "-10000", 1, -10000 },
    { "-100000", 1, -100000 },
    { "-1000000", 1, -1000000 },
    { "-10000000", 1, -10000000 },
    { "-100000000", 1, -100000000 },
    { "-1000000000", 1, -1000000000 },
    { "-10000000000", 0, 0 },
    { "-100000000000", 0, 0 },
    { "000000000000000019876", 1, 19876 },
    { "-000000000000000019876", 1, -19876 },
    { "4294967295", 0, 0 },
    { "2147483647", 1, 2147483647 },
    { "-2147483647", 1, -2147483647 },
    { "2147483648", 0, 0 },
    { "-2147483648", 1, -2147483648 },
    { "2147483649", 0, 0 },
    { "-2147483649", 0, 0 },
    { "0002147483647", 1, 2147483647 },
    { "4294967296", 0, 0 },
    { "4294967299", 0, 0 },
    { "4294967300", 0, 0 },
    { NULL, 0, 0 }
};

typedef struct test_float_s {
    char *string;
    bool accept;
    double result;
} test_float_t;

test_float_t const float_tests[] = {
    { "0", 1, 0.0 },
    { "0.0", 1, 0.0 },
    { "00.00", 1, 0.0 },
    { "1", 1, 1.0 },
    { "01", 1, 1.0 },
    { "1.0", 1, 1.0 },
    { "0.1", 1, 0.1F },
    { "0.10", 1, 0.1F },
    { ".1", 1, 0.1F },
    { "12345678987654321",  1, 12345678987654321.0  },
    { "1234567898765432.1", 1, 1234567898765432.1 },
    { "123456789876543.21", 1, 123456789876543.21 },
    { "12345678987654.321", 1, 12345678987654.321 },
    { "1234567898765.4321", 1, 1234567898765.4321 },
    { "123456789876.54321", 1, 123456789876.54321 },
    { "12345678987.654321", 1, 12345678987.654321 },
    { "1234567898.7654321", 1, 1234567898.7654321 },
    { "123456789.87654321", 1, 123456789.87654321 },
    { "12345678.987654321", 1, 12345678.987654321 },
    { "1234567.8987654321", 1, 1234567.8987654321 },
    { "123456.78987654321", 1, 123456.78987654321 },
    { "12345.678987654321", 1, 12345.678987654321 },
    { "1234.5678987654321", 1, 1234.5678987654321 },
    { "123.45678987654321", 1, 123.45678987654321 },
    { "12.345678987654321", 1, 12.345678987654321 },
    { "1.2345678987654321", 1, 1.2345678987654321 },
    { "-12345678987654321",  1, -12345678987654321.0 },
    { "-123456789876.54321", 1, -123456789876.54321 },
    { "-123456.78987654321", 1, -123456.78987654321 },
    { "-1.2345678987654321", 1, -1.2345678987654321 },
    { "4294967000", 1, 4294967000.0 },
    { "4294967100", 1, 4294967100.0 },
    { "4294967160", 1, 4294967160.0 },
    { "4294967161", 1, 4294967161.0 },
    { "4294967162", 1, 4294967162.0 },
    { "4294967163", 1, 4294967163.0 },
    { "4294967164", 1, 4294967164.0 },
    { "4294967165", 1, 4294967165.0 },
    { "4294967166", 1, 4294967166.0 },
    { "4294967167", 1, 4294967167.0 },
    { "4294967168", 1, 4294967168.0 },
    { "4294967169", 1, 4294967169.0 },
    { "4294967170", 1, 4294967170.0 },
    { "4294967200", 1, 4294967200.0 },
    { "4294967250", 1, 4294967250.0 },
    { "4294967290", 1, 4294967290.0 },
    { "4294967292", 1, 4294967292.0 },
    { "4294967294", 1, 4294967294.0 },
    { "4294967295", 1, 4294967295.0 },
    { "4294967296", 1, 4294967296.0 },
    { "4294967297", 1, 4294967297.0 },
    { "4294967298", 1, 4294967298.0 },
    { "4294967300", 1, 4294967300.0 },
    { NULL, 0, 0 }
};

int test_bools(void)
{
    test_bool_t const *curr_test;
    bool accept;
    bool result;
    int errors = 0;

    print_string("\nTesting bool conversion\n");
    curr_test = bool_tests;
    while ( curr_test->string != NULL ) {
        accept = str_to_bool(curr_test->string, &result);
        if ( curr_test->accept ) {
            if ( accept ) {
                // expected to accept the string, did accept the string
                // check the result
                if ( result == curr_test->result ) {
                    // pass
                    printf("        '%s' returned %d\n", curr_test->string, result);
                } else {
                    // returned wrong value, fail
                    printf("  FAIL: '%s' expected %d, returned %d\n", curr_test->string, curr_test->result, result);
                    errors++;
                }
            } else {
                // expected to accept the string, did not accept the string
                printf("  FAIL: '%s' wrongly rejected\n", curr_test->string);
                errors++;
            }
        } else {
            if ( accept ) {
                // expected to reject the string, but accepted it
                printf("  FAIL: '%s' wrongly accepted, returned %d\n", curr_test->string, result);
                errors++;
            } else {
                // expected to reject the string, did reject the string
                printf("        '%s' correctly rejected\n", curr_test->string);
            }
        }
        curr_test++;
    }
    if ( errors > 0 ) {
        printf("ERRORS: %d failed bool conversion tests\n", errors);
    } else {
        printf("Bool testing passed\n");
    }
    return errors;
}

int test_u32s(void)
{
    test_u32_t const *curr_test;
    bool accept;
    uint32_t result;
    int errors = 0;

    print_string("\nTesting u32 conversion\n");
    curr_test = u32_tests;
    while ( curr_test->string != NULL ) {
        accept = str_to_u32(curr_test->string, &result);
        if ( curr_test->accept ) {
            if ( accept ) {
                // expected to accept the string, did accept the string
                // check the result
                if ( result == curr_test->result ) {
                    // pass
                    printf("        '%s' returned %u\n", curr_test->string, result);
                } else {
                    // returned wrong value, fail
                    printf("  FAIL: '%s' expected %u, returned %u\n", curr_test->string, curr_test->result, result);
                    errors++;
                }
            } else {
                // expected to accept the string, did not accept the string
                printf("  FAIL: '%s' wrongly rejected\n", curr_test->string);
                errors++;
            }
        } else {
            if ( accept ) {
                // expected to reject the string, but accepted it
                printf("  FAIL: '%s' wrongly accepted, returned %u\n", curr_test->string, result);
                errors++;
            } else {
                // expected to reject the string, did reject the string
                printf("        '%s' correctly rejected\n", curr_test->string);
            }
        }
        curr_test++;
    }
    if ( errors > 0 ) {
        printf("ERRORS: %d failed u32 conversion tests\n", errors);
    } else {
        printf("U32 testing passed\n");
    }
    return errors;
}

int test_s32s(void)
{
    test_s32_t const *curr_test;
    bool accept;
    int32_t result;
    int errors = 0;

    print_string("\nTesting s32 conversion\n");
    curr_test = s32_tests;
    while ( curr_test->string != NULL ) {
        accept = str_to_s32(curr_test->string, &result);
        if ( curr_test->accept ) {
            if ( accept ) {
                // expected to accept the string, did accept the string
                // check the result
                if ( result == curr_test->result ) {
                    // pass
                    printf("        '%s' returned %d\n", curr_test->string, result);
                } else {
                    // returned wrong value, fail
                    printf("  FAIL: '%s' expected %d, returned %d\n", curr_test->string, curr_test->result, result);
                    errors++;
                }
            } else {
                // expected to accept the string, did not accept the string
                printf("  FAIL: '%s' wrongly rejected\n", curr_test->string);
                errors++;
            }
        } else {
            if ( accept ) {
                // expected to reject the string, but accepted it
                printf("  FAIL: '%s' wrongly accepted, returned %d\n", curr_test->string, result);
                errors++;
            } else {
                // expected to reject the string, did reject the string
                printf("        '%s' correctly rejected\n", curr_test->string);
            }
        }
        curr_test++;
    }
    if ( errors > 0 ) {
        printf("ERRORS: %d failed s32 conversion tests\n", errors);
    } else {
        printf("S32 testing passed\n");
    }
    return errors;
}

int test_floats(void)
{
    test_float_t const *curr_test;
    bool accept;
    float result;
    float max_limit, min_limit;
    int errors = 0;

    print_string("\nTesting float conversion\n");
    curr_test = float_tests;
    while ( curr_test->string != NULL ) {
        accept = str_to_float(curr_test->string, &result);
        if ( curr_test->accept ) {
            if ( accept ) {
                // expected to accept the string, did accept the string
                // check the result
                max_limit = nextafterf((float)curr_test->result, INFINITY);
                min_limit = nextafterf((float)curr_test->result, -INFINITY);
                if ( ( result > min_limit ) && ( result < max_limit ) ) {
                    // pass
                    printf("        '%s' returned %f (limits %f to %f)\n", curr_test->string, result, min_limit, max_limit);
                } else {
                    // returned wrong value, fail
                    printf("  FAIL: '%s' expected %f to %f, returned %f\n", curr_test->string, min_limit, max_limit, result);
                    errors++;
                }
            } else {
                // expected to accept the string, did not accept the string
                printf("  FAIL: '%s' wrongly rejected\n", curr_test->string);
                errors++;
            }
        } else {
            if ( accept ) {
                // expected to reject the string, but accepted it
                printf("  FAIL: '%s' wrongly accepted, returned %f\n", curr_test->string, result);
                errors++;
            } else {
                // expected to reject the string, did reject the string
                printf("        '%s' correctly rejected\n", curr_test->string);
            }
        }
        curr_test++;
    }
    if ( errors > 0 ) {
        printf("ERRORS: %d failed float conversion tests\n", errors);
    } else {
        printf("Float testing passed\n");
    }
    return errors;
}

int main (void) {
    int total_errors;

    platform_init();
    print_string("\n\nstr_to_xx() conversion testing\n");
    total_errors = test_bools();
    total_errors += test_u32s();
    total_errors += test_s32s();
    total_errors += test_floats();
    printf("\n\nTesting complete, %d tests failed\n", total_errors);
    while(1) {}
    // Return 0 to satisfy compiler
    return 0;
}

