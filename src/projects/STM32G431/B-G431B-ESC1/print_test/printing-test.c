#include "platform_g431.h"

#include "printing.h"
#include <float.h>
#include <assert.h>

#define DEC_INT_TEST(value, sign)  dec_int_test(value, sign, #value "," #sign)
#define DEC_UINT_TEST(value)  dec_uint_test(value, #value)
#define HEX_UINT_TEST(value, digits, group, uc)  hex_uint_test(value, digits, group, uc, #value "," #digits "," #group "," #uc)
#define BIN_UINT_TEST(value, digits, group)  bin_uint_test(value, digits, group, #value "," #digits "," #group)
#define HEX_PTR_TEST(value)  hex_ptr_test(value, #value)
#define DBL_TEST(value, precision, sign)  dbl_test(value, precision, sign, #value "," #precision "," #sign)
#define DBL_SCI_TEST(value, precision, sign)  dbl_sci_test(value, precision, sign, #value "," #precision "," #sign)

#define PRINTF_TEST0(format, expect)  do {\
                                        capture_buffer_start();\
                                        uint32_t start = tsc_read();\
                                        printf_(format);\
                                        uint32_t end = tsc_read();\
                                        capture_buffer_end();\
                                        printf_results(#format, expect, end-start);\
                                      } while (0)
#define PRINTF_TEST1(format, value1, expect)  do {\
                                        capture_buffer_start();\
                                        uint32_t start = tsc_read();\
                                        printf_(format, value1);\
                                        uint32_t end = tsc_read();\
                                        capture_buffer_end();\
                                        printf_results(#format "," #value1, expect, end-start);\
                                      } while (0)
#define PRINTF_TEST2(format, value1, value2, expect)  do {\
                                        capture_buffer_start();\
                                        uint32_t start = tsc_read();\
                                        printf_(format, value1, value2);\
                                        uint32_t end = tsc_read();\
                                        capture_buffer_end();\
                                        printf_results(#format "," #value1 "," #value2, expect, end-start);\
                                      } while (0)


/* buffer used to capture console output for checking */
#define CAPTURE_BUFFER_SIZE 1000
char capture_buffer[CAPTURE_BUFFER_SIZE];
int capture_buffer_len;

void print_to_buffer(char c)
{
    capture_buffer[capture_buffer_len++] = c;
    capture_buffer[capture_buffer_len] = '\0';
    assert(capture_buffer_len < (CAPTURE_BUFFER_SIZE-2));
}

void capture_buffer_start(void)
{
    capture_buffer_len = 0;
    capture_buffer[capture_buffer_len] = '\0';
    print_char = print_to_buffer;
}

void capture_buffer_end(void)
{
    print_char = cons_tx_wait;
}

void capture_buffer_print(void)
{
    char *cp = capture_buffer;

    while ( *cp != '\0' ) {
        cons_tx_wait(*cp++);
    }
}

void printf_results(char *args, char *expect, uint32_t clocks)
{
    char *r, *e;

    r = capture_buffer;
    e = expect;
    while ( ( *r == *e ) && ( *e != '\0' ) ) { r++; e++; };
    if ( *r != *e ) {
        print_string("FAIL: ");
    } else {
        print_string("pass: ");
    }
    print_string("in ");
    print_uint_dec(clocks);
    print_string(" clocks, printf(");
    print_string(args);
    print_string(") produced '");
    capture_buffer_print();
    if ( *r != *e ) {
        print_string("', expected '");
        print_string(expect);
    }
    print_string("'\n");
}


void __assert_func (const char * file, int line, const char * funct, const char *expr)
{
    print_string("assert(");
    print_string(expr);
    print_string(") at ");
    print_string(file);
    print_string(":");
    print_int_dec(line, '\0');
    print_string(" in function ");
    print_string(funct);
    print_string("()\n");
    // loop forever
    do {} while (1);
}

int length(char *s)
{
    int len = 0;
    while ( s[len] != '\0' ) len++;
    return len;
}


