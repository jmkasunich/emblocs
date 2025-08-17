# define the component library target
add_library(components INTERFACE)

# specify the library sources
target_sources(components INTERFACE
    mux2.c
    sum2.c
    perftimer.c
    watch.c
    rp2040_gpio.c
    not.c
)

# specify the include path
target_include_directories(components INTERFACE ${CMAKE_CURRENT_LIST_DIR} )

# specify dependencies
target_link_libraries(components INTERFACE
        emblocs
)
