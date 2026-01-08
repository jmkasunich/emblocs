#include "platform_g431.h"

#include "emblocs_api.h"
#include "printing.h"
#include <assert.h>
#include "tmp_gpio.h"
#include "watch.h"

#define PRINT_INIT

#ifndef _countof
#define _countof(array) (sizeof(array)/sizeof(array[0]))
#endif

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


// Quick and dirty delay
void delay (unsigned int time) {
    for (unsigned int i = 0; i < time; i++)
        for (volatile unsigned int j = 0; j < 20000; j++);
}


extern struct bl_comp_def_s bl_mux2_def;
extern struct bl_comp_def_s bl_sum2_def;
extern struct bl_comp_def_s bl_perftimer_def;
extern struct bl_comp_def_s bl_gpio_def;
extern struct bl_comp_def_s bl_watch_def;

struct bl_comp_def_s * const bl_comp_defs[] = {
    &bl_mux2_def,
    &bl_sum2_def,
    &bl_perftimer_def,
    &bl_gpio_def,
    &bl_watch_def,
    NULL
};


gpio_port_config_t const portA = { GPIOA, {
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
    { BGPIO_MD_ALT,  BGPIO_OUT_PP, BGPIO_SPD_VFST, BGPIO_PULL_UP,   BGPIO_AF0 }, // PA13 = SWDIO
    { BGPIO_MD_ALT,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_DOWN, BGPIO_AF0 }, // PA14 = SWCLK
    { BGPIO_MD_ALT,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_UP,   BGPIO_AF0 }  // PA15 = PWM
}};

