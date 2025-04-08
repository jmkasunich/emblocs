
EMBLOCS_SRCS = ../emblocs_core.c ../emblocs_parse.c ../emblocs_show.c \
			   ../linked_list.c  ../str_to_xx.c

COMP_SRCS = ../mux2.c ../sum2.c ../perftimer.c ../tmp_gpio.c ../watch.c

SOURCES = main.c \
          startup_stm32g431kbtx.s \
		  system_stm32g4xx.c \
		  platform_g431.c \
		  ../printing.c \
		  $(EMBLOCS_SRCS) \
		  $(COMP_SRCS)

TARGET = main.hex

MCU_PKG = $(PACKAGE_ROOT)/STM32Cube_FW_G4_V1.6.0

INC_DIRS				= .
INC_DIRS 				+= $(SOURCE_DIRS:%/=%)
INC_DIRS				+= $(MCU_PKG)/Drivers/CMSIS/Include
INC_DIRS				+= $(MCU_PKG)/Drivers/CMSIS/Device/ST/STM32G4xx/Include
INC_DIRS				+= $(MCU_PKG)/Drivers/STM32G4xx_HAL_Driver/Inc

# local.mk contains host specific paths, etc
# it should set the following variables:
# BINUTILS_ROOT - path to toolchain
# PACKAGE_ROOT - path to chip-specific packages
# SHELL - path to a UNIX style shell
#
# it might also need to set (and export) PATH so the shell can find utilities like 'rm', etc

include ../local.mk

# ---------------------------------------------------------------------
# Toolchain Configuration
# ---------------------------------------------------------------------
TOOLCHAIN               := arm-none-eabi
CC                      := $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-gcc
AS                      := $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-as
OBJCOPY					:= $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-objcopy
SIZE 					:= $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-size
C_STANDARD				:= -std=gnu11

BUILD_DIR				:= ./build
OBJECT_DIR				:= $(BUILD_DIR)/obj
DEPS_DIR				:= $(BUILD_DIR)/dep
TEMP_DIR				:= $(BUILD_DIR)/tmp
DIRS					:= $(BUILD_DIR) $(OBJECT_DIR) $(DEPS_DIR) $(TEMP_DIR)


C_SOURCES				:= $(filter %.c, $(SOURCES))
ASM_SOURCES				:= $(filter %.s, $(SOURCES))
SOURCE_DIRS				:= $(sort $(dir $(SOURCES)))
OBJECTS                 := $(addprefix $(OBJECT_DIR)/, $(notdir $(C_SOURCES:.c=.o) $(ASM_SOURCES:.s=.o)))
DIRS 					:= $(BUILD_DIR) $(OBJECT_DIR) $(DEPS_DIR) $(TEMP_DIR)

# tell make where to find each source file by setting individual vpaths for each one
FOO := $(foreach SRC, $(SOURCES), $(eval vpath $(notdir $(SRC)) $(dir $(SRC))))

# -----------------------------------------------------------------------------------------------------------------
# Defined Symbols
# -----------------------------------------------------------------------------------------------------------------
#DEFS 					:= -DSTM32F43xx -DUSE_HAL_DRIVER -DARM_MATH_CM4 -D__FPU_PRESENT=1U -DHSE_VALUE=25000000
DEFS 					:= -DSTM32G431xx -DARM_MATH_CM4 -D__FPU_PRESENT=1U -DHSE_VALUE=8000000


# ---------------------------------------------------------------------------------------------------------------------------------------
# Compiler & Linker Flags
# ---------------------------------------------------------------------------------------------------------------------------------------
# Flags sent to all tools in the Toolchain 
TOOLCHAIN_SETTINGS 		:= -mcpu=cortex-m4 -march=armv7e-m -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 
TOOLCHAIN_SETTINGS 		+= -fmessage-length=0 -ffunction-sections -fdata-sections

# C Compiler -- main args 
CFLAGS 					+= $(TOOLCHAIN_SETTINGS) $(DEFS)

# C Compiler -- include paths

CFLAGS	+= $(addprefix -I, $(INC_DIRS))

# C compiler -- other options

#CFLAGS += -pipe
CFLAGS += -save-temps -dumpdir $(TEMP_DIR)/

# C Compiler -- warnings
CFLAGS                  += -Wall
CFLAGS 					+= -Wextra
CFLAGS 					+= -Wfatal-errors
CFLAGS 					+= -Wpacked
CFLAGS 					+= -Winline
CFLAGS 					+= -Wfloat-equal
CFLAGS 					+= -Wconversion
CFLAGS 					+= -Wlogical-op
CFLAGS 					+= -Wpointer-arith
CFLAGS 					+= -Wdisabled-optimization
CFLAGS                	+= -Wunused-parameter
CFLAGS					+= -Wno-sign-conversion
CFLAGS					+= -Wstrict-aliasing=1
# Assembler settings
CFLAGS                  += -Wa,-alh=$(@:.o=.lst)

