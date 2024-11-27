#include "platform_g431.h"

#include "emblocs.h"
#include "printing.h"
#include "main.h"

void uart_send_string(char *string);
void uart_send_dec_int(int32_t n);
void uart_send_dec_uint(uint32_t n);

#define countof(foo)  (sizeof(foo)/sizeof(foo[0]))

// component specific stuff, in each component file

// instance data structure - one copy per instance in RAM
typedef struct {
    bl_inst_header_t header;
    bl_float_t *in1;
	bl_float_t *in2;
	bl_float_t *out;
	bl_bit_t *enable;
	float frozen_in2;
	bool old_enable;
} mycomp_inst_t;

// realtime code - one copy in FLASH
void mycomp_funct(bl_inst_header_t *ptr)
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
bl_pin_def_t const mycomp_pins[] = {
    { "in1", BL_PINTYPE_FLOAT, BL_PINDIR_IN, offsetof(mycomp_inst_t, in1)},
    { "in2", BL_PINTYPE_FLOAT, BL_PINDIR_IN, offsetof(mycomp_inst_t, in2)},
    { "out", BL_PINTYPE_FLOAT, BL_PINDIR_OUT, offsetof(mycomp_inst_t, out)},
    { "enable", BL_PINTYPE_BIT, BL_PINDIR_IN, offsetof(mycomp_inst_t, enable)}
};

// function definitions - one copy in FLASH
bl_funct_def_t const mycomp_functs[] = {
    { "funct", &mycomp_funct }
};

// component definition - one copy in FLASH
bl_comp_def_t const mycomp_def = { 
    "mycomp",
    countof(mycomp_pins),
    countof(mycomp_functs),
    sizeof(mycomp_inst_t),
    &(mycomp_pins[0]),
    &(mycomp_functs[0])
};



bl_sigdata_t *bl_free_signal_list = NULL;
bl_inst_header_t *bl_instance_list = NULL;

void add_to_signal_pool(bl_sigdata_t *pool, int entries)
{
    bl_sigdata_t *oldroot;

    while ( entries > 0 ) {
        oldroot = bl_free_signal_list;
        bl_free_signal_list = pool;
        pool->next_free = oldroot;
        pool++;
    }
}

bl_sigdata_t * get_sig_from_pool(void)
{
    bl_sigdata_t *retval;

    retval = bl_free_signal_list;
    if ( retval == NULL ) {
        // handle error here
    }
    bl_free_signal_list = retval->next_free;
    retval->next_free = NULL;
    return retval;
}

void return_sig_to_pool(bl_sigdata_t *sig)
{
    sig->next_free = bl_free_signal_list;
    bl_free_signal_list = sig;
}

void new_inst(bl_comp_def_t *comp_def, bl_inst_header_t *inst_data, char const *name)
{
    bl_pin_def_t const *pin_def;
    bl_sigdata_t *dummy_sig;
    bl_sigdata_t **pin_ptr_addr;

    // fill in instance data
    inst_data->definition = comp_def;
    inst_data->inst_name = name;
    // link new instance into main instance list
    inst_data->next = bl_instance_list;
    bl_instance_list = inst_data;

    // point each pin at a dummy signal and initialize the signal
    pin_def = comp_def->pin_defs;
    for ( int n = 0; n < comp_def->pin_count ; n++ ) {
        dummy_sig = get_sig_from_pool();
        // use char * arithmetic to determine where the pin pointer is stored
        pin_ptr_addr = (bl_sigdata_t **)((char *)(inst_data) + pin_def->offset);
        // point it at the dummy signal
        *pin_ptr_addr = dummy_sig;
        // store an appropriate initial value
        switch ( pin_def->type ) {
            case BL_PINTYPE_BIT:
            dummy_sig->b = 0;
            break;
            case BL_PINTYPE_FLOAT:
            dummy_sig->f = 0.0;
            break;
            case BL_PINTYPE_SINT:
            dummy_sig->s = 0;
            break;
            case BL_PINTYPE_UINT:
            dummy_sig->u = 0U;
            break;
            default:
            // handle error here
            break;
        }
    }
}


void list_all_instances(void)
{
    bl_inst_header_t *inst;

    inst = bl_instance_list;
    while ( inst != NULL ) {
        printf ( "Instance '%s' of type '%s'\n", inst->inst_name, inst->definition->name);
    }
}


void list_all_pins_in_instance(bl_inst_header_t *inst)
{
    bl_sigdata_t *pin_ptr, **pin_ptr_addr;
    bl_pin_def_t const *pindefs = inst->definition->pin_defs;
    int num_pins = inst->definition->pin_count;

    for ( int n = 0 ; n < num_pins ; n++ ) {
        printf ( "  Pin '%s' is type %2d, dir %2d, at offset %3d. Current value is ", 
                pindefs[n].name, pindefs[n].type, pindefs[n].dir, pindefs[n].offset);
        pin_ptr_addr = (bl_sigdata_t **)((char *)(inst) + pindefs[n].offset);
        pin_ptr = *pin_ptr_addr;
        switch ( pindefs[n].type ) {
            case BL_PINTYPE_BIT:
            printf ( "%s\n", pin_ptr->b ? "TRUE" : "FALSE" );
            break;
            case BL_PINTYPE_FLOAT:
            printf ( "float represented by %8x\n", (uint32_t)pin_ptr->f );
            break;
            case BL_PINTYPE_SINT:
            printf ( "%+d\n", pin_ptr->s);
            break;
            case BL_PINTYPE_UINT:
            printf ( "%u\n", pin_ptr->u);
            break;
            default:
            // handle error here
            break;
        }
    }
}




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

