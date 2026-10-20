# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

# RBBuild: main CMake module for rbbuild
#
# Usage example for project CMakeLists.txt:
#
#   cmake_minimum_required(VERSION 3.25)
#   project($ENV{RBB_PACKAGE_NAME})
#
#   include(RBBuild)
#
#   add_executable(test_app ${SOURCES})
#   target_link_libraries(test_app)
#
#   install( TARGETS test_app
#            DESTINATION usr/bin )
#
#   RBPackage()


include(RBGetVersion)
include(RBPackage)

RBGetVersion()

