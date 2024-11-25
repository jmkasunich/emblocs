#include "platform_g431.h"

#include "emblocs.h"
#include "printing.h"
#include "main.h"

void uart_send_string(char *string);
void uart_send_dec_int(int32_t n);
void uart_send_dec_uint(uint32_t n);

#define countof(foo)  (sizeof(foo)/sizeof(foo[0]))

/******************************************/
// generic stuff (will eventually be in emblocs.h)
typedef struct inst_data_s {
    char const *inst_name;
    struct comp_def_s *definition;
    struct inst_data_s *next;
} inst_data_t;

typedef struct pin_def_s {
    char const * const name;
    bl_pintype_t const type;
    bl_pindir_t const dir;
    int const offset;
} pin_def_t;

typedef struct funct_def_s {
    char const * const name;
    void (*fp) (inst_data_t *);
} funct_def_t;

typedef struct comp_def_s {
    char const * const name;
    int const pin_count;
    pin_def_t const *pin_defs;
    int const funct_count;
    funct_def_t const *funct_defs;
} comp_def_t;

/******************************************/
// component specific stuff, in each component file

// instance data structure - one copy per instance in RAM
typedef struct {
    inst_data_t header;
    bl_float_t *in1;
	bl_float_t *in2;
	bl_float_t *out;
	bl_bit_t *enable;
	float frozen_in2;
	bool old_enable;
} mycomp_inst_t;

// realtime code - one copy in FLASH
void mycomp_funct(inst_data_t *ptr)
{
    mycomp_inst_t *p = (mycomp_inst_t *)ptr;
    if ( *(p->enable) ) {
    *(p->out) = *(p->in1) + *(p->in2);
    } else {
        if ( p->old_enable ) {
            p->frozen_in2 = *(p->in2);
        }
        *(p->out) = *(p->in1) + p->frozen_in2;
    }
    p->old_enable = *(p->enable);
}
// pin definitions - one copy in FLASH
pin_def_t const mycomp_pins[] = {
    { "in1", BL_PINTYPE_FLOAT, BL_PINDIR_IN, offsetof(mycomp_inst_t, in1)},
    { "in2", BL_PINTYPE_FLOAT, BL_PINDIR_IN, offsetof(mycomp_inst_t, in2)},
    { "out", BL_PINTYPE_FLOAT, BL_PINDIR_OUT, offsetof(mycomp_inst_t, out)},
    { "enable", BL_PINTYPE_BIT, BL_PINDIR_IN, offsetof(mycomp_inst_t, enable)}
};

// function definitions - one copy in FLASH
funct_def_t const mycomp_functs[] = {
    { "funct", &mycomp_funct }
};

// component definition - one copy in FLASH
comp_def_t const mycomp_def = { 
    "mycomp",
    countof(mycomp_pins),
    mycomp_pins,
    countof(mycomp_functs),
    mycomp_functs
};


// call in main during startup:
// register_comp(&mycomp_def)

// call in main during startup:
//   new_inst(&mycomp_def, "instancename")
// or
//   new_inst("compname", "instancename")
// the latter would search for compname in a list built by register_comp()








#if 1
# define assert(_p) (_assert(__FILE__, __LINE__, _p))
#else
# define assert(_p) do {} while(1)  // just loop forever
#endif

void _assert(char *file, int line, char *msg)
{
    // is the UART running?
    if ( USART2->CR1 & USART_CR1_UE ) {
        // yes, print something
        uart_send_string("assert(): ");
        uart_send_string(file);
        uart_send_string(":");
        uart_send_dec_int(line);
        if ( msg != NULL ) {
            uart_send_string(" : ");
            uart_send_string(msg);
        }
        uart_send_string("\n");
    }
    // loop forever
    do {} while (1);
}


// Quick and dirty delay
static void delay (unsigned int time) {
    for (unsigned int i = 0; i < time; i++)
        for (volatile unsigned int j = 0; j < 20000; j++);
}

int main (void) {
    uint32_t reg;

    platform_init();
    // Put pin PC6 in general purpose output mode
    reg = LED_PORT->MODER;
    reg &= ~GPIO_MODER_MODE6_Msk;
    reg |= 0x01 << GPIO_MODER_MODE6_Pos;
    LED_PORT->MODER = reg;
    
    printf("\nhello world\n");
    printf("mycomp_def is at %p, has %d pins at %p\n", 
        &mycomp_def, mycomp_def.pin_count, mycomp_def.pin_defs);
    printf("and a function at %p\n", mycomp_funct);
    //print_ptr(&mycomp_def, 8);
    print_memory((void *)0x08000A00, 384);

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

