#include "platform_g431.h"

#include "emblocs_api.h"
#include "printing.h"
#include <assert.h>
#include "tmp_gpio.h"
#include "watch.h"

#define NEW_INIT
//#define OLD_INIT
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

#ifdef NEW_INIT

char const * const tokens[] = {
  "instance",
    "PortA", (char const *)&bl_gpio_def, (char const *)&portA,
    "PortB", (char const *)&bl_gpio_def, (char const *)&portB,
    "PortC", (char const *)&bl_gpio_def, (char const *)&portC,
    "ramp_sum", (char const *)&bl_sum2_def, NULL,
    "inv_sum", (char const *)&bl_sum2_def, NULL,
    "timer", (char const *)&bl_perftimer_def, NULL,
    "watcher", (char const *)&bl_watch_def, (char const *)&watch_pers,
    "dir_mux", (char const *)&bl_mux2_def, NULL,
    "ramp_mux", (char const *)&bl_mux2_def, NULL,
  "signal",
    "speed", "dir_mux", "in0", "inv_sum", "in0",
    "speed_inv", "inv_sum", "out", "dir_mux", "in1",
    "dir", "bit", 
    "abit", "dir_mux", "sel",
    "ramp", "ramp_mux", "sel",
    "slope", "dir_mux", "out", "ramp_sum", "in1",
    "ramp_gain", "ramp_mux", "out",
    "output", "ramp_sum", "out", "ramp_sum", "in0", "watcher", "output",
    "clocks", "timer", "time",
    "LED", "PortC", "p10in", "PortC", "p06out",
    "oe", "PortB", "p08oe", "watcher", "oe",
    "out", "PortB", "p08out", "watcher", "out",
    "in", "PortB", "p08in", "watcher", "in",
  "thread",
    "main_thread", "fp", "1000000",
    "timer", "start",
    "PortB", "read",
    "PortC", "read",
    "timer", "stop",
    "inv_sum", "update",
    "dir_mux", "update",
    "ramp_mux", "update",
    "ramp_sum", "update",
    "PortB", "write",
    "PortC", "write",
    "watch_thread", "fp", "1000000000",
    "watcher", "update",
  "show",
    "thread",
  "unlink",
    "timer", "stop",
  "show",
    "main_thread",
  "link",
    "timer", "stop", "main_thread",
  "show",
    "thread",
    "instance",
    "timer",
    "signal",
    "oe",
  "unlink",
    "dir_mux", "sel",
  "show",
    "signal",
  "link",
    "dir_mux", "sel", "dir",
  "signal",
    "ramp_gain", "ramp_sum", "gain1",
  "show",
    "signal",
  "set",
    "ramp", "1",
    "speed", "1.5",
    "inv_sum", "gain0", "-1.0",
    "ramp_sum", "gain0", "1.0",
    "ramp_mux", "in1", "1.0",
    "ramp_mux", "out", "-3",
  "show",
    "signal"
};

#endif // NEW_INIT

#ifdef OLD_INIT

bl_instance_def_t const instances[] = {
    { "PortA", &bl_gpio_def, &portA},
    { "PortB", &bl_gpio_def, &portB},
    { "PortC", &bl_gpio_def, &portC},
    { "watcher", &bl_watch_def, &watch_pers},
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
    "FLOAT", "output", "ramp_sum", "out", "ramp_sum", "in0", "watcher", "output",
    "U32", "clocks", "timer", "time",
    "BIT", "LED", "PortC", "p10in", "PortC", "p06out",
    "BIT", "oe", "PortB", "p08oe", "watcher", "oe",
    "BIT", "out", "PortB", "p08out", "watcher", "out",
    "BIT", "in", "PortB", "p08in", "watcher", "in",
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
    "PortB", "read",
    "PortC", "read",
    "inv_sum", "update",
    "dir_mux", "update",
    "ramp_mux", "update",
    "ramp_sum", "update",
    "PortB", "write",
    "PortC", "write",
    "timer", "stop",
    "HAS_FP", "1000000000", "watch_thread",
    "watcher", "update",
    NULL
};

#endif // OLD_INIT

#define CLK_MHZ 170

int main (void) {
    char *hello = "\nHello, world!\n";
    uint32_t t_start, t_inst, t_nets, t_setsig, t_setpin, t_threads, t_total;
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
#ifdef OLD_INIT
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
#ifdef PRINT_INIT
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
#endif // PRINT_INIT
#endif // OLD_INIT
#ifdef NEW_INIT
    print_string("begin parse\n");
    t_start = tsc_read();
    bl_parse_array(tokens, _countof(tokens));
    t_total = tsc_read();
    print_string("parse complete\n");
    t_total -= t_start;
#ifdef PRINT_INIT
    printf("Parse time        Clocks      uSec\n");
    printf("  Total:        %8d  %8d\n\n", t_total, t_total/CLK_MHZ);
    bl_show_memory_status();
    bl_show_all_instances();
    bl_show_all_signals();
    bl_show_all_threads();
#endif // PRINT_INIT
#endif // NEW_INIT
    main_thread = bl_thread_get_data(bl_thread_find("main_thread"));
    watch_thread = bl_thread_get_data(bl_thread_find("watch_thread"));
    assert(main_thread != NULL);
    assert(watch_thread != NULL);
    while (1) {
        print_string("ready... ");
        // wait for key pressed
        while ( ! cons_rx_ready() );
        // read the key
        c = cons_rx();
        switch(c) {
        case '+':
            data.b = 0;
            bl_signal_set(bl_signal_find("dir"), &data);
            break;
        case '-':
            data.b = 1;
            bl_signal_set(bl_signal_find("dir"), &data);
            break;
        case 'g':
            data.b = 1;
            bl_signal_set(bl_signal_find("ramp"), &data);
            break;
        case 's':
            data.b = 0;
            bl_signal_set(bl_signal_find("ramp"), &data);
            break;
        case 'Z':
            data.b = 0;
            bl_signal_set(bl_signal_find("oe"), &data);
            break;
        case 'z':
            data.b = 1;
            bl_signal_set(bl_signal_find("oe"), &data);
            break;
        case 'O':
            data.b = 1;
            bl_signal_set(bl_signal_find("out"), &data);
            break;
        case 'o':
            data.b = 0;
            bl_signal_set(bl_signal_find("out"), &data);
            break;
        default:
            break;
        }
        print_string("running...");
        t_start = tsc_read();
        bl_thread_run(main_thread, 1);
        t_threads = tsc_read();
        print_string("done\n");
        t_threads -= t_start;
        printf("execution time: %d\n", t_threads);
        bl_thread_run(watch_thread,0);
        bl_show_all_signals();
    }
    // Return 0 to satisfy compiler
    return 0;
}

