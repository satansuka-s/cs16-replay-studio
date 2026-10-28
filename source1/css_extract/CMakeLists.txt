cmake_minimum_required(VERSION 3.20)
project(css_extract CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(css_extract css_extract.cpp)

include(FetchContent)
# prefer the local checkout (core/extern/css-demo-parser); falls back to GitHub
set(LOCAL_CSSDEMO "${CMAKE_CURRENT_SOURCE_DIR}/../core/extern/css-demo-parser")
if(EXISTS "${LOCAL_CSSDEMO}/CMakeLists.txt")
	FetchContent_Declare(cssdemo SOURCE_DIR "${LOCAL_CSSDEMO}")
else()
	FetchContent_Declare(cssdemo GIT_REPOSITORY https://github.com/sockfish/css-demo-parser.git GIT_TAG master)
endif()
FetchContent_MakeAvailable(cssdemo)
target_link_libraries(css_extract PRIVATE cssdemo::cssdemo)
