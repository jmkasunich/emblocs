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

extern bl_comp_def_t bl_mux2_def;
extern bl_comp_def_t bl_sum2_def;
extern uint32_t blocs_pool[];


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
    print_memory((void *)blocs_pool, 512);
    bl_newinst(&bl_sum2_def, "comp1");
    bl_newinst(&bl_sum2_def, "sum21");
    bl_newinst(&bl_sum2_def, "comp4");
    bl_newinst(&bl_sum2_def, "comp3");
    print_memory((void *)blocs_pool, 512);
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

