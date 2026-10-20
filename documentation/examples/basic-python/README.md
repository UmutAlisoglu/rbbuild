<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# Summary

This example demonstrates the basic functionality of rbbuild:
* Integration of uv as build system for Python source code
* Packaging binaries to a archive or package manager file

This example deliberately shows the whole rbbuild workflow in
combination with uv as backend. Other examples will spotlight
the use of rbbuild with other backends (C++ or pure rbbuild).


# Description

## Files

This folder contains the following source code files:
* **pyproject.toml**: Standard Python project file with rbbuild-specific items.
* **mypython-rbbuild**: This folder contains the main Python module files.


## Using rbbuild

This example uses a third-party dependency (requests). In rbbuild,
local dependencies are stored in the `staging` folder by calling `rbbuild -FI`:
* **fetch** (`rbbuild -F`): downloads dependency packages and stores them in
  a cache folder (e.g., `$HOME/.cache/rbbuild`)
* **install-deps** (`rbbuild -I`): populates `staging/.../` folder with
  dependencies. In the context of this example, a Python *virtual environment*
  (venv) is created under `staging/linux-native/.venv`.

When compiling the code with `rbbuild -sb`, the `obj` build folder is
created. However, since no code is actually compiled, the `obj/.../`
folder remains empty.

The next step is to create a Python `wheel` and `sdist` package:
* **package** (`rbbuild -p/--package`): this command invokes uv packaging
  mechanism and creates the `wheel` and `sdist` packages.

By calling `rbbuild -c/--clean`, the user can also remove contents of the `obj`
folder after any stage of the rbbuild workflow.

`rbbuild -cf` will also delete the `staging` folder.

