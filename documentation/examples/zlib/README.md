<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# Summary

This example demonstrates how external CMake tools can be (cross) compiled and
packaged with rbbuild.
* While plain building of CMake-based projects like ZLIB is usually
  possible without any changes to the CMakeLists.txt, packaging
  requires a bit adaptation.
* By wrapping the original ZLIB package, CMakeLists.txt in the top
  level folder acts as rbbuild wrapper. This way, (cross-) building
  and packaging of ZLIB is possible using standard rbbuild commands.

# Description

## Files

This folder contains the following source code files:
* **rbbuild.toml**: rbbuild project description and configuration.
  In this example, it mainly affects the package name and version.
* **CMakeLists.txt**: CMake build and packaging instructions with
  rbbuild-specific commands in file header and footer. The actual build
  is executed from the upstream ZLIB CMakeLists.txt.


## Using rbbuild

By calling `rbbuild -FI`, ZLIB sources are extracted under staging.
This command consists of two actions:
1. **fetch** (`rbbuild -F/--fetch`): downloads dependencies (in this
  case the upstream ZLIB source package) into a local cache folder.
2. **install** (`rbbuild -I/--install-deps`): installs the
   dependencies under staging, e.g., the ZLIB sources are unpacked
   under `staging/.../zlib-1.3.2`.

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

