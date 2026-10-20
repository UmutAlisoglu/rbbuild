# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

# RBPackage: create packages
#
# Input variables:
#
#   RBPACKAGE_DESCRIPTION[_<cmp>]    -- package description used by (e.g.)
#                                       CPACK_RPM_PACKAGE_DESCRIPTION.
#                                       Append _<cmp> to define per
#                                       subcomponent descriptions
#   RBPACKAGE_REQUIRES               -- package dependencies used by (e.g.)
#                                       CPACK_RPM_PACKAGE_REQUIRES
#   RBPACKAGE_GENERATOR              -- Generators for deployment. Default: TXZ
#   RBPACKAGE_COMPONENTS             -- Which install components to deploy
#                                       (default: all install components)
#   RBPACKAGE_CUSTOM_ARTIFACTS_<cmp> -- Add custom packages to deployment that
#                                       are not "installed" via CMake. <cmp> is
#                                       the subcomponent name (case is ignored).
#   RBPACKAGE_SOURCE_DIRS            -- Package source directories for SonarQube
#                                       and Doxygen
#                                       (CMake list or semi-colon separated string).
#   RBPACKAGE_DOXYGEN_DOXYFILE       -- Specifies the Doxyfile to employ. If not
#                                       defined, generate from rbbuild template.
#
# Functions:
#   RBPackage()   -- create packages

# Global variables
set(CPACK_PACKAGING_INSTALL_PREFIX "/")
set(CPACK_SYSTEM_NAME ${CMAKE_SYSTEM_PROCESSOR})
set(CPACK_PACKAGE_VENDOR "rbbuild user")
set(CPACK_DEBIAN_PACKAGE_MAINTAINER "${CPACK_PACKAGE_VENDOR}")
set(CPACK_RPM_PACKAGE_LICENSE "Proprietary")
set(CPACK_RPM_PACKAGE_ARCHITECTURE ${CMAKE_SYSTEM_PROCESSOR})
set(CPACK_DEBIAN_PACKAGE_ARCHITECTURE ${CMAKE_SYSTEM_PROCESSOR})
# We want to prevent that header files are installed on the target device.
# Therefore, install per component.
# See https://cmake.org/Wiki/CMake:Component_Install_With_CPack
set(CPACK_RPM_COMPONENT_INSTALL ON)
set(CPACK_DEB_COMPONENT_INSTALL ON)
set(CPACK_ARCHIVE_COMPONENT_INSTALL ON)

# if install( ... COMPONENT ...) is undefined, use this value
set(CMAKE_INSTALL_DEFAULT_COMPONENT_NAME "default")

# use XZ as internal compression format.
set(CPACK_RPM_COMPRESSION_TYPE "xz")
set(CPACK_DEBIAN_COMPRESSION_TYPE "xz")

# Setting RBB_EXTRA_C_FLAGS or RBB_EXTRA_CXX_FLAGS allows to append
# compiler flags. This is useful to use a different optimization level:
#
#     RBB_EXTRA_C_FLAGS="-O0" rbbuild
#
# The example above will compile with -O0 instead of -O2.
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} $ENV{RBB_EXTRA_C_FLAGS}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} $ENV{RBB_EXTRA_CXX_FLAGS}")

# Use multiple CPU threads for compression (0 means auto-detect).
# Only active with CMake 3.20 or higher.
set(CPACK_THREADS 0)

set(RBB_CMAKE_PROPERTIES "${CMAKE_BINARY_DIR}/generated/cmake.properties")

# If we are cross compiling, we need to set the RPATH to the installation
# directory. Otherwise, the binaries will be adjusted and the signatures will
# not match anymore. This must happen at the very beginning of the
# CMakeLists.txt. When building on Linux native, we need to retain the RPATH
# value.
set(CMAKE_BUILD_WITH_INSTALL_RPATH ${CMAKE_CROSSCOMPILING})

function(RBPackageDeploy artf suffix comp)
    file( APPEND "${RBB_CMAKE_PROPERTIES}"
        "subcomponent.${comp}.${suffix}=${artf}\n" )

    set(ADDITIONAL_CLEAN_FILES ${ADDITIONAL_CLEAN_FILES} ${artf})
endfunction()


