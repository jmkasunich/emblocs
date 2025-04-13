# source search always starts in the project directory
SRC_PATH := .

# include common make variables, paths, etc, from the next level up
# this will recurse all the way to the top of the repo tree
# and will set TOPDIR for later
include ../header.mk

# info for this project

OBJECTS := main.o \
           startup_stm32g431kbtx.o \
		   system_stm32g4xx.o \
		   platform_g431.o \
		   printing.o \
		   $(EMBLOCS_OBJS) \
		   $(COMP_OBJS)

# objects aren't built here; prepend the object directory
OBJECTS := $(addprefix $(OBJECT_DIR)/,$(OBJECTS))

TARGET := main.hex

MCU_PKG := $(PACKAGE_ROOT)/STM32Cube_FW_G4_V1.6.0

INC_DIRS 				:= $(SRC_PATH:%/=%)
INC_DIRS				+= $(MCU_PKG)/Drivers/CMSIS/Include
INC_DIRS				+= $(MCU_PKG)/Drivers/CMSIS/Device/ST/STM32G4xx/Include
INC_DIRS				+= $(MCU_PKG)/Drivers/STM32G4xx_HAL_Driver/Inc

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

LDSCRIPTS				:= -TSTM32G431KBTX_FLASH.ld

# -------------------------------------------------------------
# Debug info
# -------------------------------------------------------------

DEFS 		+= -DDEBUG
CFLAGS		+= -ggdb -g1 -Og
LDFLAGS		+= --specs=rdimon.specs -Og
#LDFLAGS		+= --specs=nosys.specs -Og
#LDFLAGS		+= -nolibc -nostartfiles -Og

# include common make recipies, etc, from the top of the repo tree
include $(TOPDIR)include.mk
