#include "platform_g431.h"

#include "main.h"

void uart_send_string(char *string);
void uart_send_dec_int(int32_t n);
void uart_send_dec_uint(uint32_t n);


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

    while (1) {
        // Reset the state of pin 6 to output low
        LED_PORT->BSRR = GPIO_BSRR_BR_6;

        delay(500);

        // Set the state of pin 6 to output high
        LED_PORT->BSRR = GPIO_BSRR_BS_6;

        delay(500);
        old_tsc = tsc_read();
        uart_send_string("TSC: ");
        tsc = tsc_read();
        uart_send_dec_uint(tsc - old_tsc);
        uart_send_string("\n");
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


