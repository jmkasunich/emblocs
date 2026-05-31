/*********************************************
 *
 * GPIO management:
 *
 * This component only manages GPIOs that have emblocs pins.
 * It takes a personality that consists of two 32-bit words.
 * The first word has a bit set if the corresponding pin should
 * be an emblocs input (emblocs pin that tracks the hardware pin).
 * The second word has a bit set if the corresponding pin should
 * be an emblocs output (emblocs pin that controls the hardware
 * pin).
 * If the same bit is set in both words, the hardware pin is
 * bidirectional and an output enable emblocs pin is created.
 *
 * This component is a singleton; the RP2040 has 30 I/O pins.
 *
 *
 */

#ifndef RP2040_GPIO_H
#define RP2040_GPIO_H

typedef struct {
    uint32_t input_pins;
    uint32_t output_pins;
} rp2040_gpio_config_t;

#endif // RP2040_GPIO_H
