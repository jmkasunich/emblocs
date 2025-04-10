
#########################################################################################################################################
# Basic Makefile 
# 	- It uses GCC's autodependency feature to maintain a list of dependencies for each source file in the build directory -- this means
# 		it will recompile only the files that need to be recompiled, automatically.
# 	- The majority of the makefile is a defined variable that is evaluated with a set of parameters that can either be set at the bottom
# 		of this file or passed in via the command line. Evaluation happens at the end of the file, with defaults defined just before.
#########################################################################################################################################

# local.mk contains host specific paths, etc
# it should set the following variables:
# BINUTILS_ROOT - path to toolchain
# PACKAGE_ROOT - path to chip-specific packages
# SHELL - path to a UNIX style shell
#
# it might also need to set (and export) PATH so the shell can find utilities like 'rm', etc

include local.mk

# build mode
BUILD_TYPE ?= debug

BUILD_DIR 				:= ../build
OBJ_DIR 				:= $(BUILD_DIR)/obj
DEPS_DIR 				:= $(BUILD_DIR)/deps
TEMP_DIR 				:= $(BUILD_DIR)/temp

ALL_SRCS := 
ALL_TARGETS :=

EMBLOCS_SRCS := emblocs_core.c emblocs_show.c emblocs_parse.c

# target definitions
PRINT_TEST_TARGET := printing-test.hex
PRINT_TEST_SRCS := printing-test.c G431/startup_stm32g431kbtx.s G431/system_stm32g4xx.c G431/platform_g431.c printing.c
PRINT_TEST_LIBS :=
PRINT_TEST_C_SRC := $(filter %.c, $(PRINT_TEST_SRCS))
PRINT_TEST_ASM_SRC := $(filter %.s, $(PRINT_TEST_SRCS))
PRINT_TEST_OBJECTS := $(addprefix $(OBJ_DIR)/, $(notdir $(PRINT_TEST_C_SRC:.c=.o) $(PRINT_TEST_ASM_SRC:.s=.o)))

ALL_SRCS += $(PRINT_TEST_SRCS)
ALL_TARGETS += $(PRINT_TEST_TARGET)




FOO_TARGET := main.hex
FOO_SRCS := G431/main.c G431/startup_stm32g431kbtx.s G431/system_stm32g4xx.c G431/platform_g431.c printing.c $(EMBLOCS_SRCS)
FOO_SRCS += mux2.c sum2.c perftimer.c tmp_gpio.c watch.c
FOO_SRCS += linked_list.c str_to_xx.c
FOO_LIBS :=
FOO_C_SRC := $(filter %.c, $(FOO_SRCS))
FOO_ASM_SRC := $(filter %.s, $(FOO_SRCS))
FOO_OBJECTS := $(addprefix $(OBJ_DIR)/, $(notdir $(FOO_C_SRC:.c=.o) $(FOO_ASM_SRC:.s=.o)))



FOO_PKG := $(PACKAGE_ROOT)/STM32Cube_FW_G4_V1.6.0
SRC_DIRS := . G431

ALL_SRCS += $(FOO_SRCS)
ALL_TARGETS += $(FOO_TARGET)

#BAR_TARGET := bar.hex
#BAR_SRCS := G431/bar.c G431/baz.c G431/main.c

#ALL_SRCS += $(BAR_SRCS)
#ALL_TARGETS += $(BAR_TARGET)

# end of target definitions


# Functions
#find_includes_in_dir = $(shell find $(1) -name "*.h" | sed 's|/[^/]*$$||' | sort -u)

# ---------------------------------------------------------------------
# Toolchain Configuration
# ---------------------------------------------------------------------
TOOLCHAIN               := arm-none-eabi
CC                      := $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-gcc
AS                      := $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-as
OBJCOPY					:= $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-objcopy
SIZE 					:= $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-size
C_STANDARD				:= -std=gnu11


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


FOO = start$(@)end

# Linker
LDFLAGS 				+= $(TOOLCHAIN_SETTINGS) $(DEFS) -Xlinker --gc-sections --specs=nano.specs

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


