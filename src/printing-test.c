#include "G431/platform_g431.h"

#include "printing.h"
#include <float.h>

#define DEC_INT_TEST(value, sign)  dec_int_test(value, sign, #value "," #sign)
#define DEC_UINT_TEST(value)  dec_uint_test(value, #value)
#define HEX_UINT_TEST(value, digits, group, uc)  hex_uint_test(value, digits, group, uc, #value "," #digits "," #group "," #uc)
#define BIN_UINT_TEST(value, digits, group)  bin_uint_test(value, digits, group, #value "," #digits "," #group)
#define HEX_PTR_TEST(value)  hex_ptr_test(value, #value)
#define DBL_TEST(value, precision)  dbl_test(value, precision, #value "," #precision)
#define DBL_SCI_TEST(value, precision)  dbl_sci_test(value, precision, #value "," #precision)


void __assert_func (const char * file, int line, const char * funct, const char *expr)
{
    print_string("assert(");
    print_string(expr);
    print_string(") at ");
    print_string(file);
    print_string(":");
    print_uint_dec(line);
    print_string(" in function ");
    print_string(funct);
    print_string("()\n");
    // loop forever
    do {} while (1);
}

// Quick and dirty delay
static void delay (unsigned int time) {
    for (unsigned int i = 0; i < time; i++)
        for (volatile unsigned int j = 0; j < 20000; j++);
}

int length(char *s)
{
    int len = 0;
    while ( *(s++) != '\0' ) len++;
    return len;
}


void print_test_result(char *function, char *val_string, char *result, uint32_t clocks, int len)
{
    print_string(function);
    print_string("(");
    print_string(val_string);
    print_string(") -> '");
    print_string(result);
    print_string("' in ");
    print_int_dec(clocks, '\0');
    print_string(" clocks, ");
    print_int_dec(len, '\0');
    print_string(" bytes");
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


void dbl_test(double value, int precision, char *val_string)
{
    uint32_t start, end;
    char buffer[100];
    int len;

    start = tsc_read();
    len = snprint_double(buffer, 100, value, precision);
    end = tsc_read();
    print_test_result("snprint_double", val_string, buffer, end-start, len);
}


void dbl_sci_test(double value, int precision, char *val_string)
{
    uint32_t start, end;
    char buffer[100];
    int len;

    start = tsc_read();
    len = snprint_double_sci(buffer, 100, value, precision);
    end = tsc_read();
    print_test_result("snprint_double_sci", val_string, buffer, end-start, len);
}



int main (void) {
    char *hello = "\nHello, world!\n";
 
    platform_init();
    
    print_string(hello);
 
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

    DBL_TEST(FLT_MAX, 6);
    DBL_TEST(FLT_MIN, 15);
    DBL_TEST(DBL_MAX, 15);
    DBL_TEST(DBL_MIN, 6);
    DBL_TEST(3.14159276543210123456789, 3);
    DBL_TEST(3.14159276543210123456789, 0);
    DBL_TEST(3.14159276543210123456789, 16);
    DBL_TEST(-1.0/0.0, 16);
    DBL_TEST(-0.0/0.0, 16);
    DBL_TEST(-0.0, 7);
    DBL_TEST(0.0, 16);
    DBL_TEST(1.0/0.0, 0);
    DBL_TEST(1234567890.0987654321, 3);
    DBL_TEST(1234567890.0987654321, 0);
    DBL_TEST(1234567890.0987654321, 16);
   
    DBL_SCI_TEST(FLT_MAX, 6);
    DBL_SCI_TEST(FLT_MIN, 15);
    DBL_SCI_TEST(DBL_MAX, 15);
    DBL_SCI_TEST(DBL_MIN, 6);
    DBL_SCI_TEST(3.14159276543210123456789, 3);
    DBL_SCI_TEST(3.14159276543210123456789, 0);
    DBL_SCI_TEST(3.14159276543210123456789, 16);
    DBL_SCI_TEST(-1.0/0.0, 16);
    DBL_SCI_TEST(-0.0/0.0, 16);
    DBL_SCI_TEST(-0.0, 7);
    DBL_SCI_TEST(0.0, 16);
    DBL_SCI_TEST(1.0/0.0, 0);
    DBL_SCI_TEST(1234567890.0987654321, 3);
    DBL_SCI_TEST(1234567890.0987654321, 0);
    DBL_SCI_TEST(1234567890.0987654321, 16);
   
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

