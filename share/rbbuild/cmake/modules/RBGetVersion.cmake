# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

# RBGetVersion
# --------------
#
# Generates C/C++ API that provides version information.
#
# The module defines the following variables:
#
#   VERSION_MAJOR    - Major number
#   VERSION_MINOR    - Minor number
#   VERSION_REVISION - Revision is defined as number of days since 2018-04-16.
#   VERSION_BRANCH   - Branch name (derived from git)
#   VERSION_BUILD    - Build number (typically from Jenkins)
#   VERSION_PACKAGE  - Package name
#   VERSION_SOURCES  - Source files which contain the Version API.
#   VERSION_STRING   - Overall version string
#   VERSION_GIT_HASH - Current HEAD revision
#   VERSION_GIT_REPO - Remote git URL
#
# Only GIT is supported.
#
# Input environment variables:
#
#    RBB_ROOT             - sets RBB_ROOT (buildsystem root path)
#    RBB_CONFIG_PATH      - sets RBB_CONFIG_PATH (rbbuild shared data root, used for cmake templates)
#    RBB_DIST_PATH        - sets RBB_DIST_PATH (download files)
#    RBB_TOOLCHAIN_ID     - sets RBB_TOOLCHAIN_ID (toolchain identifier)
#    RBB_PACKAGE_NAME     - sets VERSION_PACKAGE_NAME
#    RBB_PACKAGE_VERSION  - sets VERSION_PACKAGE_STRING (with _NAME)
#    RBB_PACKAGE_MAJOR    - sets VERSION_MAJOR
#    RBB_PACKAGE_MINOR    - sets VERSION_MINOR
#    RBB_PACKAGE_REVISION - sets VERSION_REVISION
#    RBB_PACKAGE_BRANCH   - sets VERSION_BRANCH
#    RBB_PACKAGE_BUILD    - sets VERSION_BUILD
#    RBB_GIT_REPO         - sets VERSION_GIT_REPO (git repository URL)
#    RBB_GIT_HASH         - sets VERSION_GIT_HASH (git hash of current HEAD)
#
#=============================================================================

# Our base date. Computed with the following command:
#   echo "$(date --date='2018-04-16' +%s) / ((60*60*24))" | bc
set(DATE_2018_04_18 17636)


function(RBGetVersion)
    # Export the variables.
    set(RBB_ROOT          $ENV{RBB_ROOT})
    set(RBB_ROOT          ${RBB_ROOT} PARENT_SCOPE)
    set(RBB_CONFIG_PATH   $ENV{RBB_CONFIG_PATH})
    set(RBB_CONFIG_PATH   ${RBB_CONFIG_PATH} PARENT_SCOPE)
    set(RBB_DIST_PATH     $ENV{RBB_DIST_PATH})
    set(RBB_DIST_PATH     ${RBB_DIST_PATH} PARENT_SCOPE)
    set(RBB_TOOLCHAIN_ID  $ENV{RBB_TOOLCHAIN_ID})
    set(RBB_TOOLCHAIN_ID  ${RBB_TOOLCHAIN_ID} PARENT_SCOPE)
    set(VERSION_MAJOR     $ENV{RBB_PACKAGE_MAJOR})
    set(VERSION_MAJOR     ${VERSION_MAJOR} PARENT_SCOPE)
    set(VERSION_MINOR     $ENV{RBB_PACKAGE_MINOR})
    set(VERSION_MINOR     ${VERSION_MINOR} PARENT_SCOPE)
    set(VERSION_REVISION  $ENV{RBB_PACKAGE_REVISION})
    set(VERSION_REVISION  ${VERSION_REVISION} PARENT_SCOPE)
    set(VERSION_BRANCH    $ENV{RBB_PACKAGE_BRANCH})
    set(VERSION_BRANCH    ${VERSION_BRANCH} PARENT_SCOPE)
    set(VERSION_BUILD     $ENV{RBB_PACKAGE_BUILD})
    set(VERSION_BUILD     ${VERSION_BUILD} PARENT_SCOPE)
    set(VERSION_PACKAGE   $ENV{RBB_PACKAGE_NAME})
    set(VERSION_PACKAGE   ${VERSION_PACKAGE} PARENT_SCOPE)
    set(VERSION_STRING    $ENV{RBB_PACKAGE_NAME}-$ENV{RBB_PACKAGE_VERSION})
    set(VERSION_STRING    ${VERSION_STRING} PARENT_SCOPE)
    set(VERSION_GIT_REPO  $ENV{RBB_GIT_REPO})
    set(VERSION_GIT_REPO  ${VERSION_GIT_REPO} PARENT_SCOPE)
    set(VERSION_GIT_HASH  $ENV{RBB_GIT_HASH})
    set(VERSION_GIT_HASH  ${VERSION_GIT_HASH} PARENT_SCOPE)

    set(RBB_VERSION_PATH "${CMAKE_BINARY_DIR}/version")

    # Generate source and header files with the version information.
    configure_file(
        "${RBB_CONFIG_PATH}/cmake/templates/version.c.in"
        "${RBB_VERSION_PATH}/${VERSION_PACKAGE}_version.c"
    )

    configure_file(
        "${RBB_CONFIG_PATH}/cmake/templates/version.h.in"
        "${RBB_VERSION_PATH}/${VERSION_PACKAGE}_version.h"
    )

    configure_file(
        "${RBB_CONFIG_PATH}/cmake/templates/rbversioninfo.h.in"
        "${RBB_VERSION_PATH}/rbversioninfo.h"
        COPYONLY
    )

    configure_file(
        "${RBB_CONFIG_PATH}/cmake/templates/version.h.in"
        "${RBB_VERSION_PATH}/${VERSION_PACKAGE}_version.h"
    )

    # Export the generated source and header files.
    aux_source_directory("${RBB_VERSION_PATH}" _SOURCES)
    set(VERSION_SOURCES ${_SOURCES} PARENT_SCOPE)

    set(
        VERSION_HEADERS "${RBB_VERSION_PATH}/${VERSION_PACKAGE}_version.h"
        "${RBB_VERSION_PATH}/rbversioninfo.h"
        PARENT_SCOPE
    )

    # Add "generated" path to the include directory path.
    include_directories("${RBB_VERSION_PATH}")

    message(STATUS "Package version: ${VERSION_STRING}")

endfunction()

