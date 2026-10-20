<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# rbbuild Command-Line Interface


## Files and folders

Conceptually, **rbbuild** maps one-to-one relations between components, git
repositories, and Artifactory locations. This is not a strict
requirement, but eases the understanding of how rbbuild works.

The following files and folders are used by **rbbuild** in the
top-level folder of a git repository:
* [rbbuild.toml](rbbuild.toml.md): rbbuild configuration of a repository and
  specification of dependencies is defined in this file.
* `pyproject.toml`: Only for Python projects: includes content
  of rbbuild.toml. If this file is present, entries in rbbuild.toml have precendence.
* obj: build output folder. A subfolder for the selected toolchain will be
  created, e.g., *obj/yocto-armhf-4.0*.
* staging: intermediate folder to store dependencies. A subfolder for the
  selected toolchain will be created, e.g., *staging/yocto-armhf-4.0*
* `Jenkinsfile`: Interface file to Jenkins. If *Jenkinsfile.rbbuild*
  exists, it will be used instead of Jenkinsfile. This allows concurrent Jenkins jobs.
* CMakeLists.txt: build and packaging information. Note: rbbuild builds projects with
  plain CMakeLists.txt. Packaging requires extra instructions to be set.


### Deprecated files

* [deps.json](deps.json.md): JSON-formatted file with package dependencies
* [deps](deps.json.md): line-based text format that was used before `deps.json`.
  Deprecated since rbbuild 5.
* `version.properties`: File to set component name,
  major and minor revision. Deprecated since rbbuild 6.


### Artifactory caching and the dist path

To improve performance and speed-up development time, a sophisticated caching
mechanism is realized in **rbbuild** and **pkq**.

*rbbuild -F* downloads and caches files into the so-called **dist** path (e.g., `$HOME/.cache/rbbuild/dist`).
This folder caches files as follows:
* Any manifest.json file that has been queried will be cached and stored in the
  same folder structure as on the Artifactory server, e.g.,
  `sample-development/components/boost/1.79.1825-master.80/manifest.json`.
  Since these manifest.json files are supposed to never change, they will be
  reused from cache on version matches.
* Any file that has been actually downloaded will be stored in this structure
  if the download was successful and the file integrity is verified.
  Like manifest.json handling, subsequent requests to the same file will result
  in cached downloads rather than actual networking file transfer from
  Artifactory.

The caching mechanism can be overriden by adding the `-f` parameter, e.g.,
`rbbuild -f -F` will always download the manifest.json and the actual data
from Artifactory and ignore the cache.


## Actions

The functions **rbbuild** provides are called *actions* and they can be
combined in a single rbbuild call. The order of execution corresponds to
the order listed below:

* **fetch** (`rbbuild -F`): download dependencies that are specified in a file
  called [deps.json](deps.json.md).
* **install-deps** (`rbbuild -I`): install downloaded dependencies into a
  staging folder (under `staging/<tcid>` relative to the deps.json file)
* **setup** (`rbbuild -s`): setup and generate the build files
* **build** (`rbbuild -b`): build project
* **install** (`rbbuild -i`): install built artifacts into the staging folder
* **clean** (`rbbuild -c`): delete obj folder.
** If combined with `-f`, the staging folder will be cleaned as well.
** If combined with `-t <tcid>`, only the selected toolchain folder will be deleted.
* **test** (`rbbuild -T`): if available and configured, execute CTest
  and then PyTest
* **documentation** (`rbbuild -D`): execute the `documentation` action and
  run the configured documentation tools (for example, Pandoc and/or Sphinx)
* **package** (`rbbuild -p`): create distribution package as
  configured in CMakeLists.txt
* **execute** (`rbbuild -x`): execute a built program with environment
  variables set (PATH, LD_LIBRARY_PATH, etc)
* **publish** (`rbbuild --publish`): upload package files onto a binary
  repository (Artifactory). On a version conflict, a 5th version digit is
  appended/incremented and publish is retried automatically.
