# makefile for doing a dummy compile of profiler code

# Usage: make CPU=cortex-m4     (STM32G431)
#        make CPU=cortex-m0plus (RP2040)

CC      := arm-none-eabi-gcc
OBJDUMP := arm-none-eabi-objdump
SIZE    := arm-none-eabi-size

CPU   ?= cortex-m4
BUILD := build/$(CPU)
TARGET := $(BUILD)/profiler

SRC := profiler.c profiler_stubs.c
OBJ := $(addprefix $(BUILD)/,$(SRC:.c=.o))

ARCH   := -mcpu=$(CPU) -mthumb -mfloat-abi=soft
CFLAGS := $(ARCH) -std=gnu11 -O2 -g -Wall -Wextra \
          -ffunction-sections -fdata-sections
LDFLAGS := $(ARCH) -nostdlib -Wl,--gc-sections \
           -Wl,--entry=setup -Wl,-Map=$(TARGET).map

.PHONY: all size clean
all: $(TARGET).elf $(TARGET).lst size

$(BUILD):
	mkdir -p $@

$(BUILD)/%.o: %.S | $(BUILD)
	$(CC) $(ARCH) $(DEFS) -c $< -o $@

$(BUILD)/%.o: %.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(TARGET).elf: $(OBJ)
	$(CC) $(LDFLAGS) $(OBJ) -o $@

$(TARGET).lst: $(TARGET).elf
	$(OBJDUMP) -dS -l $< > $@

size: $(TARGET).elf
	$(SIZE) $<

clean:
	rm -rf build
