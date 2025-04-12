# directory containing the currently included header.mk
# this is the top of the tree (so far)
TOPDIR := $(dir $(lastword $(MAKEFILE_LIST)))

# include common make variables, paths, etc, from the next level up
# this will recurse all the way to the top of the repo tree
include $(TOPDIR)../header.mk