void print_test_result(char *function, char *val_string, char *result, uint32_t clocks, int len)
{
    print_string(function);
    print_string("(");
    print_string(val_string);
    print_string("), '");
    print_string(result);
    print_string("', ");
    print_uint_dec(clocks);
    print_string(", clocks, ");
    print_int_dec(len, '\0');
    print_string(", bytes");
    if ( len != length(result) ) {
        print_string("  LENGTH ERROR! string is ");
        print_int_dec(length(result), '\0');
        print_string(" bytes");
    }
    print_string("\n");
}


void dec_int_test(int32_t value, char sign, char *val_string)
{
    uint32_t start, end;
    char buffer[100];
    int len;

    start = tsc_read();
    len = snprint_int_dec(buffer, 100, value, sign);
    end = tsc_read();
    print_test_result("snprint_int_dec", val_string, buffer, end-start, len);
}

void dec_uint_test(uint32_t value, char *val_string)
{
    uint32_t start, end;
    char buffer[100];
    int len;

    start = tsc_read();
    len = snprint_uint_dec(buffer, 100, value);
    end = tsc_read();
    print_test_result("snprint_uint_dec", val_string, buffer, end-start, len);
}

void hex_uint_test(uint32_t value, int digits, int group, int uc,  char *val_string)
{
    uint32_t start, end;
    char buffer[100];
    int len;

    start = tsc_read();
    len = snprint_uint_hex(buffer, 100, value, digits, group, uc);
    end = tsc_read();
    print_test_result("snprint_uint_hex", val_string, buffer, end-start, len);
}


void bin_uint_test(uint32_t value, int digits, int group, char *val_string)
{
    uint32_t start, end;
    char buffer[100];
    int len;

    start = tsc_read();
    len = snprint_uint_bin(buffer, 100, value, digits, group);
    end = tsc_read();
    print_test_result("snprint_uint_bin", val_string, buffer, end-start, len);
}

void hex_ptr_test(void * value, char *val_string)
{
    uint32_t start, end;
    char buffer[100];
    int len;

    start = tsc_read();
    len = snprint_ptr(buffer, 100, value);
    end = tsc_read();
    print_test_result("snprint_ptr", val_string, buffer, end-start, len);
}


void dbl_test(double value, int precision, char sign, char *val_string)
{
    uint32_t start, end;
    char buffer[100];
    int len;

    start = tsc_read();
    len = snprint_double(buffer, 100, value, precision, sign);
    end = tsc_read();
    print_test_result("snprint_double", val_string, buffer, end-start, len);
}


void dbl_sci_test(double value, int precision, char sign, char *val_string)
{
    uint32_t start, end;
    char buffer[100];
    int len;

    start = tsc_read();
    len = snprint_double_sci(buffer, 100, value, precision, sign);
    end = tsc_read();
    print_test_result("snprint_double_sci", val_string, buffer, end-start, len);
}



