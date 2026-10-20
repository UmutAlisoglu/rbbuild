# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.17)
project($ENV{RBB_PACKAGE_NAME} LANGUAGES C)

# rbbuild-specific setup: ensures a proper version is generated and packaging enabled
include(RBBuild)

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

# Creates _greet.<soabi>.so (Linux) or _greet.<soabi>.pyd (Windows)
Python3_add_library(_greet MODULE WITH_SOABI src/greetmodule.c)

# No dependency on the MinGW runtime DLLs next to the extension
if (MINGW)
    target_link_options(_greet PRIVATE -static)
endif()

# Also package the extension as rbbuild archive (default for CMake projects)
install(TARGETS _greet LIBRARY DESTINATION lib COMPONENT runtime)

# rbbuild-specific: initiates packaging via CPack (must be last)
RBPackage()
