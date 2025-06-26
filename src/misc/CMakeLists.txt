# define the library targets
add_library(linked_list INTERFACE)
add_library(printing INTERFACE)
add_library(str_to_xx INTERFACE)

# specify the library sources
target_sources(linked_list INTERFACE
    linked_list.c
)

target_sources(printing INTERFACE
    printing.c
)

target_sources(str_to_xx INTERFACE
    str_to_xx.c
)

# specify the include path
target_include_directories(linked_list INTERFACE ${CMAKE_CURRENT_LIST_DIR} )
target_include_directories(printing INTERFACE ${CMAKE_CURRENT_LIST_DIR} )
target_include_directories(printing INTERFACE ${CMAKE_CURRENT_LIST_DIR} )

#target_link_libraries(printing INTERFACE stdio )