int main (void) {
    char *hello = "\nHello, world!\n";
 
    platform_init();
    
    print_string(hello);

/* 
    DEC_INT_TEST(26, '+');
    DEC_INT_TEST(198712325, ' ');
    DEC_INT_TEST(0x7FFFFFFF, '+');
    DEC_INT_TEST(0x80000000, '+');
    DEC_INT_TEST(0x80000001, '+');
    DEC_INT_TEST(0xFFFFFFFF, '+');
    DEC_INT_TEST(0, '\0');

    DEC_UINT_TEST(26);
    DEC_UINT_TEST(198712325);
    DEC_UINT_TEST(0x7FFFFFFF);
    DEC_UINT_TEST(0x80000000);
    DEC_UINT_TEST(0x80000001);
    DEC_UINT_TEST(0xFFFFFFFF);
    DEC_UINT_TEST(0);

    HEX_UINT_TEST(0xDEADBEEF, 8, 4, 1);
    HEX_UINT_TEST(0xDEADBEEF, 8, 8, 1);
    HEX_UINT_TEST(0xDEADBEEF, 8, 0, 0);
    HEX_UINT_TEST(0xDEADBEEF, 6, 4, 1);
    HEX_UINT_TEST(0xDEADBEEF, 9, 3, 0);
    HEX_UINT_TEST(0x13579BDF, 8, 4, 1);
    HEX_UINT_TEST(0xECA86420, 8, 4, 0);
    HEX_UINT_TEST(0x13579BDF, 2, 4, 1);

    BIN_UINT_TEST(0xDEADBEEF, 32, 4);
    BIN_UINT_TEST(0xDEADBEEF, 32, 8);
    BIN_UINT_TEST(0xDEADBEEF, 32, 16);
    BIN_UINT_TEST(0xDEADBEEF, 16, 6);
    BIN_UINT_TEST(0xDEADBEEF, 8, 4);
    BIN_UINT_TEST(0x13579BDF, 32, 4);
    BIN_UINT_TEST(0xECA86420, 32, 4);
    BIN_UINT_TEST(0x13579BDF, 32, 8);

    HEX_PTR_TEST((void *)0xDEADBEEF);
    HEX_PTR_TEST((void *)0x13579BDF);
    HEX_PTR_TEST(NULL);

    DBL_TEST(-1.0/0.0, 16, '+');
    DBL_TEST(-0.0/0.0, 16, '\0');
    DBL_TEST(-0.0, 7, ' ');
    DBL_TEST(0.0, 16, '+');
    DBL_TEST(1.0/0.0, 0, '+');
    DBL_TEST(FLT_MAX, 6, '\0');
    DBL_TEST(FLT_MIN, 15, ' ');
    DBL_TEST(DBL_MAX, 15, '+');
    DBL_TEST(DBL_MIN, 6, '+');
    DBL_TEST(DBL_MAX*10.0, 15, '\0');
    DBL_TEST(DBL_MIN/10.0, 6, '+');
    DBL_TEST(3.14159276543210123456789, 0, '+');
    DBL_TEST(3.14159276543210123456789, 3, '+');
    DBL_TEST(-3.14159276543210123456789, 6, '+');
    DBL_TEST(-3.14159276543210123456789, 9, '+');
    DBL_TEST(3.14159276543210123456789, 16, '+');
    DBL_TEST(0.00000012345678900987654321, 14, '+');
    DBL_TEST(0.000012345678900987654321, 12, '+');
    DBL_TEST(0.0012345678900987654321, 10, '+');
    DBL_TEST(0.12345678900987654321, 8, '+');
    DBL_TEST(12.345678900987654321, 8, '+');
    DBL_TEST(1234.5678900987654321, 8, '+');
    DBL_TEST(123456.78900987654321, 6, '+');
    DBL_TEST(12345678.900987654321, 4, '+');
    DBL_TEST(1234567890.0987654321, 2, '+');
    DBL_TEST(123456789009.87654321, 2, '+');
    DBL_TEST(12345678900987.654321, 4, '+');
    DBL_TEST(1234567890098765.4321, 6, '+');
    DBL_TEST(123456789009876543.21, 8, '+');
    DBL_TEST(12345678900987654321.0, 10, '+');
    DBL_TEST(4294967293.0, 14, '+');
    DBL_TEST(4294967294.0, 14, '+');
    DBL_TEST(4294967295.0, 14, '+');
    DBL_TEST(4294967296.0, 14, '+');
    DBL_TEST(4294967297.0, 14, '+');
    DBL_TEST(0.5e-6, 10, '+');
    DBL_TEST(0.6e-6, 10, '+');
    DBL_TEST(0.7e-6, 10, '+');
    DBL_TEST(0.8e-6, 10, '+');
    DBL_TEST(0.9e-6, 10, '+');
    DBL_TEST(1.0e-6, 10, '+');
    DBL_TEST(1.1e-6, 10, '+');
    DBL_TEST(1.2e-6, 10, '+');
    DBL_TEST(1.3e-6, 10, '+');
    DBL_TEST(1.4e-6, 10, '+');
    DBL_TEST(1.5e-6, 10, '+');
   
    DBL_SCI_TEST(-1.0/0.0, 16, '+');
    DBL_SCI_TEST(-0.0/0.0, 16, '+');
    DBL_SCI_TEST(-0.0, 7, '+');
    DBL_SCI_TEST(0.0, 16, '+');
    DBL_SCI_TEST(1.0/0.0, 0, '+');
    DBL_SCI_TEST(FLT_MAX, 6, '+');
    DBL_SCI_TEST(FLT_MIN, 15, '+');
    DBL_SCI_TEST(DBL_MAX, 15, '+');
    DBL_SCI_TEST(DBL_MIN, 6, '+');
    DBL_SCI_TEST(3.14159276543210123456789, 0, '+');
    DBL_SCI_TEST(3.14159276543210123456789, 3, '+');
    DBL_SCI_TEST(-3.14159276543210123456789, 6, '+');
    DBL_SCI_TEST(-3.14159276543210123456789, 9, '+');
    DBL_SCI_TEST(3.14159276543210123456789, 16, '+');
    DBL_SCI_TEST(0.00000012345678900987654321, 14, '+');
    DBL_SCI_TEST(0.000012345678900987654321, 12, '+');
    DBL_SCI_TEST(0.0012345678900987654321, 10, '+');
    DBL_SCI_TEST(0.12345678900987654321, 8, '+');
    DBL_SCI_TEST(12.345678900987654321, 8, '+');
    DBL_SCI_TEST(1234.5678900987654321, 8, '+');
    DBL_SCI_TEST(123456.78900987654321, 6, '+');
    DBL_SCI_TEST(12345678.900987654321, 4, '+');
    DBL_SCI_TEST(1234567890.0987654321, 2, '+');
    DBL_SCI_TEST(123456789009.87654321, 5, '+');
    DBL_SCI_TEST(12345678900987.654321, 10, '+');
    DBL_SCI_TEST(1234567890098765.4321, 13, '+');
    DBL_SCI_TEST(123456789009876543.21, 15, '+');
    DBL_SCI_TEST(12345678900987654321.0, 0, '+');
*/
    PRINTF_TEST0("Hello, world", "Hello, world");
    PRINTF_TEST1("this is a character: '%c'", 'X', "this is a character: 'X'");
    PRINTF_TEST1("this is a string: '%s'", "testing", "this is a string: 'testing'");
    PRINTF_TEST1("left aligned: '%-9s'", "string", "left aligned: 'string   '");
    PRINTF_TEST1("right aligned: '%9s'", "string", "right aligned: '   string'");
    PRINTF_TEST1("left aligned and truncated: '%-7.3s'", "string", "left aligned and truncated: 'str    '");
    PRINTF_TEST1("long: '%6s'", "long-string", "long: 'long-string'");
    PRINTF_TEST1("integer: '%d'", 12345, "integer: '12345'");
    PRINTF_TEST1("integer: '%d'", -12345, "integer: '-12345'");
    PRINTF_TEST2("'%8d', '%8d'", 12345, -12345, "'   12345', '  -12345'");
    PRINTF_TEST2("'%-8d', '%-8d'", 12345, -12345, "'12345   ', '-12345  '");
    PRINTF_TEST2("'% d', '% d'", 12345, -12345, "' 12345', '-12345'");
    PRINTF_TEST2("'%+d', '%+d'", 12345, -12345, "'+12345', '-12345'");
    PRINTF_TEST2("'%+8d', '%+-8d'", 12345, 12345, "'  +12345', '+12345  '");
    PRINTF_TEST2("'%+08d', '%08d'", 12345, 12345, "'+0012345', '00012345'");
    PRINTF_TEST2("'%08d', '%-08d'", -12345, -12345, "'-0012345', '-12345  '");
    PRINTF_TEST2("%d, %d", 0, 0xFFFFFFFF, "0, -1");
    PRINTF_TEST2("%d, %d", 0x80000000, 0x7FFFFFFF, "-2147483648, 2147483647");
    PRINTF_TEST1("unsigned: '%u'", 12345, "unsigned: '12345'");
    PRINTF_TEST2("%u, %u", 0, 0xFFFFFFFF, "0, 4294967295");
    PRINTF_TEST2("%u, %u", 0x80000000, 0x7FFFFFFF, "2147483648, 2147483647");
    PRINTF_TEST2("'%+8u', '%-8d'", 12345, 12345, "'   12345', '12345   '");
    PRINTF_TEST2("'%08u', '%-08u'", 12345, 12345, "'00012345', '12345   '");
    PRINTF_TEST2("'%x', '%X'", 0x2468ACE0, 0x0ECA8642, "'2468ace0', '0ECA8642'");
    PRINTF_TEST2("'%.4x', '%4X'", 0x2468ACE0, 0x0ECA8642, "'2468-ace0', '8642'");
    PRINTF_TEST2("'%b', '%12.5b'", 0x2468ACE0, 0x0ECA8642, "'00100100011010001010110011100000', '01-10010-00010'");
    PRINTF_TEST2("'%.8b', '%8b'", 0x2468ACE0, 0x0ECA8642, "'00100100-01101000-10101100-11100000', '01000010'");
    PRINTF_TEST1("ptr: %p", (void *)(0x00aa1234), "ptr: 00AA1234");
    PRINTF_TEST2("infinity: '%f', '%f'", 1.0/0.0, -1.0/0.0, "infinity: 'inf', '-inf'");
    PRINTF_TEST2("infinity: '%e', '%e'", 1.0/0.0, -1.0/0.0, "infinity: 'inf', '-inf'");
    PRINTF_TEST2("nans: '%f', '%f'", 0.0/0.0, -0.0/0.0, "nans: 'nan', '-nan'");
    PRINTF_TEST2("nans: '%e', '%e'", 0.0/0.0, -0.0/0.0, "nans: 'nan', '-nan'");
    PRINTF_TEST2("zeros: '%f', '%f'", 0.0, -0.0, "zeros: '0.00000000', '-0.00000000'");
    PRINTF_TEST2("zeros: '%e', '%e'", 0.0, -0.0, "zeros: '0.00000000e+0', '-0.00000000e+0'");
    PRINTF_TEST2("max: '%f', '%e'", FLT_MAX, FLT_MAX, "max: '3.40282347e+38', '3.40282347e+38'");
    PRINTF_TEST2("max: '%f', '%e'", DBL_MAX, DBL_MAX, "max: '1.79769313e+308', '1.79769313e+308'");
    PRINTF_TEST2("min: '%f', '%e'", FLT_MIN, FLT_MIN, "min: '1.17549435e-38', '1.17549435e-38'");
    PRINTF_TEST2("min: '%f', '%e'", DBL_MIN, DBL_MIN, "min: '2.22507386e-308', '2.22507386e-308'");
    PRINTF_TEST2("min/10: '%f', '%e'", FLT_MIN/10.0, DBL_MIN/10.0, "min/10: '1.17549435e-39', '0.00000000e+0'");
    PRINTF_TEST2("12.34: '%f', '%e'", 12.34, 12.34, "12.34: '12.34000000', '1.23400000e+1'");
    PRINTF_TEST2("12.34: '%12.4f', '%12.4e'", 12.34, 12.34, "12.34: '     12.3400', '   1.2340e+1'");
    PRINTF_TEST2("12.34: '%+012.4f', '%+012.4e'", 12.34, 12.34, "12.34: '+000012.3400', '+001.2340e+1'");
    PRINTF_TEST2("12.34: '%+-012.4f', '%+-012.4e'", 12.34, 12.34, "12.34: '+12.3400    ', '+1.2340e+1  '");

 
/*    
    for ( d1 = start*1000.0; d1 > 1e-8 ; d1 /= 10.0 ) {

        print_char('\n');
        print_int_dec(start, 0, '_');
        print_string("000\n");
        print_char('\n');
        for ( prec = 0 ; prec < 16 ; prec++ ) {
            print_double(d1, prec);
            print_char('\n');
            print_double_sci(d1, prec);
            print_char('\n');
        }
    }
*/

    while(1) {}
    // Return 0 to satisfy compiler
    return 0;
}

