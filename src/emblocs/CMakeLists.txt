# define the EMBLOCS library target
add_library(emblocs INTERFACE)

# specify the library sources
target_sources(emblocs INTERFACE
    ebl_core.c
    ebl_parse.c
    ebl_show.c
)

# specify the include path
target_include_directories(emblocs INTERFACE ${CMAKE_CURRENT_LIST_DIR} )

# specify dependencies
target_link_libraries(emblocs INTERFACE
        linked_list
        printing
        str_to_xx
)
