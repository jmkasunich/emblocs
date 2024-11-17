#include "STM32G431xx.h"

#include <stdint.h>

#include "main.h"


// Quick and dirty delay
static void delay (unsigned int time) {
    for (unsigned int i = 0; i < time; i++)
        for (volatile unsigned int j = 0; j < 2000; j++);
}

int main (void) {
    uint32_t reg;
    // Turn on the GPIOC peripheral
    RCC->AHB2ENR |= RCC_AHB2ENR_GPIOCEN;
    // Put pin 6 in general purpose output mode
    reg = LED_PORT->MODER;
    reg &= ~(0x03 << 12);
    reg |= 0x01 << 12;
    LED_PORT->MODER = reg;
    // LED_PORT->MODER |= GPIO_MODER_MODER6_0;

    while (1) {
        // Reset the state of pin 6 to output low
        LED_PORT->BSRR = GPIO_BSRR_BR_6;

        delay(500);

        // Set the state of pin 6 to output high
        LED_PORT->BSRR = GPIO_BSRR_BS_6;

        delay(500);
    }

    // Return 0 to satisfy compiler
    return 0;
}