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
    print_uint_dec(line, 0);
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

// gotta figure out how to include these structure definitions
// these should be private to the components,
// the only thing this file really needs to know is the size of the struct

typedef struct bl_perftimer_inst_s {
    bl_pin_u32_t time;
	uint32_t tsc;
} bl_perftimer_inst_t;

typedef struct bl_sum2_inst_s {
    // pins
    bl_pin_float_t in0;
    bl_pin_float_t gain0;
	bl_pin_float_t in1;
    bl_pin_float_t gain1;
    bl_pin_float_t offset;
	bl_pin_float_t out;
} bl_sum2_inst_t;

typedef struct bl_mux2_inst_s {
    bl_pin_float_t in0;
	bl_pin_float_t in1;
	bl_pin_float_t out;
	bl_pin_bit_t sel;
} bl_mux2_inst_t;

extern bl_comp_def_t bl_mux2_def;
extern bl_comp_def_t bl_sum2_def;
extern bl_comp_def_t bl_perftimer_def;

struct bl_mux2_inst_s comp1;
struct bl_sum2_inst_s sum21;
struct bl_perftimer_inst_s timer;
struct bl_mux2_inst_s comp4;


bl_inst_def_t const instances[] = {
    { "comp1", &bl_mux2_def, &comp1 },
    { "sum21", &bl_sum2_def, &sum21 },
    { "timer", &bl_perftimer_def, &timer },
    { "comp4", &bl_mux2_def, &comp4 },
    { NULL, NULL, NULL }
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
    
    printf(hello);
    printf("sum2_def is at %p, has %d pins at %p\n", 
        &bl_sum2_def, bl_sum2_def.pin_count, bl_sum2_def.pin_defs);
    printf("and a function at %p\n", bl_sum2_def.funct_defs[0].fp);
    printf("sum2_def is at %p, has %d pins\n", &bl_sum2_def, bl_sum2_def.pin_count);
   //print_ptr(&mycomp_def, 8);
    print_memory((void *)hello, 512);
    print_memory((void *)(0x20000000U), 512);
    for ( unsigned int n = 0 ; n < ARRAYCOUNT(instances)-1 ; n++ ) {
        bl_init_instance(&(instances[n]));
    }
    print_memory((void *)(0x20000000U), 512);
    list_all_instances();





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

