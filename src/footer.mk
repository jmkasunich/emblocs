# use a stack to track what directory the current .mk file is in
STACK += $(lastword $(MAKEFILE_LIST))
THISDIR := $(dir $(lastword $(STACK)))

# processing of source file list 'SOURCES'

C_SOURCES		:= $(filter %.c, $(SOURCES))
ASM_SOURCES		:= $(filter %.s, $(SOURCES))
SOURCE_DIRS		:= $(sort $(dir $(SOURCES)))
OBJECTS			:= $(addprefix $(OBJECT_DIR)/, $(notdir $(C_SOURCES:.c=.o) $(ASM_SOURCES:.s=.o)))

# tell make where to find each source file by setting individual vpaths for each one
SET_VPATH 		:= $(foreach SRC, $(SOURCES), $(eval vpath $(notdir $(SRC)) $(dir $(SRC))))

# C Compiler -- main args 
CFLAGS 			+= $(TOOLCHAIN_SETTINGS) $(DEFS)
# C Compiler -- include paths
CFLAGS			+= $(addprefix -I, $(INC_DIRS))
# C compiler -- save preprocessor and assembler intermediate files
CFLAGS			+= -save-temps -dumpdir $(TEMP_DIR)/
# C Compiler -- warnings
CFLAGS			+= -Wall
CFLAGS			+= -Wextra
CFLAGS			+= -Wfatal-errors
CFLAGS			+= -Wpacked
CFLAGS			+= -Winline
CFLAGS			+= -Wfloat-equal
CFLAGS			+= -Wconversion
CFLAGS			+= -Wlogical-op
CFLAGS			+= -Wpointer-arith
CFLAGS			+= -Wdisabled-optimization
CFLAGS			+= -Wunused-parameter
CFLAGS			+= -Wno-sign-conversion
CFLAGS			+= -Wstrict-aliasing=1
# Assembler settings
CFLAGS			+= -Wa,-alh=$(@:.o=.lst)

# Linker
LDFLAGS			+= $(TOOLCHAIN_SETTINGS) $(DEFS) -Xlinker --gc-sections
LDFLAGS			+= --specs=nano.specs

# rules and recipes for common targets

# master rule
all : $(BUILD_DIR)/$(TARGET)

.PHONY : all

# generate hex file
$(BUILD_DIR)/%.hex : $(BUILD_DIR)/%.elf
	@echo ' '
	@echo 'Generating: $@'
	@echo 'Invoking: Cross ARM GNU Create Flash Image'
	$(OBJCOPY) -O ihex $< $(@) 
	@echo 'Invoking: Cross ARM GNU Print Size'
	$(SIZE) --format=berkeley $<
	@echo 'Finished building: $@'
	@echo ' '


# link the target
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


# compile .c files (with dependency tracking)
$(OBJECT_DIR)/%.o : %.c | $(DIRS)
	@echo Compiling $(<)
	$(CC) $(C_STANDARD) $(CFLAGS) -c -MMD -MP -MT $(@) -MF $(DEPS_DIR)/$(*F).d $< -o $(@)
	$(SIZE) --format=berkeley $@


# assemble .s files
$(OBJECT_DIR)/%.o : %.s | $(DIRS)
	@echo Assembling $(<)
	$(AS) $(ASFLAGS) $< -o $(@)
	$(SIZE) --format=berkeley $@


# create build directories
$(DIRS) : 
	@echo Creating $(@)
	mkdir -p $(@)

# clean up build directories
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

.PHONY : clean

# include auto dependencies
-include $(DEPS_DIR)/*.d

# pop this .mk file off the stack
STACK := $(subst $(lastword $(STACK)),,$(STACK))
THISDIR := $(dir $(lastword $(STACK)))
