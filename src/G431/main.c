#include "platform_g431.h"

#include "emblocs.h"
#include "main.h"

void uart_send_string(char *string);
void uart_send_dec_int(int32_t n);
void uart_send_dec_uint(uint32_t n);

#define countof(foo)  (sizeof(foo)/sizeof(foo[0]))

/******************************************/
// generic stuff (will eventually be in emblocs.h)
typedef struct {
    char const * const name;
    bl_pintype_t const type;
    bl_pindir_t const dir;
    int const offset;
} pin_def_t;

typedef struct {
    char const * const name;
    int const pincount;
    pin_def_t const *pindefs;
} comp_def_t;

/******************************************/
// component specific stuff, in each component file

// instance data structure - one copy per instance in RAM
typedef struct {
// probably want a generic sub-structure with the commented out items
//    char const *inst_name;
//    comp_def_t definition;
    bl_float_t *in1;
	bl_float_t *in2;
	bl_float_t *out;
	bl_bit_t *enable;
	float frozen_in2;
	bool old_enable;
} mycomp_inst_t;

// realtime code - one copy in FLASH
void mycomp_funct(mycomp_inst_t *p)
{
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
    { "out", BL_PINTYPE_FLOAT, BL_PINDIR_IN, offsetof(mycomp_inst_t, out)},
    { "enable", BL_PINTYPE_FLOAT, BL_PINDIR_IN, offsetof(mycomp_inst_t, enable)},
};

// component definition - one copy in FLASH
comp_def_t const mycomp_def = { 
    "mycomp",
    countof(mycomp_pins),
    mycomp_pins
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
    uint32_t old_tsc = 0, tsc;

    platform_init();
    // Put pin PC6 in general purpose output mode
    reg = LED_PORT->MODER;
    reg &= ~GPIO_MODER_MODE6_Msk;
    reg |= 0x01 << GPIO_MODER_MODE6_Pos;
    LED_PORT->MODER = reg;
    
    uart_send_string("Hello, world\n");

    uart_send_dec_uint(&mycomp_def);

    

    while (1) {
        // Reset the state of pin 6 to output low
        LED_PORT->BSRR = GPIO_BSRR_BR_6;

        delay(500);
        if ( cons_rx_ready() ) {
          cons_tx_wait(cons_rx());
        }
        // Set the state of pin 6 to output high
        LED_PORT->BSRR = GPIO_BSRR_BS_6;

        delay(500);
        if ( cons_rx_ready() ) {
          cons_tx_wait(cons_rx());
        }
        old_tsc = tsc_read();
        uart_send_string("TSC: ");
        tsc = tsc_read();
        uart_send_string("sending took ");
        uart_send_dec_uint(tsc-old_tsc);
        uart_send_string(" clocks, or ");
        uart_send_dec_uint(tsc_to_usec(tsc-old_tsc));
        uart_send_string(" microseconds\n");
        old_tsc = tsc;
    }

    // Return 0 to satisfy compiler
    return 0;
}


void uart_send_string(char *string)
{
    if ( string == NULL ) return;
    while ( *string != '\0' ) {
        cons_tx_wait(*string);
        string++;
    }
}

void uart_send_dec_int(int32_t n)
{
    if ( n < 0 ) {
        cons_tx_wait('-');
        uart_send_dec_uint(-n);
    } else {
        uart_send_dec_uint(n);
    }
}

void uart_send_dec_uint(uint32_t n)
{
    char buffer[11], *cp;
    int digit;

    // point to end of buffer
    cp = &buffer[10];
    *(cp--) = '\0';
    // first digit must always be printed
    digit = n % 10;
    n = n / 10;
    *(cp--) = (char)('0' + digit);
    // loop till no more digits
    while ( n > 0 ) {
        digit = n % 10;
        n = n / 10;
        *(cp--) = (char)('0' + digit);
    }
    cp++;
    uart_send_string(cp);
}


