<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# General deps.json Structure

> **Note:** `deps.json` is the legacy dependency format. Since rbbuild 6, [`rbbuild.toml`](rbbuild.toml.md) is the preferred format.
> If `rbbuild.toml` contains a `[dependencies]` section, `deps.json` is ignored.
> The dependency entry syntax, configuration flags, version format, and variable substitution are identical in both formats
> and are documented in [rbbuild.toml — Dependencies](rbbuild.toml.md#dependencies-and-dependencies).

The dependencies file is a JSON-formatted text file that consists of a list of
packages that need to be installed. This file is called "deps.json" and is
usually located in the top-level directory of a component source repository.

A typical deps.json file looks as follows:

```json
{
    "/": {
        "deps": [
            "nng_cxx-1.1.1541.74 build_only"
        ],
        "components": ["prod", "licenses"]
    },
    "/cmake_from_sources": {
        "deps.linux" : [
            "sources-channel:cmake-3.25.1-linux-x86_64"
        ],
        "deps.win32" : [
            "sources-channel:cmake-3.25.1-windows-x86_64"
        ]
    },
}
```

A deps file consists of the following elements:
* **Namespaces** start with `/` character
* **Package dependencies** are part of a list under an element starting with "deps"
* **Section attributes** define common attributes for all packages in the same namespace

## Namespaces

A namespace is an organization method inside deps.json files. The most frequent
use of a namespace is the "default" namespace (simply "/"). By setting a
namespace, the following effects will happen:
* Calling `rbbuild -I` will install each package in a namespace into
  staging/<toolchain>/<namespace>.
* To override this behavior, the configuration parameter "installdir" must be set.

The generated manifest.json will sort all dependency packages by its namespace name.


## Package Dependencies

A configuration block allows to set variables that are applied to each deps entry in the dependency block.
Note that configuration block settings will be overridden by conflicting entries in the deps entry line.

Consider the following deps.json file:

```json
{
    "/" : {
        "deps" : [
            "yocto_rootfs       components=prod,licenses suffix=tar.gz build_only",
            "mtd_utils          components=prod,licenses suffix=tar.gz build_only",
            "background_monitor components=prod          suffix=tar.gz build_only",
            "fscryptctl         components=prod,licenses suffix=tar.gz build_only",
            "hwclock            components=prod,licenses suffix=tar.gz build_only",
            "micropython        components=prod,licenses suffix=tar.gz build_only"
        ]
    }
}
```

Note the `components`, `suffix` and `build_only` flags specified in each deps entry. This file can be
rewritten and, thus, simplified as follows:

```json
{
    "/" : {
        "deps" : [
            "yocto_rootfs",
            "mtd_utils",
            "background_monitor components=prod",
            "fscryptctl",
            "hwclock",
            "micropython"
        ],
        "components" : ["prod","licenses"],
        "suffix" : "tar.gz",
        "build_only" : true
    }
}
```

Only the entry `background_monitor` has a `components` flag because it is different from the rest.


# Dependency Entries

Each item in a "deps" block represents a so-called *Dependency Entry*, or *entry* for short.
In its simplest form, an entry represents a package with an optional version, e.g., `nng` or
`boost-1.69.0.9`. However, this representation is often not sufficient. For instance,
to narrow the package to specific components and file suffix, one would need to define this
as follows:

```
boost-1.69.0.9 components=dev suffix=tar.xz
```


## Normal Form of Entries

The normal form of an Entry is a dictionary object in the "deps" block.
Beside the specification of identification options that are included in the PackageURL string,
it also allows to convey meta-data for package SBOM generation. For example:

```
{
    "/" : {
        "deps" : [
            {
                "entry": "https://www.zlib.net/zlib-1.3.1.tar.gz",
                "build_only": True,
                "licenses": ["MIT"],
                "copyright": "(C) 1995-2022 Jean-loup Gailly and Mark Adler"
            }
        ]
    }
}
```

In this example, `entry` is a URL string or a rbbuild package. All other hash
items are called `attributes`.


## Configuration Flags

Configuration flags are shared with `rbbuild.toml`.
See [Configuration Flags](rbbuild.toml.md#configuration-flags) for the full reference.


## Dependency Block

A deps entry is either a line in the deps file, or an argument to the pkq tool.

The deps entry is used to allow the specification based on platform (`linux` or
`win32`), by toolchain ID (e.g., `yocto-armhf-4.0`). Additionally, wildcard
patterns may be used for toolchains (e.g., `yocto-armhf-4.?`). Further examples:

```json
{
    "/": {
        "deps.visualstudio-????"
            <-- will match visualstudio-2017 and visualstudio-2019, but not visualstudio-2017-x64
        "deps.yocto-armhf-2.*"
            <-- will match yocto-armhf-2.2 and yocto-armhf-2.4
    }
}
```


## Variable Substitution in deps.json

Dependency entries can contain `$PACKAGE_*` variables that are substituted at
resolve time. For example:

```
mypkg-$PACKAGE_VERSION  →  mypkg-1.2.3.4
```

For the full list of available variables, see [Version Syntax and Variable Substitution](rbbuild.toml.md#version-syntax-and-variable-substitution) in the rbbuild.toml documentation.


# Version Syntax

The version syntax is identical to `rbbuild.toml`. See [Version Syntax and Variable Substitution](rbbuild.toml.md#version-syntax-and-variable-substitution) for the full reference.


# Syntax

## deps.json

## Specification of a deps entry

Deps entries, in general, consist of either custom rbbuild or URL string entries.


### Custom rbbuild deps line entries

```
rbbuild:
  [<channel>:]<pkg>[-<version>|@<version>|@] [<attr1> <attr2> <...>]

with:
  <channel>   -- Channel name    --> must not contain whitespaces
  <pkg>       -- package name    --> must not contain whitespaces
  <version>   -- package version --> exact version or PEP 508 constraint
  <attrn>     -- Attribute (<key> or <key>=<value>)
```


### Plain version entry

This is a simplified format that is used for source packages in internal repositories (e.g., Artifactory).

```
[<channel>:]{<pkgname>|<pkgname>-<verstr>|<pkgname>@<verstr>|<pkgname>@} <flag>*
Where:
    <_namestr> = [a-zA-Z_][a-zA-Z_0-9]*
    <channel> = <_namestr>
  <pkgname> = [a-zA-Z_][a-zA-Z_0-9-]* # Package name; use @-syntax if name contains '-'
    <verstr> = [a-zA-Z_0-9\*]* # version string
```

Examples:
* `sample-sources:zlib`        (selects latest available package)
* `sample-sources:zlib<1.3`    (selects latest matching package under constraint)
* `sample-sources:zlib-1.3.1`  (selects exact zlib-1.3.1 package)
* `sample-sources:my-lib@2.4`  (selects exact version for dashed package name)
* `sample-sources:my-lib@`     (selects latest available version for dashed package name)


### External URLs (generic)


# Installation of dependencies into the staging folder

Entries that are specified in `deps.json` will be installed locally into the so-called
*staging directory*, which is usually called `staging` and placed in the same folder as
`deps.json`. The installation is executed with
```
rbbuild -I   # add -F to also fetch the dependency files from remote
```

Depending on the file type (determined by the file suffix), the package will be handled
differently. The current default behavior is:
* Archive files with standard suffixes such as `zip`, `tar.gz`, or `tar.xz` will be
  extracted into the staging folder.
* All other files will be copied into the staging folder.

This behavior can be changed with the deps entry flag `package\_install\_action`.


## Staging folder and CMake

To build C/C++ components with **rbbuild**, compile and link-time dependencies
need to be managed. With [find\_package](https://cmake.org/cmake/help/latest/command/find_package.html),
CMake provides a standard way to organize include directories and libraries.

Upon calling `rbbuild -s` or `rbbuild -b`, CMake variables, such as [CMAKE\_STAGING\_PREFIX](https://cmake.org/cmake/help/latest/variable/CMAKE_STAGING_PREFIX.html)
are set so that the `find_package` mechanism works as expected.


## Staging folder and Python

rbbuild sets up the folder `staging/<tcid>/.venv` in projects using `pyproject.toml`
with Python dependencies defined.

