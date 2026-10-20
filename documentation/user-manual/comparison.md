<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# rbbuild in comparison to other tools

rbbuild is not a single-purpose build tool. It combines
* a **build and packaging driver** for C/C++ (CMake), Python and npm projects,
* a **dependency manager** for binary packages that are published to
  Artifactory channels, including version resolution and conflict detection,
* a **package and SBOM generator** (manifest.json and CycloneDX), and
* a **PEP 517 build backend** (`rbbuild.buildsystem.build`) for Python wheels.

Because of this scope, there is no one-to-one replacement for rbbuild in the
open-source world. This document positions rbbuild against tools that cover
one of these areas. It is meant as a decision aid, not as a ranking.


# Python build tools

The tools in this section create wheels and source distributions from a
`pyproject.toml`. Most of them are *build backends* (PEP 517) that are called by
a *frontend* such as pip, uv, or `python -m build`.

| | rbbuild | flit-core | hatchling | setuptools | scikit-build-core |
|---|---|---|---|---|---|
| Purpose | Project build tool with own backend | Minimal backend for pure Python | Backend of the Hatch project manager | General-purpose backend | Backend for CMake-based extensions |
| Pure Python wheels | Yes | Yes | Yes | Yes | Yes |
| Wheels with compiled code | Yes, CMake builds the code; wheel is tagged by `platform-specific` | No | Via build hooks | Yes (`Extension`, `build_ext`) | Yes (CMake) |
| Several wheels from one repository | Yes (`[packaging.<name>]`, `depends-on`) | No | Limited | No | No |
| Compiled code is built by | CMake step of the same `rbbuild` call | - | Custom hook | `build_ext` / compilers | CMake |
| Version scheme | Derived from major.minor, date and CI build number | Static or module attribute | Static, or plugin (e.g., `hatch-vcs`) | Static, or plugin (e.g., `setuptools-scm`) | Static or plugin |
| Needs the tool to build | Yes (`build_wheel` and `build_sdist` only work when called by rbbuild) | No | No | No | No |
| Publishing | Artifactory channels | `flit publish` / twine | `hatch publish` / twine | twine | twine |
| Build-time dependencies | Large (uv, cmake, ninja, ...) | None | A few small packages | Small | CMake, Ninja |
| Ecosystem | Small | Large | Large | Largest | Medium |

## What is different in rbbuild

* **One command for C/C++ and Python.** `rbbuild -sbp` compiles with CMake and
  creates the wheel from the results of the same build, see the examples
  [python-ctypes-c](../examples/python-ctypes-c/README.md) and
  [python-cext-c](../examples/python-cext-c/README.md). Other backends delegate
  this to hooks or to a CMake-specific backend.
* **Python is one output of many.** The same project can also produce rbbuild
  archive packages, an SBOM and a manifest, and these are published together.
* **Profiles and toolchains.** Targets (e.g., native, cross-compiling) and
  repositories are selected by profile and toolchain, not by build isolation
  environment.

## Where the other tools are stronger

* **Standard workflows.** pip, uv and `python -m build` work with flit, hatch,
  setuptools and scikit-build-core out of the box. Projects with the rbbuild
  backend are built by rbbuild; only editable installs (PEP 660) work with a
  plain `pip install -e .`.
* **Wheels for PyPI.** rbbuild tags native wheels with the platform of the
  Python interpreter (e.g., `linux_x86_64`). It does not create `manylinux` wheels
  or run `auditwheel`, so such wheels are suitable for internal indexes, not for
  PyPI. cibuildwheel together with scikit-build-core or setuptools is the usual
  choice for PyPI.
* **Lightweight builds.** flit-core has no dependencies; building a wheel with
  rbbuild requires its whole dependency set.
* **Python version.** rbbuild requires a recent Python (see README.md).
* **Community and tooling.** The other backends have wide documentation, many
  plugins and a large user base.

## Choosing

* Pure Python library for PyPI: flit-core, hatchling or setuptools.
* Python package with a few C extensions, built for PyPI: scikit-build-core,
  setuptools or meson-python (with cibuildwheel).
* Product with C/C++, Python and further components, built for several
  targets and delivered through Artifactory with SBOM: rbbuild.


# C/C++ build and package tools

