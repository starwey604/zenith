cmake_minimum_required(VERSION 3.22)
project(zenith_runtime VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(ZENITH_PLATFORM "native" CACHE STRING "Runtime platform")
set_property(CACHE ZENITH_PLATFORM PROPERTY STRINGS native lbc3)
if(NOT ZENITH_PLATFORM MATCHES "^(native|lbc3)$")
    message(FATAL_ERROR "ZENITH_PLATFORM must be native or lbc3")
endif()
if(ZENITH_PLATFORM STREQUAL "lbc3" AND
   (NOT CMAKE_CROSSCOMPILING OR NOT CMAKE_SYSTEM_PROCESSOR STREQUAL "aarch64"))
    message(FATAL_ERROR "lbc3 requires the AArch64 cross toolchain")
endif()

# ThinLTO is set explicitly by the presets, rather than CMake full LTO.
if(NOT CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
    message(FATAL_ERROR "Use the LLVM presets: this runtime requires Clang")
endif()
find_package(Threads REQUIRED)
include(CTest)
add_subdirectory(apps/zenith-control)
