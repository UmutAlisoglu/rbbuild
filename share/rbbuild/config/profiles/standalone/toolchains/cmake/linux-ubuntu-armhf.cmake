# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

# On Ubuntu 24.04, the compiler is installed via the following command:
#
#   sudo apt install gcc-arm-linux-gnueabihf

set(CMAKE_CROSSCOMPILING   True)
set(CMAKE_SYSTEM_NAME      Linux)
set(CMAKE_SYSTEM_VERSION   6.11.0-ubuntu-24.04)
set(CMAKE_SYSTEM           ${SYTEM_NAME}-${SYSTEM_VERSION})
set(CMAKE_SYSTEM_PROCESSOR arm)

list(APPEND CMAKE_PREFIX_PATH "${CMAKE_STAGING_PREFIX}/usr")

set(CROSS_COMPILE_HOST "arm-linux-gnueabihf")

set(CMAKE_C_COMPILER   ${CROSS_COMPILE_HOST}-gcc CACHE STRING "" FORCE)
set(CMAKE_CXX_COMPILER ${CROSS_COMPILE_HOST}-g++ CACHE STRING "" FORCE)
set(CMAKE_STRIP        ${CROSS_COMPILE_HOST}-strip CACHE STRING "" FORCE)


#
# The following compiler flags settings are optional
#

# setting compiler and linker flags.
# CACHE STRING "" FORCE overrides any defaults from CMake (e.g., -O3 -DNDEBUG)

# Security-related flags
# -fstack-protector-all: add canaries to all variables on stack
# -D_FORTIFY_SOURCE=1: use hardened variant of LIBC functions
# -Wshadow: warn when a variable is shadowing from upper context layers
# -Wstack-protector: warn for stack-protector problems
set(RBBUILD_SECURITY_C_FLAGS      "-fstack-protector-all -D_FORTIFY_SOURCE=1 -Wshadow -Wstack-protector")

# -z,relro: make several ELF sections read-only (security feature)
set(RBBUILD_SECURITY_LINKER_FLAGS "-Wl,-z,relro")

# C flags
# Contents of *_RELEASE and *_DEBUG parameters are appended according to the
# selected configuration
# -fno-semantic-interposition: do not allow to intercept symbols from libraries using LD_PRELOAD.
set(CMAKE_C_FLAGS         "${RBBUILD_SECURITY_C_FLAGS} -O2 -fdiagnostics-color=always -W -Wall -Wno-psabi" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS_RELEASE "-s -fno-semantic-interposition"    CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS_DEBUG   "-ggdb -funwind-tables" CACHE STRING "" FORCE)

# C++ flags
# Contents of *_RELEASE and *_DEBUG parameters are appended according to the
# selected configuration
# -fvisibility-inlines-hidden: forces inline methods to be excluded from ELF
# binaries, thus, making code smaller.
set(CMAKE_CXX_FLAGS         "${CMAKE_C_FLAGS} -fvisibility-inlines-hidden" CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS_RELEASE "-s -fno-semantic-interposition"    CACHE STRING "" FORCE)
set(CMAKE_CXX_FLAGS_DEBUG   "-ggdb -funwind-tables" CACHE STRING "" FORCE)

# security flag: use -fPIE to improve security
set(CMAKE_POSITION_INDEPENDENT_CODE TRUE)


# Linker flags
# --as-needed: remove unneeded libraries in ELF DT_NEEDED sections
# -O1: enable linker optimization
# --hash-style=gnu: use faster GNU style hash table structures
set(CMAKE_EXE_LINKER_FLAGS    "${RBBUILD_SECURITY_LINKER_FLAGS} -Wl,--as-needed,-O1,--hash-style=gnu" CACHE STRING "" FORCE)
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS}" CACHE STRING "" FORCE)

