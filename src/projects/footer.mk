# use a stack to track what directory the current .mk file is in
STACK += $(lastword $(MAKEFILE_LIST))
THISDIR := $(dir $(lastword $(STACK)))

# include common make recipies, etc, from the next level up
# this will recurse all the way to the top of the repo tree
include $(THISDIR)../footer.mk

# pop this .mk file off the stack
STACK := $(subst $(lastword $(STACK)),,$(STACK))
THISDIR := $(dir $(lastword $(STACK)))
