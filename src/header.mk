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

include ../local.mk

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

# define source file groups that projects might want to use

EMBLOCS_SRCS := ../emblocs_core.c ../emblocs_parse.c ../emblocs_show.c \
			   ../linked_list.c  ../str_to_xx.c

COMP_SRCS := ../mux2.c ../sum2.c ../perftimer.c ../tmp_gpio.c ../watch.c

