# makefile for doing a dummy compile of profiler code

# Usage: make CPU=cortex-m4     (STM32G431)
#        make CPU=cortex-m0plus (RP2040)

CC      := arm-none-eabi-gcc
OBJDUMP := arm-none-eabi-objdump
SIZE    := arm-none-eabi-size
DOXYGEN := doxygen

CPU        ?= cortex-m0
BUILD := build/$(CPU)
TARGET := $(BUILD)/main

SRC := profiler.c profiler_sampler.S profiler_dummy.c
OBJ := $(SRC)
OBJ := $(OBJ:.c=.o)
OBJ := $(OBJ:.S=.o)
OBJ := $(addprefix $(BUILD)/,$(OBJ))
DEP := $(OBJ:.o=.d)
OBJLST := $(OBJ:.o=.lst)

DOCDIR  := build/doc

ARCH := -mcpu=$(CPU) -mthumb -mfloat-abi=soft

CFLAGS   := $(ARCH) -std=gnu11 -O2 -g -Wall -Wextra \
            -ffunction-sections -fdata-sections
ASFLAGS  := $(ARCH)
LDFLAGS  := $(ARCH) -nostdlib -Wl,--gc-sections \
            -Wl,--entry=setup -Wl,-Map=$(TARGET).map
CPPFLAGS := -I.
DEPFLAGS := -MMD -MP

.PHONY: all size clean doc
all: $(TARGET).elf $(TARGET).lst $(OBJLST) size

$(BUILD):
	mkdir -p $@

$(BUILD)/%.o: %.S | $(BUILD)
	$(CC) $(ASFLAGS) $(DEPFLAGS) $(CPPFLAGS) -c $< -o $@

$(BUILD)/%.o: %.c | $(BUILD)
	$(CC) $(CFLAGS) $(DEPFLAGS) $(CPPFLAGS) -c $< -o $@

$(BUILD)/%.lst: $(BUILD)/%.o
	$(OBJDUMP) -dS -l $< > $@

$(TARGET).elf: $(OBJ)
	$(CC) $(LDFLAGS) $(OBJ) -o $@

$(TARGET).lst: $(TARGET).elf
	$(OBJDUMP) -dS -l $< > $@

size: $(TARGET).elf
	$(SIZE) $<

doc: Doxyfile profiler.h profiler_config.h
	$(DOXYGEN) Doxyfile

clean:
	rm -rf build

-include $(DEP)