#SRC_DIRS 				:= G431
#HEADERS 				:= $(foreach dir, $(SRC_DIRS), $(shell find $(dir) -name "*.h"))
#ASM_SRC 				:= $(foreach dir, $(SRC_DIRS), $(shell find $(dir) -name "*.s"))
#C_SRC					:= $(foreach dir, $(SRC_DIRS), $(shell find $(dir) -name "*.c"))

C_SRC					:= $(filter %.c, $(ALL_SRCS))
ASM_SRC					:= $(filter %.s, $(ALL_SRCS))

#INC_DIRS 				:= $(call find_includes_in_dir, $(SRC_DIRS))
INC_DIRS 				:= $(SRC_DIRS)
INC_DIRS				+= $(FOO_PKG)/Drivers/CMSIS/Include
INC_DIRS				+= $(FOO_PKG)/Drivers/CMSIS/Device/ST/STM32G4xx/Include
INC_DIRS				+= $(FOO_PKG)/Drivers/STM32G4xx_HAL_Driver/Inc

OBJECTS                 := $(addprefix $(OBJ_DIR)/, $(notdir $(C_SRC:.c=.o) $(ASM_SRC:.s=.o)))
#LDSCRIPTS				:= $(addprefix -T, $(foreach dir, $(SRC_DIRS), $(shell find $(dir) -name "*.ld")))
LDSCRIPTS				:= -TG431/STM32G431KBTX_FLASH.ld
DIRS 					:= $(BUILD_DIR) $(OBJ_DIR) $(DEPS_DIR) $(TEMP_DIR)
AUTODEPS 				:= $(addprefix $(DEPS_DIR)/, $(notdir $(C_SRC:.c=.d)))

ALL_SRCS := $(sort $(ALL_SRCS))
ALL_TARGETS := $(addprefix $(BUILD_DIR)/, $(ALL_TARGETS))


# RULES

# master rule
all : $(ALL_TARGETS)

# C compilation rule (with dependency tracking

$(OBJ_DIR)/%.o : G431/%.c
	@echo Compiling $(<)
	$(CC) $(C_STANDARD) $(CFLAGS) -c -MMD -MP -MT $(@) -MF $(DEPS_DIR)/$(*F).d $< -o $(@)
	$(SIZE) --format=berkeley $@

$(OBJ_DIR)/%.o : ./%.c
	@echo Compiling $(<)
	$(CC) $(C_STANDARD) $(CFLAGS) -c -MMD -MP -MT $(@) -MF $(DEPS_DIR)/$(*F).d $< -o $(@)
	$(SIZE) --format=berkeley $@


# assembly rule

$(OBJ_DIR)/%.o : G431/%.s
	@echo Assembling $(<)
	$(AS) $(ASFLAGS) $< -o $(@)
	$(SIZE) --format=berkeley $@


# hex file generator rule

%.hex : %.elf
	@echo ' '
	@echo 'Generating: $@'
	@echo 'Invoking: Cross ARM GNU Create Flash Image'
	$(OBJCOPY) -O ihex $< $(@) 
	@echo 'Invoking: Cross ARM GNU Print Size'
	$(SIZE) --format=berkeley $<
	@echo 'Finished building: $@'
	@echo ' '

# linker rule

$(BUILD_DIR)/main.elf : $(FOO_OBJECTS) | $(DIRS)
	@echo ' '
	@echo 'Linking $(@)'
	@echo 'Invoking: Cross ARM C Linker'
	$(CC) \
		-Xlinker -Map=$(patsubst %.elf,%.map,$(@)) \
		$(LDFLAGS) \
		$(LDSCRIPTS) \
		-o $(@) $(FOO_OBJECTS)
	@echo 'Finished linking: $@'

$(BUILD_DIR)/printing-test.elf : $(PRINT_TEST_OBJECTS) | $(DIRS)
	@echo ' '
	@echo 'Linking $(@)'
	@echo 'Invoking: Cross ARM C Linker'
	$(CC) \
		-Xlinker -Map=$(patsubst %.elf,%.map,$(@)) \
		$(LDFLAGS) \
		$(LDSCRIPTS) \
		-o $(@) $(PRINT_TEST_OBJECTS)
	@echo 'Finished linking: $@'

# directory creation rule(s)

$(OBJECTS) : | $(DIRS)

$(DIRS) : 
	@echo Creating $(@)
	mkdir -p $(@)