| | rbbuild | CMake | Meson | Conan | Bazel |
|---|---|---|---|---|---|
| Type | Build driver, package and dependency manager | Build system generator | Build system | Package manager | Build and test system |
| Describes the build | `CMakeLists.txt` (plain CMake) plus `rbbuild.toml` | `CMakeLists.txt` | `meson.build` | `conanfile.py` / `conanfile.txt` (calls a build system) | `BUILD` files and Starlark |
| Builds code | Via CMake and Ninja | Via generators (Ninja, Makefiles, ...) | Via Ninja or other backends | Via the build system of the package | Itself, hermetic and incremental |
| Binary packages | Yes, tar.xz (or CPack formats) with manifest.json and SBOM | CPack | No | Yes (Conan packages) | No, build outputs and caches |
| Dependency resolution | Resolves versions across channels, reports conflicts | `find_package`, `FetchContent` | Wraps and subprojects | Yes (version ranges, lock files) | Modules (`MODULE.bazel`), versions pinned by the registry |
| Dependencies are | Prebuilt packages from channels, or source archives given by URL | Found installed or fetched | Wraps (source) or system | Binary packages or built from the recipe | Built from source |
| Cross-compilation | CMake toolchain files, selected with `-t` | Toolchain files | Cross files | Build and host profiles | Platforms and toolchains |
| Languages | C/C++, Python, npm | C/C++ and others | C/C++ and others | C/C++ | Many |
| Remote caching | Download cache of packages | No | No | Binary package cache | Remote cache and execution |
| Public package index | No (organization-defined channels) | No | WrapDB | ConanCenter | Bazel Central Registry |

## CMake and Meson

rbbuild is *not* an alternative to CMake: it runs CMake (with Ninja) and adds
the parts around it, such as toolchain selection, versioning, packaging, SBOM and
publishing. Projects keep a plain `CMakeLists.txt` and call a few rbbuild
commands (`include(RBBuild)`, `RBPackage()`). CMake's own CPack is used for the
archives.

Meson is an alternative to CMake. rbbuild only supports CMake as C/C++ build
tool and has no Meson integration.

## Conan

Conan and rbbuild solve overlapping problems: building, packaging and
consuming binary C/C++ packages with versions and toolchain variants.

* **Ecosystem.** Conan has a public index (ConanCenter) with many libraries and
  a recipe format that is widely known. rbbuild has no public index; packages
  come from the channels of an organization.
* **Binary compatibility.** Conan models settings and options (compiler,
  architecture, build type, ...) and selects binaries with a package ID.
  rbbuild encodes the toolchain in the package file names (`<package>-<version>-<toolchain>-...`)
  and keeps the variants simple.
* **Recipes.** In Conan, every package needs a recipe. In rbbuild, a package is
  the result of building a repository with a `CMakeLists.txt`; no extra
  recipe is needed.
* **Languages.** rbbuild handles Python wheels, npm packages and C/C++ together,
  and delivers one manifest and SBOM for all components. Conan is C/C++ focused.
* **Third-party sources.** Both can take source archives of third-party code
  (rbbuild by URL, see the zlib example). Conan recipes can build them for each
  configuration; rbbuild packages are built by the project that owns them.

Conan is the better fit for projects that use many open-source C/C++ libraries
and want a public ecosystem. rbbuild is the better fit where packages are built
and published in-house, and where C/C++ and Python artifacts need a common
delivery path with SBOM.

## Bazel

Bazel is a build system for large, multi-language repositories (monorepos),
with hermetic builds, fine-grained caching and remote execution.

* **Scale.** Bazel rebuilds only what changed, across languages, and can
  distribute builds. rbbuild builds one repository per package with CMake and
  exchanges *binary packages* between repositories.
* **Model.** Bazel builds everything from source in one graph. rbbuild's model
  is many repositories, each with its own build and release cycle, connected by
  versioned packages.
* **Effort.** Bazel requires `BUILD` files (or rules for every language) and a
  Bazel-specific project structure. rbbuild uses plain CMake and Python files.
* **Ecosystem.** Bazel has large community rule sets (`rules_cc`, `rules_python`,
  ...) and tooling.

Bazel fits one large repository where the whole build graph can be controlled.
rbbuild fits a landscape of independent repositories whose binary results are
versioned, scanned and consumed by others.


# Summary

| Need | Suggestion |
|---|---|
| Publish a pure Python library to PyPI | flit-core, hatchling or setuptools |
| Python wheels with C/C++ code for PyPI | scikit-build-core or setuptools, with cibuildwheel |
| Use many public C/C++ libraries | Conan (with CMake or Meson) |
| One large repository, fast incremental builds | Bazel |
| In-house C/C++, Python and npm components with cross toolchains, Artifactory delivery and SBOM | rbbuild |
