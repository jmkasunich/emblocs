#include "platform_g431.h"

#include "emblocs.h"
#include "printing.h"
#include "main.h"
#include "linked_list.h"

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

bl_inst_def_t const instances[] = {
    { "comp1", &bl_sum2_def, NULL },
    { "sum21", &bl_sum2_def, NULL },
    { "timer", &bl_perftimer_def, NULL },
    { "comp4", &bl_mux2_def, NULL },
    { NULL, NULL, NULL }
};

char const * const nets[] = {
    "FLOAT", "fp_sig", "comp1", "out", "comp4", "in1",
    "FLOAT", "output", "comp4", "out", "sum21", "gain0",
    "BIT", "sel_sig", "comp4", "sel",
    "U32", "clocks", "timer", "time",
    NULL
};

bl_setsig_def_t const setsigs[] = {
    { "sel_sig", { .b = 1 } },
    { "fp_sig", { .f = 3.14F } },
    {NULL, {0} }
};

bl_setpin_def_t const setpins[] = {
    { "comp1", "in0", { .f = 2.1F } },
    { "sum21", "gain0", { .f = 4.5F } },
    { NULL, NULL, {0} }
};



int main (void) {
    uint32_t reg;
    char *hello = "\nHello, world!\n";

    platform_init();
    // Put pin PC6 in general purpose output mode
    reg = LED_PORT->MODER;
    reg &= ~GPIO_MODER_MODE6_Msk;
    reg |= 0x01 << GPIO_MODER_MODE6_Pos;
    LED_PORT->MODER = reg;

    print_string("BOOT\n");

//    linked_list_test();

    print_string(hello);

    print_memory((void *)hello, 512);
    print_string("\n\n");
    bl_show_memory_status();
    bl_show_all_instances();
    bl_show_all_signals();
    print_string("begin init\n");
    bl_init_instances(instances);
    bl_init_nets(nets);
    bl_init_setsigs(setsigs);
    bl_init_setpins(setpins);
    print_string("init complete\n");
    bl_show_memory_status();
    bl_show_all_instances();
    bl_show_all_signals();

    

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