gpio_port_config_t const portB = { GPIOB, {
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB0  = BEMF 2
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB1  = opamp 3 out
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB2  = Ifb3 opamp -
    { BGPIO_MD_ALT,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF7 }, // PB3  = USART2 TX
    { BGPIO_MD_ALT,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_UP,   BGPIO_AF7 }, // PB4  = USART2 RX
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB5  = GPIO BEMF
    { BGPIO_MD_BIN,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB6  = ENC PH A / HALL 1
    { BGPIO_MD_BIN,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB7  = ENC PH V / HALL 2
    { BGPIO_MD_BIO,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB8  = ENC PH Z / HALL 3
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB9  = CAN TX
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB10 = NC
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB11 = BEMF 3
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB12 = POTENTIOMETER
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB13 = NC
    { BGPIO_MD_ANA,  BGPIO_OUT_PP, BGPIO_SPD_SLOW, BGPIO_PULL_NONE, BGPIO_AF0 }, // PB14 = TEMPERATURE SENSOR
    { BGPIO_MD_OUT,  BGPIO_OUT_PP, BGPIO_SPD_MED,  BGPIO_PULL_NONE, BGPIO_AF0 }  // PB15 = gate W lo
}};

gpio_port_config_t const portC = { GPIOC, {
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


watch_pin_config_t const watch_pers[] = {
    { BL_TYPE_BIT, "in", "in: %1b " },
    { BL_TYPE_BIT, "oe", "oe: %1b " },
    { BL_TYPE_BIT, "out", "out: %1b " },
    { BL_TYPE_FLOAT, "output", "output: %6.3f\n" },
    { BL_TYPE_BIT, NULL, NULL }
};

char const * const tokens[] = {
  "block",
//    "PortA", "gpio", (char const *)&portA,
//    "PortB", "gpio", (char const *)&portB,
//    "PortC", "gpio", (char const *)&portC,
    "ramp_sum", "sum2",
    "inv_sum", "sum2",
    "timer", "perftimer",
    "watcher", "watch", (char const *)&watch_pers,
    "dir_mux", "mux2",
    "ramp_mux", "mux2",
  "signal",
    "speed", "inv_sum", "in0", "dir_mux", "in0",
    "speed_inv", "inv_sum", "out", "dir_mux", "in1",
    "dir", "bit", 
    "abit", "dir_mux", "sel",
    "ramp", "ramp_mux", "sel",
    "slope", "ramp_sum", "in1", "dir_mux", "out",
    "ramp_gain", "float", "ramp_mux", "out",
    "output", "ramp_sum", "out", "ramp_sum", "in0", "watcher", "output",
    "clocks", "timer", "time",
//    "LED", "PortC", "p10in", "PortC", "p06out",
//    "oe", "PortB", "p08oe", "watcher", "oe",
//    "out", "PortB", "p08out", "watcher", "out",
//    "in", "PortB", "p08in", "watcher", "in",
  "thread",
    "main_thread", "fp", "1000000",
    "timer", "start",
//    "PortB", "read",
//    "PortC", "read",
//    "timer", "stop",
    "inv_sum", "update",
    "dir_mux", "update",
    "ramp_mux", "update",
    "ramp_sum", "update",
//    "PortB", "write",
//    "PortC", "write",
    "watch_thread", "fp", "1000000000",
    "watcher", "update",
//  "show",
//    "thread",
  "unlink",
    "timer", "stop",
//  "show",
//    "main_thread",
  "link",
    "timer", "stop", "main_thread",
//  "show",
//    "thread",
//    "block",
//    "timer",
//    "signal",
//    "oe",
  "unlink",
    "dir_mux", "sel",
//  "show",
//    "signal",
  "link",
    "dir_mux", "sel", "dir",
  "signal",
    "ramp_gain", "ramp_sum", "gain1",
//  "show",
//    "signal",
  "set",
    "ramp", "1",
    "speed", "1.5",
    "inv_sum", "gain0", "-1.0",
    "ramp_sum", "gain0", "1.0",
//    "ramp_mux", "in1", "1.0",
//    "ramp_mux", "out", "-3",
//  "show",
//    "all"
};

#define CLK_MHZ 170

int main (void) {
    char *hello = "\nHello, world!\n";
    uint32_t t_start, t_end, t_init, t_thread;
    struct bl_thread_data_s *main_thread;
    struct bl_thread_data_s *watch_thread;
    char c;
    bl_sig_data_t data;

    platform_init();

    print_string("BOOT\n");
    print_string(hello);
//    print_memory((void *)hello, 512);
    print_string("\n\n");
    bl_show_memory_status();
    print_string("begin parse\n");
    t_start = tsc_read();
    bl_parse_array(tokens, _countof(tokens));
    t_end = tsc_read();
    print_string("parse complete\n");
    t_init = t_end - t_start;
#ifdef PRINT_INIT
    printf("Parse time        Clocks      uSec\n");
    printf("  Total:        %8d  %8d\n\n", t_init, t_init/CLK_MHZ);
    bl_show_memory_status();
//    bl_show_all_blocks();
    bl_show_all_signals();
    bl_show_all_threads();
#endif // PRINT_INIT
    main_thread = bl_thread_get_data(bl_thread_find("main_thread"));
    watch_thread = bl_thread_get_data(bl_thread_find("watch_thread"));
    assert(main_thread != NULL);
    assert(watch_thread != NULL);
    while (1) {
        print_string("ready... ");
        uint start = tsc_read();
        // wait for key pressed
        c = '0';
        while ( ! cons_rx_ready() ) {
            uint elapsed = (uint)tsc_read() - start;
            if ( tsc_to_usec(elapsed) > 1000000 ) {
                print_char(c);
                if ( ++c > '9' ) {
                    c = '0';
                    print_char('\n');
                }
                start = tsc_read();
            }
        }
        // read the key
        c = cons_rx();
        switch(c) {
        case '+':
            // forward
            data.b = 0;
            bl_signal_set(bl_signal_find("dir"), &data);
            break;
        case '-':
            // reverse
            data.b = 1;
            bl_signal_set(bl_signal_find("dir"), &data);
            break;
        case 'g':
            // go
            data.b = 1;
            bl_signal_set(bl_signal_find("ramp"), &data);
            break;
        case 's':
            // stop
            data.b = 0;
            bl_signal_set(bl_signal_find("ramp"), &data);
            break;
        // case 'Z':
        //     data.b = 0;
        //     bl_signal_set(bl_signal_find("oe"), &data);
        //     break;
        // case 'z':
        //     data.b = 1;
        //     bl_signal_set(bl_signal_find("oe"), &data);
        //     break;
        // case 'O':
        //     data.b = 1;
        //     bl_signal_set(bl_signal_find("out"), &data);
        //     break;
        // case 'o':
        //     data.b = 0;
        //     bl_signal_set(bl_signal_find("out"), &data);
        //     break;
        default:
            break;
        }
        print_string("running...");
        t_start = tsc_read();
        bl_thread_run(main_thread, 1);
        t_end = tsc_read();
        print_string("done\n");
        t_thread = t_end - t_start;
        printf("execution time: %d\n", t_thread);
        bl_thread_run(watch_thread,0);
        bl_show_all_signals();
    }
    // Return 0 to satisfy compiler
    return 0;
}