# Linker
LDFLAGS 				+= $(TOOLCHAIN_SETTINGS) $(DEFS) -Xlinker --gc-sections --specs=nano.specs
LDSCRIPTS				:= -TSTM32G431KBTX_FLASH.ld


# -------------------------------------------------------------
# Build Type Modifiers
# -------------------------------------------------------------
# Debug
DEFS_DEBUG 				+= -DDEBUG
CFLAGS_DEBUG            += -ggdb -g1 -Og
LDFLAGS_DEBUG			+= --specs=rdimon.specs -Og 

# Release
CFLAGS_RELEASE			+= -Os
LDFLAGS_RELEASE 		+= --specs=nosys.specs


ifeq (BUILD_TYPE, release)
	DEFS 	+= $(DEFS_RELEASE)
	CFLAGS 	+= $(CFLAGS_RELEASE)
	LDFLAGS += $(LDFLAGS_RELEASE)
else 
	DEFS 	+= $(DEFS_DEBUG)
	CFLAGS 	+= $(CFLAGS_DEBUG)
	LDFLAGS += $(LDFLAGS_DEBUG)
endif


# master rule
all : $(BUILD_DIR)/$(TARGET)

# rule to generate hex file
$(BUILD_DIR)/%.hex : $(BUILD_DIR)/%.elf
	@echo ' '
	@echo 'Generating: $@'
	@echo 'Invoking: Cross ARM GNU Create Flash Image'
	$(OBJCOPY) -O ihex $< $(@) 
	@echo 'Invoking: Cross ARM GNU Print Size'
	$(SIZE) --format=berkeley $<
	@echo 'Finished building: $@'
	@echo ' '


# linker rule
$(BUILD_DIR)/$(TARGET:.hex=.elf) : $(OBJECTS)
	@echo ' '
	@echo 'Linking $(@)'
	@echo 'Invoking: Cross ARM C Linker'
	$(CC) \
		-Xlinker -Map=$(patsubst %.elf,%.map,$(@)) \
		$(LDFLAGS) \
		$(LDSCRIPTS) \
		-o $(@) $(OBJECTS)
	@echo 'Finished linking: $@'


# rule to compile .c files
$(OBJECT_DIR)/%.o : %.c | $(DIRS)
	@echo Compiling $(<)
	$(CC) $(C_STANDARD) $(CFLAGS) -c -MMD -MP -MT $(@) -MF $(DEPS_DIR)/$(*F).d $< -o $(@)
	$(SIZE) --format=berkeley $@


# rule to assemble .s files
$(OBJECT_DIR)/%.o : %.s | $(DIRS)
	@echo Assembling $(<)
	$(AS) $(ASFLAGS) $< -o $(@)
	$(SIZE) --format=berkeley $@


# rule to create build directories
$(DIRS) : 
	@echo Creating $(@)
	mkdir -p $(@)


list :
	@echo 'TARGET = $(TARGET)'
	@echo 'SOURCES = $(SOURCES)'
	@echo 'ASM_SOURCES = $(ASM_SOURCES)'
	@echo 'C_SOURCES = $(C_SOURCES)'
	@echo 'SOURCE_DIRS = $(SOURCE_DIRS)'
	@echo 'OBJECTS = $(OBJECTS)'
	@echo 'INC_DIRS = $(INC_DIRS)'
	@echo 'BUILD_DIR = $(BUILD_DIR)'
	@echo 'OBJECT_DIR = $(OBJECT_DIR)'
	@echo 'DEPS_DIR = $(DEPS_DIR)'
	@echo 'TEMP_DIR = $(TEMP_DIR)'
	@echo 'DIRS = $(DIRS)'
	@echo 'LDSCRIPTS = $(LDSCRIPTS)'
	@echo 'CFLAGS = $(CFLAGS)'


clean:
	@echo "Cleaning"
	rm -rf $(BUILD_DIR)/*.elf
	rm -rf $(BUILD_DIR)/*.hex
	rm -rf $(BUILD_DIR)/*.map
	rm -rf $(OBJECT_DIR)/*.o
	rm -rf $(OBJECT_DIR)/*.lst
	rm -rf $(DEPS_DIR)/*.d
	rm -rf $(TEMP_DIR)/*.i
	rm -rf $(TEMP_DIR)/*.s


.PHONY : clean all list

# include auto dependencies
-include $(DEPS_DIR)/*.d

.SILENT :

