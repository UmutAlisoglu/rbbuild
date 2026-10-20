# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.17)
project ($ENV{RBB_PACKAGE_NAME})

# rbbuild-specific setup: ensures a proper version is generated and packaging enabled
include(RBBuild)

# Configure CMake build targets
set(MAIN_SOURCES main.cc ${VERSION_SOURCES})
file(GLOB LIB_SOURCES src/*.cc)

include_directories(include)
add_library(lib SHARED ${LIB_SOURCES})
target_link_libraries(lib)

add_library(lib_static STATIC ${LIB_SOURCES})
target_link_libraries(lib_static)

add_executable(app ${MAIN_SOURCES})
target_link_libraries(app lib)

add_executable(app_static ${MAIN_SOURCES})
target_link_libraries(app_static lib_static)

# Packaging instructions.
#
# COMPONENT also affects filename of generated
# archive file.
install(
    TARGETS app lib
    COMPONENT runtime
)

install(
    TARGETS app_static
    COMPONENT static
)

# Uncomment this instruction to generate RPM packages
# instead of archive packages.
# If not set, defaults to "TXZ" (tar.xz archive).
# Available formats are listed with "cpack -h" (part of CMake).
#
# RPM feature is only available on Linux with rpmbuild
# installed.
# Ensure that "sudo apt install rpm" is executed on Ubuntu/Debian.
#
# set(RBPACKAGE_GENERATOR "RPM")

# rbbuild-specific: initiates packaging via CPack (must be last)
RBPackage()

