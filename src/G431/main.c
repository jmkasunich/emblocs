#include "platform_g431.h"

#include "emblocs.h"
#include "printing.h"
#include "main.h"
#include <assert.h>
#include "tmp_gpio.h"

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
extern bl_comp_def_t bl_gpio_def;

gpio_port_config_t portA = { 'A', {
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PA0  = VBUS
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PA1  = Ifb1 opamp +
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PA2  = opamp 1 out
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PA3  = Ifb1 opamp -
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PA4  = BEMF 1
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PA5  = Ifb2 opamp -
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PA6  = opampt 2 out
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PA7  = Ifb2 opamp +
    { BGPIO_MD_OUT,  BGPIO_OUT_PP, BGPIO_SPD_MED,  BGPIO_PULL_NONE, BGPIO_AF0 }, // PA8  = gate U hi
    { BGPIO_MD_OUT,  BGPIO_OUT_PP, BGPIO_SPD_MED,  BGPIO_PULL_NONE, BGPIO_AF0 }, // PA9  = gate V hi
    { BGPIO_MD_OUT,  BGPIO_OUT_PP, BGPIO_SPD_MED,  BGPIO_PULL_NONE, BGPIO_AF0 }, // PA10 = gate W hi
    { BGPIO_MD_IN,   BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PA11 = CAN RX
    { BGPIO_MD_OUT,  BGPIO_OUT_PP, BGPIO_SPD_MED,  BGPIO_PULL_NONE, BGPIO_AF0 }, // PA12 = gate V lo
    { BGPIO_MD_ALT,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_UP,   BGPIO_AF0 }, // PA13 = SWDIO
    { BGPIO_MD_ALT,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_DOWN, BGPIO_AF0 }, // PA14 = SWCLK
    { BGPIO_MD_ALT,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_UP,   BGPIO_AF0 }  // PA15 = PWM
}};

gpio_port_config_t portB = { 'B', {
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB0  = BEMF 2
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB1  = opamp 3 out
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB2  = Ifb3 opamp -
    { BGPIO_MD_ALT,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF7 }, // PB3  = USART2 TX
    { BGPIO_MD_ALT,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_UP,   BGPIO_AF7 }, // PB4  = USART2 RX
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB5  = GPIO BEMF
    { BGPIO_MD_BIN,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB6  = ENC PH A / HALL 1
    { BGPIO_MD_BIN,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB7  = ENC PH V / HALL 2
    { BGPIO_MD_BIN,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB8  = ENC PH Z / HALL 3
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB9  = CAN TX
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB10 = NC
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB11 = BEMF 3
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB12 = POTENTIOMETER
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB13 = NC
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB14 = TEMPERATURE SENSOR
    { BGPIO_MD_OUT,  BGPIO_OUT_PP, BGPIO_SPD_MED,  BGPIO_PULL_NONE, BGPIO_AF0 }  // PB15 = gate W lo
}};

gpio_port_config_t portC = { 'C', {
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC0  = 
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC1  = 
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC2  = 
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC3  = 
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC4  = 
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC5  = 
    { BGPIO_MD_BOUT, BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC6  = STATUS LED
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC7  = 
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC8  = 
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC9  = 
    { BGPIO_MD_BIN,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC10 = BUTTON
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC11 = CAN SHDN
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC12 = 
    { BGPIO_MD_OUT,  BGPIO_OUT_PP, BGPIO_SPD_MED,  BGPIO_PULL_NONE, BGPIO_AF0 }, // PC13 = gate U lo
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PC14 = OSC / CAN TERM
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }  // PC15 = OSC
}};


bl_inst_def_t const instances[] = {
    { "ramp_sum", &bl_sum2_def, NULL },
    { "inv_sum", &bl_sum2_def, NULL },
    { "timer", &bl_perftimer_def, NULL },
    { "dir_mux", &bl_mux2_def, NULL },
    { "ramp_mux", &bl_mux2_def, NULL },
    { NULL, NULL, NULL }
};

char const * const nets[] = {
    "FLOAT", "speed", "dir_mux", "in0", "inv_sum", "in0",
    "FLOAT", "speed_inv", "inv_sum", "out", "dir_mux", "in1",
    "BIT", "dir", "dir_mux", "sel",
    "BIT", "ramp", "ramp_mux", "sel",
    "FLOAT", "slope", "dir_mux", "out", "ramp_sum", "in1",
    "FLOAT", "ramp_gain", "ramp_mux", "out", "ramp_sum", "gain1",
    "FLOAT", "output", "ramp_sum", "out", "ramp_sum", "in0",
    "U32", "clocks", "timer", "time",
    NULL
};

bl_setsig_def_t const setsigs[] = {
    { "ramp", { .b = 1 } },
    { "speed", { .f = 1.5F } },
    {NULL, {0} }
};

bl_setpin_def_t const setpins[] = {
    { "inv_sum", "gain0", { .f = -1.0F } },
    { "ramp_sum", "gain0", { .f = 1.0F } },
    { "ramp_mux", "in1", { .f = 1.0F } },
    { NULL, NULL, {0} }
};

char const * const threads[] = {
    "HAS_FP", "1000000", "main_thread",
    "timer", "start",
    "inv_sum", "update",
    "dir_mux", "update",
    "ramp_mux", "update",
    "ramp_sum", "update",
    "timer", "stop",
    NULL
};

#define CLK_MHZ 170

int main (void) {
    uint32_t reg;
    char *hello = "\nHello, world!\n";
    uint32_t t_start, t_inst, t_nets, t_setsig, t_setpin, t_threads, t_total;
    bl_thread_data_t *thread;
    char c;
    bl_sig_data_t data;

    platform_init();
    // Put pin PC6 in general purpose output mode
    reg = LED_PORT->MODER;
    reg &= ~GPIO_MODER_MODE6_Msk;
    reg |= 0x01 << GPIO_MODER_MODE6_Pos;
    LED_PORT->MODER = reg;

    print_string("BOOT\n");
    print_string(hello);
//    print_memory((void *)hello, 512);
    print_string("\n\n");
    bl_show_memory_status();
    print_string("begin init\n");
    t_start = tsc_read();
    bl_init_instances(instances);
    t_inst = tsc_read();
    bl_init_nets(nets);
    t_nets = tsc_read();
    bl_init_setsigs(setsigs);
    t_setsig = tsc_read();
    bl_init_setpins(setpins);
    t_setpin = tsc_read();
    bl_init_threads(threads);
    t_threads = tsc_read();
    print_string("init complete\n");
    t_total = t_threads - t_start;
    t_threads -= t_setpin;
    t_setpin -= t_setsig;
    t_setsig -= t_nets;
    t_nets -= t_inst;
    t_inst -= t_start;
    printf("Init time:        Clocks      uSec\n");
    printf("  Instances:    %8d  %8d\n", t_inst, t_inst/CLK_MHZ);
    printf("  Nets:         %8d  %8d\n", t_nets, t_nets/CLK_MHZ);
    printf("  Set signals:  %8d  %8d\n", t_setsig, t_setsig/CLK_MHZ);
    printf("  Set pins:     %8d  %8d\n", t_setpin, t_setpin/CLK_MHZ);
    printf("  Threads:      %8d  %8d\n\n", t_threads, t_threads/CLK_MHZ);
    printf("  Total:        %8d  %8d\n\n", t_total, t_total/CLK_MHZ);
    bl_show_memory_status();
    bl_show_all_instances();
    bl_show_all_signals();
    bl_show_all_threads();

    
    thread = bl_find_thread_data_by_name("main_thread");
    assert(thread != NULL);
    while (1) {
        // Reset the state of pin 6 to output low
        LED_PORT->BSRR = GPIO_BSRR_BR_6;

        print_string("ready... ");
        // wait for key pressed
        while ( ! cons_rx_ready() );
        // read the key
        c = cons_rx();
        switch(c) {
        case '+':
            data.b = 0;
            bl_set_sig_by_name("dir", &data);
            break;
        case '-':
            data.b = 1;
            bl_set_sig_by_name("dir", &data);
            break;
        case 'g':
            data.b = 1;
            bl_set_sig_by_name("ramp", &data);
            break;
        case 's':
            data.b = 0;
            bl_set_sig_by_name("ramp", &data);
            break;
        default:
            break;
        }
        print_string("running...");
        t_start = tsc_read();
        bl_thread_update(thread, 1);
        t_threads = tsc_read();
        print_string("done\n");
        t_threads -= t_start;
        printf("execution time: %d\n", t_threads);
        bl_show_all_signals();
        // Set the state of pin 6 to output high
        LED_PORT->BSRR = GPIO_BSRR_BS_6;
        delay(500);
    }
    // Return 0 to satisfy compiler
    return 0;
}

