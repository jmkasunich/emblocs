cmake_minimum_required(VERSION 3.15)
project(bundle_test_lib C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(BUNDLE_SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../src/misc)

add_library(bundle SHARED ${BUNDLE_SRC_DIR}/bundle.c)

target_include_directories(bundle PRIVATE ${BUNDLE_SRC_DIR})
target_compile_definitions(bundle PRIVATE BDL_BUILD_TESTS)
target_compile_options(bundle PRIVATE -Wall -Wextra -g)

set_target_properties(bundle PROPERTIES
    PREFIX ""
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/data/tmp
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/data/tmp
    ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/data/tmp
)
