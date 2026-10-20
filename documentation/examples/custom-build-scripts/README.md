<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# Summary

This example demonstrates how to run custom build scripts with rbbuild:
* Execution of an arbitrary script instead of a build system such as CMake
* Passing the build folder to the script via an environment variable
* Packaging the script output as a plain file and as an archive

Other examples show the use of rbbuild with CMake or Python backends.


# Description

## Files

* **rbbuild.toml**: project name and version, the `build-scripts` entry that
  lists the script to run, and two `[packaging.*]` entries that package the
  script output `$OBJ/my_component`: once as-is (`mypackage_plain`) and once
  as an archive (`mypackage_archive`).
* **custom_build_script.py**: example build script. It writes the file
  `my_component` into the build folder given by the environment variable
  `RBB_BUILD_PATH`.


## Using rbbuild

```shell
rbbuild -sbp
```

The build step (`-b`) executes each script listed in `build-scripts`, with
the project folder as working directory. The script is started directly
(the path is passed to the operating system as the program to run), and
`-j <njobs>` and the build target, if given, are appended as arguments.
The packaging step (`-p`) creates the two packages under `obj/<toolchain>`.


## Note for Windows

The example fails on Windows with the following error:

```
OSError: [WinError 193] %1 is not a valid Win32 application
```

Windows has no file type association for `.py` scripts that can be used when
a script is started directly, so the operating system cannot execute
`custom_build_script.py`.

As a workaround on Windows, use a launcher that Windows can execute directly,
e.g., a `.cmd` file that calls the Python script, and list it in
`build-scripts` instead:

```bat
@echo off
python "%~dp0custom_build_script.py" %*
```
