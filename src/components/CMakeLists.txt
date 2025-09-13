# define the component library target
add_library(components INTERFACE)

# specify the library sources
target_sources(components INTERFACE
    convert.c
    mux2.c
    siggen.c
    sum2.c
    perftimer.c
    watch.c
    rp2040_gpio.c
    not.c
    limit1.c
    limit2.c
    bl_rgb.c
)

# specify the include path
target_include_directories(components INTERFACE ${CMAKE_CURRENT_LIST_DIR} )

# specify dependencies
target_link_libraries(components INTERFACE
        emblocs
)