# extra rules

clean:
	@echo "Cleaning"
	rm -rf *.o
	rm -rf *.d
	rm -rf *.i
	rm -rf *.lst
	rm -rf $(OBJ_DIR)/*.o
	rm -rf $(OBJ_DIR)/*.lst
	rm -rf $(DEPS_DIR)/*.d
	rm -rf $(TEMP_DIR)/*.i
	rm -rf $(TEMP_DIR)/*.s

list :
	@echo 'SRC_DIRS = $(SRC_DIRS)'
	@echo 'BUILD_DIR = $(BUILD_DIR)'
	@echo 'OBJ_DIR = $(OBJ_DIR)'
	@echo 'DEPS_DIR = $(DEPS_DIR)'
	@echo 'INC_DIRS = $(INC_DIRS)'
	@echo 'ALL_SRCS = $(ALL_SRCS)'
	@echo 'ALL_TARGETS = $(ALL_TARGETS)'
	@echo 'ASM_SRC = $(ASM_SRC)'
	@echo 'C_SRC = $(C_SRC)'
	@echo 'OBJECTS = $(OBJECTS)'
	@echo 'PRINT_TEST_OBJECTS = $(PRINT_TEST_OBJECTS)'
	@echo 'LDSCRIPTS = $(LDSCRIPTS)'
	@echo 'DIRS = $(DIRS)'
	@echo 'AUTODEPS = $(AUTODEPS)'

.PHONY : clean all list

.SILENT :


# =======================================================================================================================================
# Build Target Rule 
# - Generate build config using Product Name ($1), Product Root Directory ($2), Build Type ("Debug" or "Release") ($3)
# =======================================================================================================================================
define BUILD_TARGET_RULE
$(eval $(call CONFIG_RULE,$2,$3))

all : $$(BUILD_DIR)/$1.elf $$(BUILD_DIR)/$1.hex

# Tool Invocations
$$(BUILD_DIR)/$1.elf : $$(OBJECTS) | $$(BUILD_DIR)
	@echo ' '
	@echo 'Building $$(@)'
	@echo 'Invoking: Cross ARM C++ Linker'
	$$(CXX) \
		-Xlinker -Map=$$(patsubst %.elf,%.map,$$(@)) \
		$$(LDFLAGS) \
		$$(LDSCRIPTS) \
		-o $$(@) $$(OBJECTS)
	@echo 'Finished building: $$@'
	@echo ' '
	@echo $$(build)

%.hex : %.elf
	@echo 'Invoking: Cross ARM GNU Create Flash Image'
	$$(OBJCOPY) -O ihex $$< $$(@) 
	@echo 'Finished building: $$@'
	@echo ' '
	@echo 'Invoking: Cross ARM GNU Print Size'
	$$(SIZE) --format=berkeley $$<
	@echo 'Finished building: $$@'
	@echo ' '

$$(OBJECTS) : | $$(DIRS)

$$(DIRS) : 
	@echo Creating $$(@)
	@mkdir -p $$(@)

$$(OBJ_DIR)/%.o : %.c
	@echo Compiling $$(<F)
	@$$(CC) $$(C_STANDARD) $$(CFLAGS) -c -MMD -MP $$< -o $$(@)

#$$(OBJ_DIR)/%.o : %.cpp
#	@echo Compiling $$(<F)
#	@$$(CXX) $$(CXX_STANDARD) $$(CXXFLAGS) -c -MMD -MP $$< -o $$(@)

$$(OBJ_DIR)/%.o : %.s
	@echo Assembling $$(<F)
	@$$(AS) $$(ASFLAGS) $$< -o $$(@)




clean :
	@rm -rf $$(PRODUCT_DIR)/Build

.PHONY : clean all

# include by auto dependencies
-include $$(AUTODEPS)

endef
# =======================================================================================================================================
# End BUILD_TARGET_RULE
# =======================================================================================================================================
#########################################################################################################################################
#########################################################################################################################################

-include $(DEPS_DIR)/*.d


# Evaluate Rules Defined Above
#$(eval $(call BUILD_TARGET_RULE,$(PRODUCT),$(PRODUCT_DIR),$(BUILD_TYPE)))