* **upload** (`rbbuild --upload`): like publish, but used to upload non-rbbuild files
* **delete** (`rbbuild --delete`): delete a file from a channel
* **sca** (`rbbuild --sca`): static code analysis

For CMake/pypa/npm-based packages, a version-conflict retry repackages using
the bumped (5-digit) version, but component filenames and any version baked
into generated C/C++ headers still show the original 4-digit version. This
is not a problem: `manifest.json` still references those files correctly,
and the first 4 digits already identify the build uniquely.

Without any parameters, **rbbuild** will execute the actions *setup* and
*build* by default.


## Static code analysis

`rbbuild --sca` runs the tools listed in `sca-tools` (default: `ruff`, see
[rbbuild.toml.md](rbbuild.toml.md)). [ruff by Astral](https://docs.astral.sh/ruff/)
checks projects that have a `pyproject.toml`, `ruff.toml` or `.ruff.toml`.
Without any SCA tool, rbbuild prints a warning. If ruff reports findings,
rbbuild ends with a non-zero error-code. The ruff configuration can come from two sources:

* the project: `ruff.toml`, `.ruff.toml` or `[tool.ruff]` in `pyproject.toml`
* the profile: `ruff.toml` in the profile folder, with common rules for all
  projects (if the profile has none, the one of an imported profile is used)

| Project configuration | Profile `ruff.toml` | ruff is called with |
|---|---|---|
| any | no | ruff's normal config discovery |
| none | yes | `--config <profile ruff.toml>` |
| yes, without `extend` | yes | `--config obj/<tcid>/ruff.toml` (generated) |
| yes, with `extend` | yes | ruff's normal config discovery (profile ignored) |

The generated `obj/<tcid>/ruff.toml` contains the project settings and
`extend = <profile ruff.toml>`. Hence, project settings take precedence, with
the semantics of ruff: for example, `select` in the project replaces the profile
rules, while `extend-select` adds to them.

ruff does not infer `target-version` from `requires-python` if `--config` is
used. In that case, rbbuild derives it from `requires-python` in
`pyproject.toml`, unless the project or the profile sets `target-version`.


## Single-shot Actions

Single-shot actions will execute and cannot be chained:
* **list** (`rbbuild -l`): list available toolchains.
* **generate** (`rbbuild -g <path>`): generate project scaffold files in *path* and exit.
  By default, `rbbuild.toml` and `Jenkinsfile` are generated.  The source
  directory is also inspected: if C/C++ files are found, `CMakeLists.txt` is
  added; if Python files are found, `pyproject.toml` is added.
  Pass `--generate-files` to select specific files explicitly:

  ```
  rbbuild -g myproject --generate-files rbbuild.toml Jenkinsfile CMakeLists.txt
  ```

  Supported file names: `rbbuild.toml`, `Jenkinsfile`, `CMakeLists.txt`,
  `pyproject.toml`, `.gitignore`, `tasks.json`.


## Using rbbuild generated Visual Studio project files

Visual Studio project files are generated by calling `rbbuild -s`. Afterwards, the solution
can be opened under `obj\<tcid>\myproject.sln`, where `tcid` is the toolchain ID
(e.g., `win32-visualstudio-2022-x64`).


# CMake Integration

To enable certain features of **rbbuild**, `CMakeLists.txt` needs to contain
certain calls. A minimal example looks as follows:

```
cmake_minimum_required(VERSION 3.25)
project($ENV{RBB_PACKAGE_NAME})         # Derived from version.properties or git.

include(RBBuild)                        # Main include to make rbbuild
                                        # variables available

# 1. CMake build rules, e.g., add_executable, target_link_libraries, etc
# 2. CMake packaging rules using install()

RBPackage()                             # Finalizes packaging. Must be at the end of the file.
```

If these calls are not presents, functions like `rbbuild -p` will not work properly.
However, (cross-) compiling any project with a standard CMakeLists.txt is possible with rbbuild.


## Version variables available in CMakeLists.txt

After `include(RBBuild)`, the output files and packages will contain the
standard rbbuild versioning scheme:
```
<PACKAGE>-<MAJOR>.<MINOR>.<REVISION>.<BUILD>
```

Furthermore, the following variables are accessible in CMakeLists.txt:

| Variable name     | Description                                       |
|-------------------|---------------------------------------------------|
| VERSION_PACKAGE   | Package string derived from project name.         |
| VERSION_MAJOR     | Major number (defaults to 0)                      |
| VERSION_MINOR     | Minor number (defaults to 0)                      |
| VERSION_REVISION  | Revision number is the day since 2018-04-16       |
| VERSION_BRANCH    | Name of the GIT branch: <br> * Auto detected from git or environment<br> * Uses BRANCH_NAME environment variable if available<br> * Defaults to "local" |
| VERSION_BUILD     | Build number: <br> * Auto detected from environment<br> * uses BUILD_NUMBER environment variable if available<br> * Defaults to 0 |
| VERSION_SOURCES   | Generated version source files for the current package (see below) |
| VERSION_HEADERS   | Generated version header files for the current package (see below) |

The version information is written into the text file
`obj/<tcid>/generated/build_info.properties`, where `<tcid>` is the identifier of the toolchain.


## Revision Determination

The REVISION is the day since 2018-04-16. For example all builds on 2018-05-02
will have a REVISION number of 17 (seventeen days have passed since 2018-04-16),
i.e, `9.0.17.8`.


## Versioning Code Generation

Beside providing the above mentioned variables, the RBBuild CMake Module will
generate a C header and source file which exposes two API's for the application
to use (`<package_name>_version.h`):

```C
const rb_version_info* <package>_get_version_info(void);
const char* <package>_get_version_string(void);

```

The `struct rb_version_info` is defined in `rbversioninfo.h` as follows:
```C
typedef struct {
    int major;
    int minor;
    int revision;
    int build;
}
rb_version_info;
```

To make use of these generated files in CMakeLists.txt, the following solution can be used:

```
add_executable(target ${SOURCES} ${VERSION_SOURCES})
install(
    FILES ${VERSION_HEADERS}
    DESTINATION include
)
```

Example Code for a `helloworld` package:

```C
#include <stdio.h>
#include <helloworld_version.h>

int main(int argc, const char* argv[])
{
    const rb_version_info* vinfo = helloworld_get_version_info();

    printf( "Major: %d Minor: %d Rev: %d Build: %d\n", vinfo->major,
                                                       vinfo->minor,
                                                       vinfo->revision,
                                                       vinfo->build );
    return 0;
}
```

And the corresponding CMakeLists.txt:

```
cmake_minimum_required(VERSION 3.25)
project($ENV{RBB_PACKAGE_NAME})

include(RBBuild)

file(GLOB SOURCES src/*.c)
add_executable(helloworld ${SOURCES} ${VERSION_SOURCES})

RBPackage()
```


## CMake toolchain files

**rbbuild** tools operate with
[CMake toolchain files](https://gitlab.kitware.com/cmake/community/wikis/doc/cmake/CrossCompiling)
for cross-compilation.
The selection of a toolchain is done on the command-line with the parameters
`--toolchain` and `--platform`.

As of now, there are no special requirements on the content of toolchain files --
**rbbuild** works with any regular CMake toolchain file.
Each toolchain file is referenced by a toolchain definition (TOML file) of the
profile, see [rbbconf](rbbconf.md).


# Environment Variables


## Output environment variables

The following environment variables are exported by **rbbuild** when invoking
programs (e.g., cmake):

| Environment variable       | Description                           |
|----------------------------|---------------------------------------|
| RBB_ROOT                   | root path of the rbbuild installation |
| RBB_DIST_PATH              | Download path for cached Artifactory objects |
| RBB_TOOLCHAIN_ID           | The toolchain ID that has been used (e.g., yocto-armhf-4.0) |
| RBB_PACKAGE_NAME           | Package name                          |
| RBB_PACKAGE_MAJOR          | Package major version                 |
| RBB_PACKAGE_MINOR          | Package minor version                 |
| RBB_PACKAGE_REVISION       | Package revision                      |
| RBB_PACKAGE_BRANCH         | Package branch                        |
| RBB_PACKAGE_BUILD          | Package build number (from Jenkins)   |
| RBB_PACKAGE_VERSION        | Assembled package version string      |
| RBB_GIT_REPO               | Current git repository, if available  |
| RBB_GIT_HASH               | Current git hash, if available        |
| RBB_SOURCE_PATH            | Top-level source directory            |
| RBB_BUILD_PATH             | Build path, e.g., obj/linux-native/   |

All other environment variables from the calling context (e.g., console) will
be passed to **rbbuild** and the underlying subprocesses.


## Input variables

If defined, the following environment variables override the behavior of
**rbbuild**. This mechanism is primarily required to ease the Jenkins CI
interfacing:

| Environment variable       | Description                                    |
|----------------------------|------------------------------------------------|
| BRANCH_NAME                | Override branch name                           |
| BUILD_NUMBER               | Override build number                          |
| BUILD_REVISION             | Override revision                              |
| RBB_DISABLE_FETCH_PROGRESS | Suppress CLI progress output                   |
| RBB_CREDENTIALS            | Override Artifactory credentials               |
| RBB_CHANNEL                | Select the channel (`-C` has precedence)       |
| RBB_DEFAULT_CHANNEL        | (ignored)                                      |
| RBB_TOOLCHAIN_ID           | Select the toolchain (`-t` has precedence)     |
| RELEASE_BUILD              | release modifier for rbbuild --version strings |


# RBPackage: create installer packages

Using `rbbuild -p` allows to create installer packages. To do so, the
`CMakeLists.txt` needs to invoke `RBPackage()` at the bottom of the file.
Note that `RBBuild` must be included and called before in order to
set the package version correctly.

The following variables may be set in CMakeLists.txt:
* `RBPACKAGE_GENERATOR`: governs the set of deployed generator types
                         (default: "TXZ")
* `RBPACKAGE_COMPONENTS`: which install components to deploy
                          (default: all installed components)
* `RBPACKAGE_CUSTOM_ARTIFACTS_<cmp>`: add custom packages to deployment that
                                      are not "installed" via CMake.
                                      `<cmp>` is the subcomponent name (case is ignored).
* `RBPACKAGE_REQUIRES`: set package dependencies (e.g., "zlib >= 1.2.8")
* `RBPACKAGE_DESCRIPTION`: text field to describe the package itself.
                           Append `_<cmp>` to define per subcomponent descriptions.
* `RBPACKAGE_SOURCE_DIRS`: Package source directories for Doxygen and SonarQube
                           (CMake list or semi-colon separated string).
                           Note that the paths must be absolute, e.g.,
                           `${CMAKE_SOURCE_DIR}/source`
* `RBPACKAGE_DOXYGEN_DOXYFILE`: Specifies the Doxyfile to employ. If not
                                defined, generate from rbbuild template.


## Create a simple package

The [CMake install](https://cmake.org/cmake/help/v3.7/command/install.html)
mechanism is employed to select the files and targets to install.
The easiest way to create a package is to install the files that is previously
compiled with CMake:

```
add_executable(MyExecutable ${SOURCES})
install( TARGETS MyExecutable
         RUNTIME DESTINATION usr/bin )
```

Notice that the destination path is a relative path rather than an absolute path (/usr/bin).
It is possible to deploy non-targets, e.g., using `install(FILES ...)` or
`install(DIRECTORY ...)`.


## Installing Components

By default, `RBPackage` picks up all files that are installed for the target
package. However, sometimes it is necessary to distinguish between files that
are installed on the target device (such as executables and libraries) and the
staging area (e.g., library header files for local usage).
This is done using install components:

```
include(RBBuild)

install(
    TARGETS example-target
    COMPONENT prod
    RUNTIME DESTINATION usr/lib
)
# use COMPONENT dev to install headers which are only used locally
install(
    FILES ${API_HEADERS} ${VERSION_HEADERS}
    COMPONENT dev
    DESTINATION usr/include
)

RBPackage()
```

In this case, `rbbuild -i` will install all files as specified by `install()`,
however, only targets belonging to COMPONENT "prod" will be packaged in the
final package.


# Custom build scripts with rbbuild

Users can choose to build custom build scripts instead of CMake or other buildsystems.
To do so, they user has to provide a script file in the top-level source folder.
By default, script files starting with `rbbuild-build.` are selected. Otherwise, the user
can configure a list of scripts in rbbuild.toml as follows:

```
[rbbuild]
build-scripts = ['custom_script1.py', 'custom_script2.py]
```

For the remainder this section, we will use `rbbuild-build.sh`, but any suffix will be
accepted.
For cross-platform build scripts, it is recommended to implement the build script in Python.


## Interface specification

The custom build script is called as follows:

```
`rbbuild-build.sh` -j N target
```

Where `target` is the (optional) build target that allows to pass specific arguments from
rbbuild to the build script. The option `-j N` passes the maximum number of parallel jobs.
All arguments may be ignored by the build script.

The script is from the top-level source path (where the script itself resides).

In addition, Environment variables, such as `RBB_PACKAGE_VERSION` or `RBB_TOOLCHAIN_ID`
are accessible from the script when executed via rbbuild.


## Example

Example `rbbuild-build.sh` script:

```shell
#!/bin/bash

OUTFILE="$RBB_BUILD_PATH/my_component"

echo "Custom build script $@ ..."                 > $OUTFILE
echo "RBB_TOOLCHAIN_ID: $RBB_TOOLCHAIN_ID"       >> $OUTFILE
echo "RBB_PACKAGE_VERSION: $RBB_PACKAGE_VERSION" >> $OUTFILE
echo "OUTFILE=$OUTFILE"
```

```shell
rbbuild -sb        # This will call rbbuild-build.sh
```

To package the outcome of the build script with `rbbuild -p`, add the following
configuration to rbbuild.toml:

```
[packaging.my_component]
files = ['$OBJ/my_component']
```


# Doxygen integration

**rbbuild** provides a facility to generate Doxygen HTML output:
* In CMakeLists.txt set the variable `RBPACKAGE_SOURCE_DIRS` to the source directories
  that need to be scanned (see above).
* Call `rbbuild doc` The output is in obj/<tcid>/generated/doc.

A requirement for this feature to work is that the packages `doxygen` and `graphviz` are installed.


# Enable bash-completion for rbbuild

Bash-completion for **rbbuild** and the other command line tools is described
in [bash_completion.md](bash_completion.md).


# rbbuild test framework

`rbbuild -T` executes tests of a component:
* CTest (part of CMake) will be executed if any tests were defined in the `CMakeLists.txt`
* If there are any tests defined in Python, they will be executed with `pytest`
Both tests will be invoked in order for all components in the Jenkins after
compilation. If there is no test defined, **rbbuild** will still return with return code 0.
If a test is defined but the test fails, **rbbuild** will also fail.
The tools are selected with `test-tools` (see [rbbuild.toml.md](rbbuild.toml.md)).
Without it, CTest runs for CMake projects and `pytest` for projects built with `pypa`;
to run `pytest` in a CMake project, set `test-tools = ['ctest', 'pytest']`.
On success, rbbuild will place the results in `obj/<tcid>/Testing`.
The xUnit XML files are then displayed in Jenkins (currently in progress).


## Unittests with CTest

In order to use CTest, the CMakeLists.txt needs to be extended:

* Add `enable_testing()` in the upper parts of the CMakeLists.txt (which
  essentially adds the "test" target).
* Add targets to compile unittests with `add_executable()` (preferrably
  with Google Test).
* Enable the test with `add_test()`.

The tests should be separated from the normal source code in a dedicated folder
with CMakeLists.txt. The folder should be named `unit_tests` (this is not a
must, but helps to understand the structure of a component better).

Unittests can only be executed on the `linux-native` or `win32-visualstudio` toolchain.
Thus, the CMakeLists.txt should be configured this way to avoid failures on cross-builds:

```
if (${RBB_TOOLCHAIN_ID} STREQUAL native)
    enable_testing()
endif()
```

## Component testing with pytest

While `pytest` is the de facto standard tool for unittests under Python,
`pytest` is also an excellent choice for platform independent black-box tests
(aka component test). To use `pytest` with rbbuild, the following needs to be
considered:
* `pytest` will scan all folders of the component for the presence of Python
  tests, e.g., all files starting with `test_*.py` will be collected and
  executed.
* `pytest` will also include unittests within regular .py files, e.g., methods
  starting with `test_` and classes starting with `Test`.
* To add fixtures and test configurations, the file conftest.py will be
  included before executing the tests.
* To avoid that the unittest is being executed for all toolchains that are
  defined in the Jenkinsfile, the environment variable `RBB_TOOLCHAIN_ID` is
  made available for the tests. This variable contains the toolchain string,
  e.g., "visualstudio-2017" or "yocto-armhf-2.2".
Blackbox tests should be separated from the normal source code in a dedicated
folder with CMakeLists.txt.
The folder should be named `component_tests` (again, this is not a must, but
helps to understand the structure of a component better).

Often, component tests only make sense when using the native or visualstudio
toolchain because the generated executables are not runnable on ARM.
To address this problem,
[test modules can be skipped completely](https://docs.pytest.org/en/latest/skipping.html):

```python
import pytest
import os

if os.environ['RBB_TOOLCHAIN_ID'] != 'native':
    pytest.skip("Test with selected toolchain is not supported", allow_module_level=True)

def test_mytest():
    # test implementation
```

Alternatively, individual tests can be disabled conditionally

```python
import pytest
import os

supported_tc = pytest.mark.skipif( os.environ['RBB_TOOLCHAIN_ID'] != 'native', reason="Test with selected toolchain is not supported" )

@supported_tc
def test_mytest():
    # test implementation
```


## Running tests with rbbuild

The specifics of the **rbbuild** test implementation will be outlined in this
section.

* **rbbuild** adds the parameter `-T` as "action", which means that it
  can be easily combined with other rbbuild parameters.
  Consider for example:
  ```
  rbbuild -sbT -t native
  ```
  This call will `setup`, `build`, and then `execute` the tests for the "native"
  toolchain (the order of the parameters are as usual irrelevant).
* `rbbuild -T` requires that the `obj/<tcid>` directory has been initialized
  with `rbbuild -s` before.
* Some tests also require that the test executable or the unit under test has
  been built before (with `rbbuild -b`).
* It is possible to invoke ctest or pytest via rbbuild individually:
  ```
  rbbuild -T pytest
  rbbuild -T ctest
  ```
* It is possible to build individual targets with this command:
  ```
  rbbuild -b my_target
  ```
* If -T is present and ctest or pytest is added, these strings will not be
  interpreted as targets for build. Consider:
  ```
  rbbuild -sbT pytest
  ```
  This call will execute the pytest run, but not build the target "pytest".
  To accomplish this task, one has to split the rbbuild command:
  ```
  rbbuild -sb pytest  # assuming this is a named target in the CMakeLists.txt
  rbbuild -T pytest   # execute the pytest test run.
  ```

