# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

cmake_minimum_required(VERSION 3.17)
project($ENV{RBB_PACKAGE_NAME})

# Staging folder of zlib sources
set(ZLIB ${CMAKE_STAGING_PREFIX}/zlib-1.3.2)

# rbbuild-specific setup: ensures a proper version is generated and packaging enabled
include(RBBuild)

# Needed to set CMAKE_INSTALL_PREFIX, which is used by zlib
set(CMAKE_INSTALL_PREFIX "${CMAKE_STAGING_PREFIX}" CACHE STRING "" FORCE)
add_subdirectory(${ZLIB})

# Install and packaging rules
install(
    TARGETS zlib
    COMPONENT runtime
    DESTINATION usr/lib
)

install(
    TARGETS zlibstatic
    COMPONENT dev
    DESTINATION usr/lib
)

# Headers are installed into our staging folder - pick them up from there
install(
    DIRECTORY ${ZLIB}
    COMPONENT dev
    DESTINATION usr
)

# rbbuild-specific: initiates packaging via CPack (must be last)
RBPackage()

