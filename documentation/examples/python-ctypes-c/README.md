<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# Summary

This example demonstrates how rbbuild combines C and Python in one project:
* Compilation of a C shared library with CMake
* Calling the library from Python with `ctypes` (no Python headers needed)
* Packaging the library and the Python code into a platform-specific
  Python `wheel` (e.g., `greet_ctypes-1.0.3099.0-py3-none-linux_x86_64.whl`)

The library does not use the Python C API. Hence, the wheel is independent of
the Python version (`py3-none`), but specific to the platform.
The example [python-cext-c](../python-cext-c/README.md) shows the same with
a CPython extension module.


# Description

## Files

* **rbbuild.toml**: project name and version, and the `[packaging.wheel]`
  entry of type `python`. `platform-specific = true` tells rbbuild to tag the
  wheel with the platform. The compiled library `obj/<toolchain>/libgreet.*`
  is added to the `greet_ctypes` package (`strip` removes the toolchain folder
  from the path in the wheel, `dest` is the target folder inside the wheel).
* **CMakeLists.txt**: builds the shared library `greet`.
* **src/greet.c**: C functions `greet_add()` and `greet_hello()`.
* **greet_ctypes/__init__.py**: loads the library that is installed next to
  this file and exposes `add()` and `hello()`.


## Using rbbuild

```shell
rbbuild -sbp
```

This command compiles the library (`-sb`) and creates the packages (`-p`)
in `obj/<toolchain>`:
* `greet_ctypes-<version>-py3-none-<platform>.whl`: the wheel with the Python
  package and the library
* `greet_ctypes-<version>.tar.gz`: the source distribution; it contains the
  same files as the wheel
* `greet_ctypes-<version>-<toolchain>-runtime.tar.xz`: rbbuild archive of the
  library (from the CMake `install()` statement)
* `manifest.json` and the SBOM

The wheel can be installed and used with any Python installer:

```shell
uv pip install obj/linux-native/greet_ctypes-*.whl
python -c "import greet_ctypes; print(greet_ctypes.add(2, 3), greet_ctypes.hello())"
```

The platform tag is defined by the toolchain: it is taken from the toolchain
definition in the profile, or from the Python interpreter for `native`
toolchains (see [rbbconf.md](../../user-manual/rbbconf.md)). For toolchains
without platform tag, set the tag explicitly, e.g.,
`wheel-tag = 'py3-none-linux_armv7l'`, see
[rbbuild.toml.md](../../user-manual/rbbuild.toml.md).
