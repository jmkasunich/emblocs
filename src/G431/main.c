#include "platform_g431.h"

#include "emblocs.h"
#include "printing.h"
#include "main.h"





// call in main during startup:
//   new_inst(&mycomp_def, "instancename")
// or
//   new_inst("compname", "instancename")
// the latter would search for compname in a list built by register_comp()



_Static_assert(1==1, "pass");

//_Static_assert(1==2, "fail");



#if 1
# define assert(_p) (_assert(__FILE__, __LINE__, _p))
#else
# define assert(_p) do {} while(1)  // just loop forever
#endif

void _assert(char *file, int line, char *msg)
{
    print_string("assert(): ");
    print_string(file);
    print_string(":");
    print_uint_dec(line, 0);
    if ( msg != NULL ) {
        print_string(" : ");
        print_string(msg);
    }
    print_string("\n");
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


int main (void) {
    uint32_t reg;

    platform_init();
    // Put pin PC6 in general purpose output mode
    reg = LED_PORT->MODER;
    reg &= ~GPIO_MODER_MODE6_Msk;
    reg |= 0x01 << GPIO_MODER_MODE6_Pos;
    LED_PORT->MODER = reg;
    
    printf("\nhello world\n");
    printf("mux2_def is at %p, has %d pins at %p\n", 
        &bl_mux2_def, bl_mux2_def.pin_count, bl_mux2_def.pin_defs);
    printf("and a function at %p\n", bl_mux2_def.funct_defs[0].fp);
    printf("sum2_def is at %p, has %d pins\n", &bl_sum2_def, bl_sum2_def.pin_count);
   //print_ptr(&mycomp_def, 8);
    print_memory((void *)0x08000A00, 512);

    while (1) {
        // Reset the state of pin 6 to output low
        LED_PORT->BSRR = GPIO_BSRR_BR_6;

        delay(500);
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

