# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.17)
project($ENV{RBB_PACKAGE_NAME} LANGUAGES C)

# rbbuild-specific setup: ensures a proper version is generated and packaging enabled
include(RBBuild)

add_library(greet SHARED src/greet.c)

# Keep the Windows import library out of obj/<toolchain>, which is packaged
set_target_properties(greet PROPERTIES
    ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/import
)

# No dependency on the MinGW runtime DLLs next to the library
if(MINGW)
    target_link_options(greet PRIVATE -static)
endif()

# Also package the library as rbbuild archive (default for CMake projects)
install(TARGETS greet COMPONENT runtime)

# rbbuild-specific: initiates packaging via CPack (must be last)
RBPackage()
