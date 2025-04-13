# directory containing the currently included header.mk
# this is the very top of the tree, no more climbing
TOPDIR := $(dir $(lastword $(MAKEFILE_LIST)))

# Disable built-in rules and variables
MAKEFLAGS += --no-builtin-rules
MAKEFLAGS += --no-builtin-variables
.SUFFIXES :

# Avoid excess printing
.SILENT :

# local.mk contains host specific paths, etc
# it should set the following variables:
# BINUTILS_ROOT - path to toolchain
# PACKAGE_ROOT - path to chip-specific packages
# SHELL - path to a UNIX style shell
#
# it might also need to set (and export) PATH so the shell can find utilities like 'rm', etc

include $(TOPDIR)local.mk

#append this directory to the source search path
SRC_PATH += $(TOPDIR)

# tell make to use the path only for .c and .s files
SET_VPATH := $(eval vpath %.c $(SRC_PATH))
SET_VPATH := $(eval vpath %.s $(SRC_PATH))



# ---------------------------------------------------------------------
# Toolchain Configuration
# ---------------------------------------------------------------------
TOOLCHAIN		:= arm-none-eabi
CC				:= $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-gcc
AS				:= $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-as
OBJCOPY			:= $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-objcopy
SIZE			:= $(BINUTILS_ROOT)/bin/$(TOOLCHAIN)-size
C_STANDARD		:= -std=gnu11

# ---------------------------------------------------------------------
# Directories - when make is invoked in a project directory, all build
# products are stored in a subdirectory of that project, even if the 
# source files come from elsewhere in the tree.  This allows each
# project to re-build common code with project-specific configuration
# and compiler flags.
# ---------------------------------------------------------------------

BUILD_DIR		:= ./build
OBJECT_DIR		:= $(BUILD_DIR)/obj
DEPS_DIR		:= $(BUILD_DIR)/dep
TEMP_DIR		:= $(BUILD_DIR)/tmp
DIRS			:= $(BUILD_DIR) $(OBJECT_DIR) $(DEPS_DIR) $(TEMP_DIR)

# define object file groups that projects might want to use

EMBLOCS_OBJS := emblocs_core.o emblocs_parse.o emblocs_show.o \
			    linked_list.o str_to_xx.o

COMP_OBJS := mux2.o sum2.o perftimer.o tmp_gpio.o watch.o
