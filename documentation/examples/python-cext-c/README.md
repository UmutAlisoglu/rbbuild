<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# Summary

This example demonstrates how rbbuild combines C and Python in one project:
* Compilation of a CPython extension module (C) with CMake
* Packaging the extension and the Python code into a platform-specific
  Python `wheel` (e.g.,
  `greet_cext-1.0.3099.0-cp314-cp314-linux_x86_64.whl`)

An extension module uses the Python C API. Hence, the wheel is specific to the
Python version (`cpXY-cpXY`) and to the platform. The example
[python-ctypes-c](../python-ctypes-c/README.md) shows a simpler variant that
only depends on the platform.


# Description

## Files

* **rbbuild.toml**: project name and version, and the `[packaging.wheel]`
  entry of type `python`. `platform-specific = true` tells rbbuild to tag the
  wheel with the platform. The Python version in the tag is taken from the
  extension module's file name. The compiled module `obj/<toolchain>/_greet.*`
  is added to the `greet_cext` package.
* **CMakeLists.txt**: builds the extension module `_greet` with CMake's
  `Python3_add_library()`.
* **src/greetmodule.c**: C code of the module `greet_cext._greet`.
* **greet_cext/__init__.py**: exposes `add()` and `hello()` of the module.


## Prerequisites

The Python development files (headers) are required. They are part of Python
installations from python.org and uv. On Debian/Ubuntu with the system
Python, install `python3-dev`.


## Using rbbuild

```shell
rbbuild -sbp
```

This command compiles the module (`-sb`) and creates the packages (`-p`)
in `obj/<toolchain>`:
* `greet_cext-<version>-cpXY-cpXY-<platform>.whl`: the wheel with the Python
  package and the extension module
* `greet_cext-<version>.tar.gz`: the source distribution; it contains the same
  files as the wheel
* `greet_cext-<version>-<toolchain>-runtime.tar.xz`: rbbuild archive of the
  module (from the CMake `install()` statement)
* `manifest.json` and the SBOM

The wheel can be installed and used with any Python installer:

```shell
uv pip install obj/linux-native/greet_cext-*.whl
python -c "import greet_cext; print(greet_cext.add(2, 3), greet_cext.hello())"
```

The platform tag is defined by the toolchain, see
[rbbconf.md](../../user-manual/rbbconf.md). For toolchains without platform
tag, set the tag explicitly, e.g., `wheel-tag = 'cp314-cp314-linux_armv7l'`,
see [rbbuild.toml.md](../../user-manual/rbbuild.toml.md).
