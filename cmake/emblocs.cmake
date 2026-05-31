# emblocs.cmake - EMBLOCS build system integration
#
# Include this file in your CMakeLists.txt after add_executable():
#
#   include(${EMBLOCS_DIR}/cmake/emblocs.cmake)
#
# Required variables (set these in CMakeLists.txt before including this file):
#
#   BLOCS_FILE  - stem name of the .blocs system definition file (without
#                 extension). The file ${BLOCS_FILE}.blocs must be in the
#                 same directory as CMakeLists.txt.
#                 e.g. set(BLOCS_FILE blink)  ->  expects blink.blocs
#
#   TARGET      - CMake executable target name; must match add_executable().
#                 If the executable is named after the project (as when
#                 using the Raspberry Pi Pico VS Code extension), use:
#                   set(TARGET ${CMAKE_PROJECT_NAME})
#                 Override only if your executable name differs from the
#                 project name.
#
#   EMBLOCS_DIR - path to the root of the emblocs repository.
#                 e.g. set(EMBLOCS_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../submodules/emblocs)
#
# After including this file, the following variable is available:
#
#   EMBLOCS_INC - path to emblocs headers (src/emblocs/), already added to
#                 target_include_directories() for TARGET. Available for
#                 reference if needed elsewhere in CMakeLists.txt.

set(EMBLOCS_INC ${EMBLOCS_DIR}/src/emblocs)

# Re-run configure if the system definition or config file changes
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/${BLOCS_FILE}.blocs
    ${CMAKE_CURRENT_SOURCE_DIR}/emblocs.json
)

# Run blocs_compiler.py at configure time to generate variant source files
execute_process(
    COMMAND python
        ${EMBLOCS_DIR}/python/blocs_compiler.py
        ${CMAKE_CURRENT_SOURCE_DIR}/${BLOCS_FILE}.blocs
        ${CMAKE_BINARY_DIR}
    RESULT_VARIABLE BLOCS_COMP_RESULT
    OUTPUT_VARIABLE BLOCS_COMP_OUTPUT
    ERROR_VARIABLE BLOCS_COMP_OUTPUT
)
if(NOT BLOCS_COMP_RESULT EQUAL 0)
    message(FATAL_ERROR "blocs_compiler.py failed:\n${BLOCS_COMP_OUTPUT}")
else()
    message(STATUS "${BLOCS_COMP_OUTPUT}")
endif()

# Include generated compile rules - adds generated source files to TARGET
include(${CMAKE_BINARY_DIR}/${BLOCS_FILE}.cmake)

# Add generated headers and emblocs headers to the include path
target_include_directories(${TARGET} PRIVATE
    ${CMAKE_BINARY_DIR}
    ${EMBLOCS_INC}
)
