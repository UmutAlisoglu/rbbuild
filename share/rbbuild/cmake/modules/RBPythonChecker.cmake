# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

# In order to perform PEP8 checks, flake8 needs to be installed.
# To do so, one can use the pip installer
#
#   $ pip install flake8

find_program(FLAKE8_EXE NAME "flake8"
                        HINTS "$ENV{HOME}/.local/bin/" )
mark_as_advanced(FLAKE8_EXE)

if (NOT FLAKE8_EXE)
    #message(WARNING "flake8 is not installed. Skipping PEP8 checks!\n"
    #                "Execute 'pip install flake8' to fix.")
    set(FLAKE8_EXE "echo")
endif()

# Ignored flake8 / PEP8 rules:
# * E501: >79 character -- Justification: this is not a strict error for us, only a recommendation
set(FLAKE8_ERROR_IGNORE_LIST "E501")


# Usage:
#    rb_add_executable_py(<target> <script.py>)
#
# Only one python script allowed per target!
#
# Example:
#
#     rb_add_executable_py(inotify inotify.py)
#     rb_add_executable_py(script2 script2.py)
#     install( TARGETS inotify script2
#              DESTINATION bin )
function(rb_add_executable_py)
    set(target ${ARGV0})
    set(script ${ARGV1})

    add_executable(${target} ${script})
    set_target_properties( ${target}
                           PROPERTIES LINKER_LANGUAGE NONE )

    add_custom_command( TARGET ${target}
                        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
                        USES_TERMINAL
                        POST_BUILD
                        COMMAND "${FLAKE8_EXE}" --ignore=${FLAKE8_ERROR_IGNORE_LIST} ${script}
                        COMMAND ${CMAKE_COMMAND} -E copy "${script}" "$<TARGET_FILE:${target}>" )

endfunction()


# Usage:
#     rb_add_library_py(<target> <script1.py> [<script2.py> ...])
#
# Example:
#
#     rb_add_library_py(python_lib inotify.py script2.py)
#     install( TARGETS python_lib
#              PUBLIC_HEADER
#              DESTINATION lib )
function(rb_add_library_py)
    set(target ${ARGV0})
    math(EXPR argc_minus_1 "${ARGC} - 1" OUTPUT_FORMAT DECIMAL)
    list(SUBLIST ARGV 1 ${argc_minus_1} scripts)

    add_library(${target} INTERFACE)
    set_target_properties( ${target}
                           PROPERTIES PUBLIC_HEADER "${scripts}"
                                      HEADER_ONLY 1
                                      LINKER_LANGUAGE NONE )
    add_custom_command( OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/flake8.done"
                        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
                        USES_TERMINAL
                        COMMAND "${FLAKE8_EXE}" ${scripts}
                        COMMAND ${CMAKE_COMMAND} -E touch "${CMAKE_CURRENT_BINARY_DIR}/flake8.done" )

    add_custom_target( ${target}.check ALL
                       SOURCES ${scripts}
                       DEPENDS "${CMAKE_CURRENT_BINARY_DIR}/flake8.done" )

    add_dependencies(${target} ${target}.check)

endfunction()
