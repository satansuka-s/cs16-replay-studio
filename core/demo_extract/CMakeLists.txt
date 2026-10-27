cmake_minimum_required(VERSION 3.16)
project(demo_extract CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT MSVC)
    add_compile_options(-Wall -Wextra)
endif()

# HLDemo (YaLTeR) - structural GoldSrc demo reader/writer
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../extern/HLDemo ${CMAKE_CURRENT_BINARY_DIR}/HLDemo)

add_executable(demo_extract
    src/main.cpp
    src/demodecoder.hpp
    src/delta.hpp
    src/bitreader.hpp
    src/netprotocol.hpp
    src/json_writer.hpp
)

target_include_directories(demo_extract PRIVATE
    src
    ${CMAKE_CURRENT_SOURCE_DIR}/../extern/HLDemo/src
)

target_link_libraries(demo_extract PRIVATE HLDemo)
