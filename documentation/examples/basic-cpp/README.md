<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# Summary

This example demonstrates the basic functionality of rbbuild:
* Integration of CMake as build system for C++ source code
* Compilation of source code to binary artifacts on various targets
* Packaging binaries to a archive or package manager file

This example deliberately shows the whole rbbuild workflow in
combination with CMake as backend. Other examples will spotlight
the use of rbbuild with other backends (Python or pure rbbuild).
Likewise, the handling of third-party code and dependencies are
demonstrated in other examples.


# Description

## Files

This folder contains the following source code files:
* **rbbuild.toml**: rbbuild project description and configuration.
  In this example, it mainly affects the package name and version.
* **CMakeLists.txt**: CMake build and packaging instructions with
  rbbuild-specific commands in file header and footer.
* **main.cc**: C++ entry point source file with `main()` function
  definition. Will be compiled to `obj/.../app` and `obj/.../app_static`.
* **include & src**: C++ code for `ExampleLibrary` class. Will be compiled
  to `obj/.../liblib.so` and `obj/.../liblib_static.a` (on Linux;
  comparable output on Windows).

## Using rbbuild

When compiling the code with `rbbuild -sb`, the `obj` build folder is
created. Here you can find, under a toolchain-specific toolchain folder
such as `obj/linux-native`, generated binaries and other artifacts.

The command `rbbuild -sb` (which can simply be abbreviated to `rbbuild`)
consists of two steps:
1. **setup** (`rbbuild -s/--setup`): in a nutshell, this command invokes
   the CMake build folder creation (calling `cmake obj/linux-native`)
   with rbbuild-specific parameters passed to CMake. This call also
   creates the `ninja` build files.
2. **build** (`rbbuild -b/--build`): calls the actual compilation via
   the CMake-generated build files (i.e., `ninja`).

Afterwards, the user can create a package out of the compiled artifacts:
* **package** (`rbbuild -p/--package`): this command invokes the CMake packaging
  mechanism and creates, based on defined inputs in CMakeLists.txt, archive or
  other package manager files under `obj`.

By calling `rbbuild -c/--clean`, the user can also remove contents of the `obj`
folder after any stage of the rbbuild workflow.

