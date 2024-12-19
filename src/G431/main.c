#include "platform_g431.h"

#include "emblocs.h"
#include "printing.h"
#include "main.h"

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

extern bl_comp_def_t bl_mux2_def;
extern bl_comp_def_t bl_sum2_def;
extern bl_comp_def_t bl_perftimer_def;

void test_int_print(uint32_t value)
{
    char buf[20];

    print_uint_hex((uint32_t)value, 8, 1, 0);
    print_string(" as int: '");
    print_int_dec(value, '+');
    print_string("' = '");
    snprint_int_dec(buf, 20, value, '+');
    print_string(buf);
    print_string("'  as uint: '");
    print_uint_dec(value);
    print_string("' = '");
    snprint_uint_dec(buf, 20, value);
    print_string(buf);
    print_string("'\n");
}

void test_binhex_print(uint32_t value)
{
    char buf[50];

    print_uint_hex((uint32_t)value, 8, 1, 0);
    print_string(" as hex: '");
    snprint_uint_hex(buf, 50, (uint32_t)value, 2, 1, 0);
    print_string(buf);
    print_string("' = '");
    snprint_uint_hex(buf, 50, (uint32_t)value, 8, 0, 3);
    print_string(buf);
    print_string("'  as binary: '");
    snprint_uint_bin(buf, 50, value, 32, 7 );
    print_string(buf);
    print_string("' = '");
    snprint_uint_bin(buf, 50, value, 32, 4);
    print_string(buf);
    print_string("'\n");
}

int main (void) {
    uint32_t reg;
    char *hello = "\nHello, world!\n";
    double d1, d2, d3;
    float f1, f2, f3;
    uint32_t start, end;

    platform_init();
    // Put pin PC6 in general purpose output mode
    reg = LED_PORT->MODER;
    reg &= ~GPIO_MODER_MODE6_Msk;
    reg |= 0x01 << GPIO_MODER_MODE6_Pos;
    LED_PORT->MODER = reg;
    
    print_string(hello);
    delay(500);
    //printf("sum2_def is at %p, has %d pins at %p\n", 
    //    &bl_sum2_def, bl_sum2_def.pin_count, bl_sum2_def.pin_defs);
    //printf("and a function at %p\n", bl_sum2_def.funct_defs[0].fp);
    //printf("sum2_def is at %p, has %d pins\n", &bl_sum2_def, bl_sum2_def.pin_count);

    start = tsc_read();
    test_binhex_print(start);
    test_binhex_print(0);
    test_binhex_print(0x7FFFFFFF);
    test_binhex_print(0x80000000);
    test_binhex_print(0x80000001);
    test_binhex_print(0xFFFFFFFF);

    

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
    d1 = 0.0;
    print_double(d1, 6, '+');
    print_char('\n');
    print_double_sci(d1, 6, '+');
    print_char('\n');

    d1 = -0.0;
    print_double(d1, 6, '+');
    print_char('\n');
    print_double_sci(d1, 6, '+');
    print_char('\n');

    d1 = 0.0;
    print_double(d1, 0, '+');
    print_char('\n');
    print_double_sci(d1, 0, '+');
    print_char('\n');

    d1 = -0.0/0.0;
    print_double(d1, 0, '+');
    print_char('\n');
    print_double_sci(d1, 0, '+');
    print_char('\n');

    d1 = 1.0/0.0;
    print_double(d1, 0, '+');
    print_char('\n');
    print_double_sci(d1, 0, '+');
    print_char('\n');

    d1 = -1.0/0.0;
    print_double(d1, 0, '+');
    print_char('\n');
    print_double_sci(d1, 0, '+');
    print_char('\n');


    print_string("timing checks\n");
    f1 = tsc_read();
    f2 = tsc_read();
    start = tsc_read();
    f3 = f1 - f2;
    end = tsc_read();
    print_string("float: ");
    print_int_dec(end-start, ' ');
    print_string(" clocks to get answer ");
    print_double_sci(f1, 10, '+');
    print_string(" - ");
    print_double_sci(f2, 10, '+');
    print_string(" = ");
    print_double_sci(f3, 10, '+');
    print_string("\n");
    d1 = tsc_read();
    d2 = tsc_read();
    start = tsc_read();
    d3 = d1 - d2;
    end = tsc_read();
    print_string("double: ");
    print_int_dec(end-start, ' ');
    print_string(" clocks to get answer ");
    print_double_sci(d1, 10, '+');
    print_string(" - ");
    print_double_sci(d2, 10, '+');
    print_string(" = ");
    print_double_sci(d3, 10, '+');
    print_string("\n");

    while(1) {}

    print_memory((void *)hello, 512);
    bl_newinst(&bl_sum2_def, "comp1");
    bl_newinst(&bl_sum2_def, "sum21");
    bl_newinst(&bl_perftimer_def, "timer");
    bl_newinst(&bl_mux2_def, "comp4");
    bl_newsig(BL_TYPE_BIT, "sel_sig");
    bl_newsig(BL_TYPE_FLOAT, "fp_sig");
    bl_newsig(BL_TYPE_FLOAT, "output");
    bl_newsig(BL_TYPE_U32, "clocks");
    list_all_instances();
    list_all_signals();
    bl_linksp("clocks", "timer", "time");
    bl_linksp("fp_sig", "comp1", "out");
    bl_linksp("fp_sig", "comp4", "in1");
    bl_linksp("sel_sig", "comp4", "sel");
    list_all_instances();
    list_all_signals();
    

    while (1) {
        // Reset the state of pin 6 to output low
        LED_PORT->BSRR = GPIO_BSRR_BR_6;

        delay(5000);
        print_string("tick... ");
        if ( cons_rx_ready() ) {
          cons_tx_wait(cons_rx());
        }
        // Set the state of pin 6 to output high
        LED_PORT->BSRR = GPIO_BSRR_BS_6;

        delay(500);
        print_string("tock\n");
        if ( cons_rx_ready() ) {
          cons_tx_wait(cons_rx());
        }
    }

    // Return 0 to satisfy compiler
    return 0;
}