function(RBPackagePrepare)
    if (_rbpackage_prepare_done)
        return()
    endif()

    # Version settings
    if (NOT DEFINED VERSION_PACKAGE)
        set(VERSION_MAJOR 0)
        set(VERSION_MINOR 0)
        set(VERSION_REVISION 0)
        message( FATAL_ERROR
            "No package version information available. Make sure to add\n"
            "  include(RBGetVersion)\n"
            "  RBGetVersion()\n"
            "before calling RBPackage() in the CMakeLists.txt" )
    endif()

    set(CPACK_PACKAGE_NAME ${VERSION_PACKAGE} PARENT_SCOPE)
    # Doesn't work for CPACK_ARCHIVE: https://gitlab.kitware.com/cmake/cmake/-/issues/16516
    set(CPACK_RPM_default_FILE_NAME    "${VERSION_PACKAGE}-${VERSION_MAJOR}.${VERSION_MINOR}.${VERSION_REVISION}-${VERSION_BRANCH}.${VERSION_BUILD}-${RBB_TOOLCHAIN_ID}.rpm" PARENT_SCOPE)
    set(CPACK_DEBIAN_default_FILE_NAME "${VERSION_PACKAGE}-${VERSION_MAJOR}.${VERSION_MINOR}.${VERSION_REVISION}-${VERSION_BRANCH}.${VERSION_BUILD}-${RBB_TOOLCHAIN_ID}.ipk" PARENT_SCOPE)

    # The filename is following the IVY naming scheme, which is <package>-<version>-<variant>.<ext>
    set(CPACK_PACKAGE_FILE_NAME "${VERSION_STRING}-${RBB_TOOLCHAIN_ID}" PARENT_SCOPE)
    set(CPACK_PACKAGE_VERSION   "${VERSION_MAJOR}.${VERSION_MINOR}.${VERSION_REVISION}" PARENT_SCOPE)
    set(CPACK_DEBIAN_FILE_NAME  "${VERSION_STRING}-${RBB_TOOLCHAIN_ID}.ipk" PARENT_SCOPE)

    # Set Version: field in RPM package.
    # Note that all hyphens (-) are replaced by underscores (_) in the CPackRPM
    # module because rpmbuild refuses to accept these strings.
    # For some reason, we need to use CACHE STRING.
    set(CPACK_RPM_PACKAGE_VERSION "${VERSION_MAJOR}.${VERSION_MINOR}.${VERSION_REVISION}-${VERSION_BRANCH}.${VERSION_BUILD}" CACHE STRING "" FORCE)

    # Warn about deprecated variables
    if (RBPACKAGE_PRODUCTION_COMPONENTS OR RBPACKAGE_DEVELOPMENT_COMPONENTS)
        message(AUTHOR_WARNING "RBPACKAGE_DEVELOPMENT_COMPONENTS and RBPACKAGE_PRODUCTION_COMPONENTS are deprecated!")
    endif()


    # Set components that needs to be built. See CpackComponent.cmake.
    if (NOT RBPACKAGE_COMPONENTS)
        get_cmake_property(RBPACKAGE_COMPONENTS COMPONENTS)
        set(RBPACKAGE_COMPONENTS ${RBPACKAGE_COMPONENTS} PARENT_SCOPE)
    endif()

    # Support for Doxygen
    # Requires doxygen and graphviz to be installed.
    if (CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
        find_package(Doxygen)
        if (DOXYGEN_FOUND)
            get_property(LANGUAGES GLOBAL PROPERTY ENABLED_LANGUAGES)
            if (CXX IN_LIST LANGUAGES)
                set(RBPACKAGE_DOXYGEN_OPTIMIZE_C YES)
            elseif(C IN_LIST LANGUAGES)
                set(RBPACKAGE_DOXYGEN_OPTIMIZE_C YES)
            else()
                set(RBPACKAGE_DOXYGEN_OPTIMIZE_C NO)
            endif()

            list(JOIN RBPACKAGE_SOURCE_DIRS " " RBPACKAGE_DOXYGEN_INPUT)
            if (NOT RBPACKAGE_DOXYGEN_DOXYFILE)
                configure_file( "$ENV{RBB_CONFIG_PATH}/cmake/templates/Doxyfile.in"
                    "${CMAKE_BINARY_DIR}/generated/Doxyfile" )
            else()
                configure_file( "${RBPACKAGE_DOXYGEN_DOXYFILE}"
                    "${CMAKE_BINARY_DIR}/generated/Doxyfile"
                    COPYONLY )
            endif()

            add_custom_target( doc
                DEPENDS "${CMAKE_BINARY_DIR}/_rbpackage_doxygen.done" )

            add_custom_command( OUTPUT "${CMAKE_BINARY_DIR}/_rbpackage_doxygen.done"
                USES_TERMINAL
                COMMAND ${DOXYGEN_EXECUTABLE} ${CMAKE_BINARY_DIR}/generated/Doxyfile -w html
                COMMAND ${CMAKE_COMMAND} -E touch "${CMAKE_BINARY_DIR}/_rbpackage_doxygen.done" )
        endif()
    endif()

    set(_rbpackage_prepare_done True PARENT_SCOPE)

endfunction()


function(RBPackage)
    RBPackagePrepare()

    file(REMOVE "${RBB_CMAKE_PROPERTIES}")
    # Set default package generators if not available (i.e., when calling rbbuild --package)
    if (NOT RBPACKAGE_GENERATOR)
        set(RBPACKAGE_GENERATOR "TXZ")
    endif()

    set(CPACK_GENERATOR ${RBPACKAGE_GENERATOR})
    list(REMOVE_DUPLICATES CPACK_GENERATOR)

    # The user could have added new components to our list. Remove duplicates.
    if(RBPACKAGE_COMPONENTS)
        list(REMOVE_DUPLICATES RBPACKAGE_COMPONENTS)
    endif()

    # We must override this variable even if we don't define custom variables.
    # Otherwise, the component name (-prod) will not be generated.
    set(CPACK_COMPONENTS_ALL ${RBPACKAGE_COMPONENTS})

    foreach (_comp ${RBPACKAGE_COMPONENTS})
        # Iterate over all selected generators
        foreach (_gen ${CPACK_GENERATOR})
            string(TOLOWER ${_gen} _suffix)
            # Explicitly require tar.xz package format
            if ("TXZ" STREQUAL ${_gen})
                set(_suffix "tar.xz")
            elseif("TGZ" STREQUAL ${_gen})
                set(_suffix "tar.gz")
                # Handle RPM packaging
            elseif("RPM" STREQUAL ${_gen})
                set(CPACK_RPM_PACKAGE_REQUIRES    "${RBPACKAGE_REQUIRES}")
                set(CPACK_RPM_PACKAGE_DESCRIPTION "${RBPACKAGE_DESCRIPTION}")
                set(CPACK_RPM_${_comp}_PACKAGE_DESCRIPTION "${RBPACKAGE_DESCRIPTION_${_comp}}")
            elseif("DEB" STREQUAL ${_gen})
                set(_suffix "ipk")
            endif()

            # Special handling for subcomponent "default"
            if ("default" STREQUAL ${_comp} AND ("RPM" STREQUAL ${_gen} OR "DEB" STREQUAL ${_gen}))
                set(ARTIFACT_FNAME "${CMAKE_CURRENT_BINARY_DIR}/${CPACK_PACKAGE_FILE_NAME}.${_suffix}")
            else()
                set(ARTIFACT_FNAME "${CMAKE_CURRENT_BINARY_DIR}/${CPACK_PACKAGE_FILE_NAME}-${_comp}.${_suffix}")
            endif()
            RBPackageDeploy("${ARTIFACT_FNAME}" "${_suffix}" "${_comp}")
        endforeach()
    endforeach()


    # Handle RBPACKAGE_CUSTOM_ARTIFACTS_<scomp> variables:
    # * <scomp> is the target subcomponent name
    # * string(TOLOWER <scomp> scomp) will be called, i.e., the subcomponent
    #   for RBPACKAGE_CUSTOM_ARTIFACTS_PROD is "prod"
    get_cmake_property(_var_names VARIABLES)
    list (SORT _var_names)
    foreach (_var ${_var_names})
        string(REGEX MATCH "RBPACKAGE_CUSTOM_ARTIFACTS_(.*)" _re_match ${_var})
        if (_re_match)
            string(REGEX REPLACE "RBPACKAGE_CUSTOM_ARTIFACTS_(.*)" "\\1" _re_comp ${_var})
            string(TOLOWER ${_re_comp} _re_comp_lower)

            foreach (_artf ${${_var}})
                if (NOT _artf MATCHES ".+\.[a-zA-Z0-9_]+")
                    message(FATAL_ERROR "${_var}:${_artf}: "
                        "filename must have a file extension suffix" )
                endif()
                string(REGEX REPLACE "^.+\\.([a-zA-Z0-9_]+)$" "\\1" _suffix "${_artf}")
                RBPackageDeploy("${_artf}" "${_suffix}" ${_re_comp_lower})
            endforeach()

        endif()
    endforeach()

    file( APPEND "${RBB_CMAKE_PROPERTIES}"
        "package_sources=${RBPACKAGE_SOURCE_DIRS}\n" )

    include(CPack)

endfunction()


include(RBPythonChecker)

