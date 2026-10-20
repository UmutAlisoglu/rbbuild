<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# Version 5.4 and beyond

rbbuild version after 5.3 and before 6.0 are maintained on a separate branch.
The changes made there are mostly related to toolchains/project profiles and
environment specific bugfixes. Thus, the details for the following versions are not
listed in this document:

| rbbuild version | release date |
|-----------------|--------------|
| 5.4             | 2024-06-12   |
| 5.5             | 2025-03-10   |
| 5.6             | 2025-04-28   |
| 5.7             | 2025-08-27   |
| 5.8             | 2025-11-05   |
| 5.9             | tba          |


# Version 5.3 (released 2024-01-15)

- Change SonarQube server URL
- FossID wrapper changes:
  - prevent git action on blacklisted scan codes
  - force a re-scan of an already passed marked scan
  - scan against the base project on which the scans belong to reuse identifications from there
  - Add scan URL via `parse_manifest` generated csv file
  - Update FossID global ignore rules to exclude files and folders from specific scans
  - Fix FossID SDK include path within `parse_manifest` wrapper
- `pkq`: handling of missing call parameter


# Version 5.2 (released 2023-06-06)
- Added new arm toolchains


# Version 5.1 (released 2023-03-08)

- Fix promote issue for manifest files
- Upgrade to CMake 3.25.1
- Correct / unify `CMAKE_SYSTEM_PROCESSOR` for Windows toolchains
- Added rbbuild `licenses` component


# Version 5.0 (released 2023-02-28)

- rbbuild has become an Bosch internal InnerSource project!
- Move all third-party programs out of the rbbuild git repo to Artifactory
- Removed http protocol from the config. Manifest url corrected.
- Removed `cotire.cmake` module.
- `pkq --show-commits=<n> --git` now additionally displays git information


# Version 4.14 (released 2022-10-18)

- Fix wildcards at end of deps entry for non-semantic versioning scheme
  (hotfix to correct bug introduced with previous version)


# Version 4.13 (released 2022-10-12)

- Fixed critical package resolution matching bug.
- Added support for Jira/Bitbucket `release/` branch name prefix.

# Version 4.12 (released 2022-09-23)

- `rb_add_executable_py` and `rb_add_library_py` functions added to the `RBPackage` CMake module.
  It runs PEP8 checks with `flake8` for Python scripts (turns into a no-op if flake8 is not found).
- Updated artifactory channels and toolchains
- Reworked internal channel redirect handling.
- `pkq -R` has a new option `--resolve-out=<file>`. This extracts the resolved version in a file.
- Added support for standard Jira/Bitbucket branch name prefixes `hotfix/`, `bugfix/`, and `feature/`.
- Added support for `Jenkinsfile.rbbuild` in addition to `Jenkinsfile`.
- rbbuild now evaluates the environment variables `RBB_EXTRA_C_FLAGS` and `RBB_EXTRA_CXX_FLAGS`.
  The purpose of this mechanism is to set custom compile flags, e.g: `RBB_EXTRA_CXX_FLAGS='-O0" rbbuild`
- Dependencies can be passed via command-line option `-L/--deps-line` to rbbuild.
  Example: `rbbuild -FI -L google_test::master -L boost`
- Added support for `set(RBPACKAGE_GENERATOR "DEB")`. This will create .ipk package files.
- Improved `rbbuild clean`.
- Increased priority of environment variables vs `version.properties`.
  For example, if `RBB_PACKAGE_NAME` env var is set, the value from `version.properties` is ignored.


# Version 4.11 (released 2022-05-04)

- `pkq --depsfile <deps.json> -o <deps.json>` now resolves wildcard versions.
  Only the selected toolchain will be evaluated. Use `-t` to select a different toolchain.
- `pkq` parameters `--deps` and `--skip` have been removed.
- `rbbuild` now creates a frozen `deps` file in `obj/<tcid>/generated/deps.json`.
  If present, this file is used instead of a deps.json file (`-F` or `-f` enforced normal resolution).
- Added new deps flags `restrict_platform` and `restrict_toolchain`, which allow to restrict the
  platform or toolchain respectively.
- Added experimental graphical user interface for `pkq -g / --gui`.
- Removed `rbbuild --param dist_path`. Use `RBB_DIST_PATH` environment variable instead.
- `pkq --changes` now allows to use abbreviated matches, e.g:
   ```
     # regular syntax
     pkg-9.1.88-branch.77..pkg-9.2.1-branch.99
     pkg-9.1.88-branch.77..9.2.1-branch.99
     pkg-9.1.88-branch.77..branch.99
     pkg-9.1.88-branch.77..99
     # :: syntax
     pkg::branch.77..pkg::branch.99
     pkg::branch.77..branch.99
     pkg::branch.77..99
  ```
- `pkq` argument changes:
  - Standard in is no longer read when no arguments are passed. Use `pkq -`.
  - `--changes` is deprecated and silently ignored. Instead, the input will be handled if it contains '..'.
  - Removed separator option (`-s`) as it conflicts with the new package string handling ('..').
  - `--depsfile` now aliases to `-i`
  - Added new parameter `-o <file>` which will write out to a file.
  - Added new option `-R / --resolve`, which resolves wildcard package strings to a
    `deps.json` file (can be combined with `-o`).
  - Combining multiple operations in a single pkq call is now disabled (e.g., `--list --tree`).
- Binrepo and channel handling has been refactored:
  - Remove support for legacy config parsing
  - Separation of config item and binrepo / channel objects
-  New parameter `-x/--execute` that allows running executables with rbbuild. This wrapper sets
   essential environment variables such as `PATH` and `LD_LIBRARY_PATH`.
   Example: `rbbuild -x program -- --param 1 --param 2`
-  GCC native and yocto-armhf-2.4 now always print color output
-  Upgrade third-party programs: CMake 3.22, Ninja 1.10.2
-  Corrected RPM architecture metadata from "armv7a" to "arm". This means, --ignorearch is no
   longer needed when installing RPM packages from rbbuild yocto-armhf-2.4.
-  Add support for `pytest` code coverage and upload on `SonarQube`.


# Version 4.10 (released 2021-05-05)

- `rbbuild -g` changes:
  - generates deps.json. Legacy deps files will be transformed, if present.
  - adds a symlink to .vscode/tasks.json. With this file and the Task Runner extension,
    executing rbbuild commands in *Visual Studio Code* will be eased.
- Add deps.json flag `foreign_toolchain` and `foreign_platform`. This allows `rbbuild -FI`
  to download and install packages from other toolchains.
- Update subsitution rules for package branch names.
- If `COMPONENT` is missing in CMakeLists.txt `install()`, `default` is set. Files belonging
  to subcomponent `default` will be stripped from the subcomponent entry. For instance:
     `pkg-1.2.3-master.4-default.rpm` becomes `pkg-1.2.3-master.4.rpm`.
- Add `RBPACKAGE_DESCRIPTION_<cmp>` CMakeLists.txt variable to allow defining RPM package descriptions per subcomponent.
- `rbbuild --publish` aborts with an error if the target file already existed on Artifactory.
- Add support for URL support in deps files, e.g.,
    `url:www.some-web-site/urlpkg.zip package=pkg_sources-1.2.3 suffix=zip`
  Large parts of the `staging_folder` and `deps_file` modules have been refactored.
- The deprecated `zip` and `rpm` deps flags will now fail to parse.
- Allow new syntax in deps: `<name>::<branch>.<build>`. This shorter syntax uniquely matches a package.
- The parameter `--offline` now avoids checking the online server.
- Deps entries containing "#" will now be cut-off (also in deps.json).
  Example: `googletest  # this is an example comment`.
- Artifactory search for non-wildcard packages will now also extend to other repositories if
  configured. For example, if a package is not found, the package lookup will be tried on
  the next configured channel.
- `RBPACKAGE_GENERATOR` defaults to TXZ, which will result in smaller (intermediate) build
  artifacts. On Windows, setups now also generate `tar.xz` files instead of `zip`.
  Removed the long-deprecated and unused `RBPACKAGE_GENERATOR_DEV` CMake variable.
- Extended `pkq --list=<n>`, where `<n>` is the number of items (default: 10).


# Version 4.9 (released 2020-11-26)

- `rbbuild -g <path>` now generates a template project or, if `<path>` exists, the following files
  if they are missing: `CMakeLists.txt`, `.gitignore`, `version.properties`, and `Jenkinsfile`.
- Add support for doxygen. rbbuild doc will now create doxygen output in `obj/<...>/generated/doc`.
  If `RBPACKAGE_DOXYGEN_DOXYFILE` was defined, it will be used as configuration file.
  Otherwise, a template is being used.
- `pkq --changes`: a package that has been moved into a different namespace will no longer
  appear as `new` and `deleted`, but `moved` instead.
- Add `-s/--separator` option to `pkq --changes`. This parameter allows a different string
  than `<old>..<new>`, e.g., `-s '\t'` will place a tab between the packages.
- If a package is queried in Artifactory (e.g., `rbbuild -F`), all manifest.json files of a
  matching package version will be cached on the local hard-disk.
  Due to caching, this is slow for the very first query, but much faster on subsequent calls.


# Version 4.8 (released 2020-09-18)

- Fix unpacking of dependency packages into the staging directory on Win32.


# Version 4.7 (released 2020-08-17)

- `manifest.json`: items in `build_only_comps` entry are now lexicographically sorted.
- Fixed a regression with the cache file handling (Artifactory connection is only used if needed).
  With this, minor changes to a few console outputs have been made.
- Added cache index for the staging directory. Subsequent `rbbuild -I` calls will be ignored to
  speed up the installation process.


# Version 4.6 (released 2020-07-21)

- `pkq --changes --show-commits` now only displays changed packaged
- Upgrade to CMake 3.17.3
- Export `RBB_PACKAGE_DEPENDENCIES` environment variable to be used by CMake.
- Updated several Artifactory channels
- `pkq --changes` also allows branches to be different. These packages are now displayed as:
  `changed` instead of `new` and `deleted`.


# Version 4.5 (released 2020-06-04)

- Only connect to Artifactory when it is actually used.
- Only connect to Bitbucket when it is actually used (`pkq --changes --show-commits`).
- The following environment variables are now evaluated:
  - `RBB_DIST_PATH`: override for `rbbuild --param dist_path`
  - `RBB_TOOLCHAIN_ID`: alternative to `rbbuild -t` (which has higher precendence)
  - `RBB_DISABLE_FETCH_PROGRESS`: overrides `rbbuild --param disable_fetch_progress`
  - `RBB_DEFAULT_CHANNEL`: alternative to `rbbuild --set default_channel`
  - `RBB_CREDENTIALS`: alternative `rbbuild --set credentials`
- Bitbucket repository is now extracted from `git_repo` entry in each package manifest.json.
  Consequently, the project configuration entry in section `[bitbucket]` has been removed.
- Allow to use patterns in deps.json for `<tcid>`, e.g., `deps.visualstudio-????`.
- Add back support for deps syntax `<pkg>::<branch>`.


# Version 4.4 (released 2020-02-17)

- Add new deps flag `package_install_action=copy`. With this flag, `rbbuild -I` overrides
  the default behavior for the file suffix. For RPM packages, it will now copy the files
  into the installdir rather than ignoring them.
- If a deps file contains the wildcard entries `boost` and `pkg` (which has a dependency on `boost`),
  the build will fail if there is a newer version of boost available than referenced in `pkg`.
  Before, the resolution algorithm would derive the boost version from `pkg`.
- Add support for *Visual Studio 2019* toolchain on Windows.


# Version 4.3 (released 2020-01-15)

- `pkq --changes` no longer displays merge commits by default. Instead,
  `pkq --changes --show-commits=<N>` will display the last N commits from Bitbucket.
  `pkq --changes --filter-changes=<filter>` lists packages that are filtered by:
  `new`, `deleted`, `changed`, `same`, and `*` (default; showing all packages).
- Refactored dependency resolution algorithm to provide much better results in rbbuild
  and pkq. One effect is that branches are now part of the package, which means for example
  `pkg-x.x.x-master.x` and `pkg-x.x.x-OTHERBRANCH.x` will not be marked as conflicting.
  However, their dependencies will conflict, unless one of the packages is marked `build_only`.
  The commits from Bitbucket are changed from merges to all commits. At the same time, the max.
  number of commits is lowered from 1000 to 100.
- `rbbuild -FI` now always prints the dependency tree on the console.
- rbbuild version string is written into manifest.json when publishing.
- Various changes have been made around the deps.json handling:
  - deps.json following the existing format form 4.2 is no longer supported.
    The new format can be reviewed in the rbbuild manual.
  - `rbbuild -C` is now deprecated and will be removed in the next release.
    Instead, namespaces are defined in deps.json and will be fetched automatically.
  - key identifiers in "dependencies" section in manifest.json are changed:
    old: `<pkgname>-<tcid>`            (e.g., `openssl-yocto-armhf-2.4`)
    new: `<pkgname>::<branch>@<tcid>`  (e.g., `openssl::master@yocto-armhf-2.4`)
    This change allows packages with the same name but different branches in the same deps file.
  - `rbbuild --no-traverse` has been deprecated and is now a no-op.
  - deps: add support for negated components (e.g., `components=~licenses`).
- `deps.json` now supports the definition of flags (e.g., `components=prod`) per namespace section.
  Per deps entry flags have precedence over section flags.
- The dedicated `subspace` section in `manifest.json` has been replaced in favor
  of packages in the dependencies section using the syntax `<namespace>/<pkg>`.
- `manifest.json` `json_version` is bumped to 3. Existing manifests v1 and v2 are still supported.
- Upgrade SonarQube CFamily build-wrapper to version 6.3. Removed Windows 32-bit variant.
- Upgrade SonarQube Scanner to version 4.2.0.
- Allow variables in rbbuild deps file entries: `$PACKAGE_VERSION`, `$PACKAGE_NAME`,
  `$PACKAGE_MAJOR`, `$PACKAGE_MINOR`, `$PACKAGE_REVISION`, `$PACKAGE_BRANCH`, `$PACKAGE_BUILD`.


# Version 4.2 (released 2019-09-23)

- `pkq <pkgstr>[..<pkgstr>] --changes[=file[.html]]` now generates a list of merge logs
  from Bitbucket for each component in the dependency tree of the selected package.
- Enhance terminal colors by environment variables:
  - `RBB_COLOR_ALWAYS_WRITE`: enables color output even on non-tty files.
  - `RBB_COLOR_SCHEME`: distinguish between "WhiteOnBlack" (current default) and "BlackOnWhite".
- Upgrade CMake to version 3.15.
- `pkq --list` now only displays versions that are available for the selected toolchain.
- Add support for deps.json. If this file is present, it will be used instead of regular deps files.
  Sections other than "common", <tcid>, and <platform> will be treated as namespace, making deps
  files in subdirectories (using `rbbuild -C`) obsolete. If used in conjunction with
  `rbbuild --depsfile`, the file must end with ".json", otherwise, the old text parser is used.
- rbbuild and pkq dependency resolution now selects first version that has a valid manifest rather
  than the latest version. This fixes build errors which are caused by removed toolchains in the
  Jenkinsfile, or half-built Jenkins pipeline jobs.
- `rbbuild -T` now also ignores "staging" directory.


# Version 4.1 (released 2019-06-17)

- The way how packages are queried has been optimized.
  - `manifest.json` files are now also cached in the `dist_path` folder.
    Using `rbbuild -fF` disables the use of these cache files.
  - if an entry is not pinned (that is, the queried version resolves to  multiple available
    versions), the package in question may resolve to an older version if it was pulled in
    from another dependency. Example:
    ```
        pkg (depends on boost-1.64.1)
        boost
    ```
    boost resolves to 1.64.1 (from pkg) instead of the latest available version.
- Added parameter `--no-traverse` that returns flat dependency list (i.e., the contents of
  the deps file(s)) rather than the resolved one. This is useful for rootfs and installer builds.
- yocto-armhf toolchains now add `-funwind-tables` when calling `rbbuild -d`
- Added color terminal support on Windows 10 and higher.
- Ninja is now built on Linux in the rbbuild sources. Upgraded ninja version 1.9.0.
- Added toolchain "android-ndk-r16b" on Linux.
- When extracting ZIP files on Linux, permissions (e.g., exec bit) are preserved.
- Added support for building with Sonar scanner. Section [sonar] added with variables:
  - `host_url` (Sonar server).
  - `project_key`. Default: com.bosch.
  - `build_wrapper_enable` (True|False value to activate). Default: False.
  - `login` (sonar credentials). Default: None.
- `rbbuild -F` now displays the download progress in MB for files > 5 MB.


# Version 4.0 (released 2019-04-29)

- If the environment variable `RBB_DISABLE_TEST` is present, pytest and ctest scans
  are disabled (invoked via `rbbuild -T`).
- Implement transient dependency handling. When a component is present in deps,
  `rbbuild -F` and `-I` will now behave differently:
   - All dependencies are recursively collected.
   - If a package dependency name (e.g., boost) is present twice, rbbuild will fail with
     an error if either the versions or the toolchain IDs are not the same.
   - Added `build_only={<scomp>[,<scomp>]*|'*'}` flag to deps. With this flag, packages
     can be excluded from dependency checks. Defaults to dev,licenses,signatures (in rbbuild.conf).
-  Added more Artifactory channels to rbbuild.
-  Refactoring of dependency handling and deps files:
   - Missing entries in deps files will now lead to an error.
   - `source` flag is deprecated and will result in an error. Instead, new channels syntax
     `*-sources:<pkg>` must be used.
   - Artifactory properties for sources are now ignored. Instead, the filename
     (including wildcards) can be selected in deps, e.g., `zlib-1.2*` resolves to `zlib-1.2.11.tar.gz`
   - Support for multiple entries in deps with varying suffixes and components.
   - `suffix=zip` no longer resolves to tar.gz and similar.
   - The deprecated `zip` and `rpm` flags have been removed.
   - Support `*` for version digits, e.g., `pkg-x.x.x-master.x` is equivalent to `pkg-*.*.*-master.*`.
-  `rbbuild --get/--set` changes:
   - `--set artifactory_*` have been replaced by `credentials=` and `default_channel`.
     In particular, `artifactory_credentials=<creds>` has been replaced with
     `credentials=<repo>:<creds>`, where `<repo>` is a short name of the artifactory server
     that is configured in `conf/rbbuild.conf`.
   - `--get` has been removed.
- `deps.<platform>` or `deps.<tcid>` are now parsed even if deps is not present.
- Plain `sources` files in Artifactory are now expected to be organized in Ivy format.
- Add `pkq`, an Artifactory package dependency query tool.
- Downloaded files are no longer organized by toolchain. Instead, files are flatly installed into
  the dist folder.
- `pkq --deps` generates a "frozen" deps file. For example, `pkq pkg-x.x.x-master.x --deps`:
  ```
  example-development:pkg-9.0.331-master.27 build_only=licenses,signatures,dev components=signatures suffixes=sha512
  example-development:pkg-9.0.331-master.27 build_only=licenses,signatures,dev components=licenses,dev,prod suffixes=tar.gz,rpm
  ```
- Add support for multiple depsfiles in one call, e.g: `rbbuild --depsfile=deps1,deps2`
- `rbbuild -c/--clean` is now possible without CMakeLists.txt.
- The deployed package name is no longer derived from the `project()` in `CMakeLists.txt`.
  Instead, the package name is derived from `version_package` entry in `version.properties`,
  otherwise, the local repository path name. This means typically no change, however, the
  `CMakeLists.txt` should contain `project ($ENV{RBB_PACKAGE_NAME})`
- Added `rbbuild --publish=<channel>` to deploy files to Artifactory.
- Set default staging path to staging (same level as CMakeLists.txt and obj).
  Use `rbbuild --set staging=/opt/staging/1.0.0` to revert.
  `rbbuild -cf` will also delete the staging directory.
- Dots in branch names are now substituted by underscores.


# Version 3.1 (released 2019-01-02)

- `rbbuild -F` and `-I` now defaults to select all subcomponents of an entry in deps
  if components are set. Before, the default was "prod" and "dev".
- The CMake function `RBPackageSign` has been added to the `RBPackage` module.
  Hash sums for all files marked with this function will be added to the subcomponent
  signatures.
- For Linux native executable builds, the ld option `-rpath` is set such that the
  library link path is set to `<staging>/usr/lib`.
  This allows  executables to be run on the VM out of `obj` directory without setting
  `LD_LIBRARY_PATH`.
- Add `rbbuild --manifest-only` to omit download / install steps and generate a manifest only.
- Support package string syntax in deps: `pkg-x.x.x-branch.x`. The syntax `pkg::branch` is now
  deprecated and will be removed in v4.0.
- `RPATH` is no longer set when crosscompiling on Linux.
- Fix logic error in version comparison.
- Add `concat_files` tool to append text files. The primary use case of this utilitiy is to
  generate license information files.
- Remove `-Wconversion` warning flag from C/C++ builds to avoid too many false positives that
  were being generated.
- Hard-fail if we hit a endless recursion while unpacking tarfiles.
- Pytest is now run by default on the source directory of every component source directory
  (excluding obj). Errors are not fatal.
- Add support for Ninja on Windows for non-visualstudio toolchains.
- Properly pass all environment variables from console to commands called by rbbuild (e.g., cmake).
- Add `rbbuild -T` command to execute unittests and pytest.
- Parameter `--log-level=[ERROR|WARNING|INFO|DEBUG]` now allows to select the maximum
  log level that is printed out (INFO being default).


# Version 3.0 (released 2018-04-27)

- Add new utility `post_process_rootfs`.
- Upgrade Ninja to version 1.8.2 (Linux x86-64 only)
- Add new toolchain for buildroot 2018.02 with gcc 7.0 and binutils 2.30
- Add `manifest.json`: this files collect package information (with `rbbuild --package`)
  and dependencies (`rbbuild --fetch`). This file is stored in the obj folder and uploaded
  to Artifactory. The package meta information in `dist_path` has been removed.
- Add support for building in different directories with `-C/--directory` (works like make `-C`).
  This directory is passed into manifest.json as namespace.
- Entries in deps are now organized as list instead of a dictionary. This means that
  multiple entries with the same name can exist (e.g., with different subcomponents or versions).
- Bump CMake to 3.11.0.
- CMake is now bundled in Windows as well.
- Add CMake module `Cotire`.
- Branch names are now abbreviated to KEY-NNNN, if they are derived from Bitbucket/Jira tickets.
- `rbbuild --debug --install` now works as expected on Visual Studio.
- Revision number (third version number) is now derived from the build date in days rather than
  the git/svn revision.
- Artifactory properties are no longer employed to derive the version of a component.
  Instead, the Ivy path and version string will be used in combination with the `manifest.json`.


# Version 2.2 (released 2018-03-09)

- Allow to override Artifactory user with `--set artifactory_user`
- Using TGZ and RPM as package formats on Linux by default now.
  With this change, symlinks (shared objects!) are working as expected.
- rbbuild now returns an error code, if the underlying (cmake) call failed.
  This is especially useful for Jenkins jobs.
- Add support for `deps.<PLATFORM>` and `deps.<TCID>` files for dependencies specific
  to the platform or toolchain, respectively.
- If the environment variable `BUILD_REVISION` is defined, git/svn will no longer
  be queried and the value passed in this variable is taken instead.
- `rbbuild-local.conf` was moved from `/opt/buildsystem/conf` to `$HOME/.config`
   (also on Windows). This change is made in a backward-compatible manner, which
   means that existing rbbuild-local.conf files will be read if they exist.
-  `rbbuild --set dist_path=` allows setting a custom distfiles folder.
   This distfiles folder is now passed to CMakeLists.txt as `RBB_DIST_PATH`.
-  Make buildsystem a component just like any other.
   Relocate all Docker-specific files to build infrastructure team SVN repository.
- Add `rbbuild -S <path>` to override the default `CMAKE_STAGING_PREFIX`
  (which defaults to <staging>/<tcid>). Needed for NFS/network boot setup.
-  Add support for specifying the platform via `--platform`.
-  Moved Visual Studio configuration settings in rbbuild.conf from `[win32]` section to
   `[visualstudio]`.
- Add support for `yocto-armhf-2.2` target.
- Store git repository and git hash (HEAD):
  - new char* fields in `rbgetversion.h` (git\_repo and git\_hash)
  - new CMake variables `VERSION_GIT_REPO` and `VERSION_GIT_HASH`
  - git\_repo and git\_hash fields in `build_info.properties` and Artifactory
- Add support for Artifactory profiles:
  - `--set/--get artifactory_profile` allows to switch between different profiles.
  - The current profile is set as default and will be used when the "default" was set.
  - deps files now accept a non-default profile, i.e., `[<profile>:]<package>...`.
  - Jenkinsfile gvciPlugin refactored:
    - gvciPlugin arguments are now deprecated. Instead, use
      toolchain array inside the block.
    - optional parameter `profile` added (with `default` as standard repository).
- refactored `ColorTerm` as singleton instance (term). The methods `info()`, `warning()`,
  and `error()` functions are added that write messages to stderr.
- Changed deps format: `prod` and `dev` flags have been replaced with `components=prod,dev`.
- Sub-components are now derived from the filename instead of being a separate property.
  Thus, the Artifactory properties `@version_*` are only used for searching / matching.
- Artifactory package properties `@production` and `@development` are deprecated and ignored.
- Upgrade to CMake 3.10.2. This update allows to build single subcomponent targets without RPM.
- Replaced `RBPACKAGE_RPM_COMPONENTS` and `RBPACKAGE_ARCHIVE_COMPONENTS`:
  - `RBPACKAGE_COMPONENTS` allows to control whether an install component is packaged.
  - `RBPACKAGE_TARGET_DEPLOY` controls whether the package is deployed to the target.
- Allow `rbbuild -F` or `rbbuild -I` to be used without CMakeLists.txt.
- Upon creation, distpath and all subdirectories will be created with permissions 0777.
- Add `rbbuild --param dist_path=<path>` to set a parameter.
- Add `rbbuild --param disable_fetch_progress=<bool>` (used to improve Jenkins log outputs).
- Add `rbbuild --components <comp1>[,<comp2>...]` to selectively install components.


# Version 2.1 (released 2017-10-19)

-  Add `rbbuild --set staging=<path>` that allows to define a new staging directory.
   Remove unused `install_path` variable from config. The selected staging directory
   is now shown when rbbuild is called.
-  Add `rbbuild --install-deps` that installs binary packages according to a
   specification file (deps) into the staging directory.
-  Improve single target build:
    - `rbbuild <target> -c` will now call `ninja clean` and then build the target instead
      of removing the `obj` folder entirely.
    - `rbbuild -s` is implicitly called when building a specific target
    - `rbbuild -v` will now display build actions and targets
- Use http.client for downloading packages from Artifactory.
- Security: `rbbuild-local.conf` will be created with 00600 mode on Linux.
- Fix and improve bash autocompletion
- If `-t` is used in conjunction with `-c`, only remove the selected toolchain.
  Otherwise, the full object directory (`obj`) is removed.
- On Linux, `$STAGING/usr/include` and `$STAGING/usr/lib` are also considered with
  `find_path` and `find_library`. This is a necessary step for using the target's NFS
  root as staging prefix (dev builds).
-  Add new options to rbbuild to handle and download parameters from Artifactory:
   - Add `-F/--fetch` option that perform the actions in rbfetch
   - Add `-f/--force` option to force download (with `-F`)
   - Add `-I` short option alias for `--install-deps`
   - reorganize code for install-deps
-  Refactor `RBPackage` to support the new packaging scheme.
   - Existing CMakeLists.txt will no longer create packages.
   - deps file now accepts optional flags for specifying which files to download and install:
     zip (default: on), rpm (default: off), dev (default: on), prod (default: on),
     and source (default: off).
   - ZIP archives can have any file name (except file suffix) in Artifactory.
     The information is now extracted from Artifactory properties.
   - The contents of ZIP files are now directly extracted into the staging root.
     Thus, there is no longer a subdirectory within the ZIP file.
   - Source files can be managed with rbbuild. These files are toolchain-independent,
     hence, they will be stored in /opt/buildsystem/distfiles/sources.
-  Replace --set-staging and --set-default by a generic --set option.
   - with 'toolchain=<tcid>' a default toolchain can be set
   - with 'staging=<path>' a staging directory is specified.
   - 'artifactory\_server', 'artifactory\_repo', and 'artifactory\_creds'
     modify Artifactory settings.
   - --get <cfg> returns the value of a specific config item
   - --print-all-conf Prints all available configuration options


# Version 2.0 (released 2017-06-20)

- Re-implement rbbuild in Python 3.5
- Add support for Windows
- rbbuild now has long options for all commands, e.g., --build
- rbbuild now uses internally cmake --build instead of calling the maketool directly
- buildsystem is no longer constrained to be located in /opt/buildsystem.
- Format of rbbuild.conf has changed.
- cmake/toolchains/default is now ignored. Instead, the name of the default toolchain
  is is placed in rbbuild.conf under [<platform>]->default_toolchain.
- rbbuild --set-default <tcid> updates rbbuild-local.conf with a new default toolchain.
- Integrate buildsystem with Jenkins
- Install prefix is set to / instead of /usr. This means that (on Linux), the
  installation paths for binaries and libraries must be updated to usr/bin and usr/lib.


# Version 1.0 (no date)

- First stable release
- Add -Wl,-z,relro to linker flags per default
- Added examples/basic-library
- Add RBPackage CMake function to utilize CPack to select RPM, TGZ, or ZIP
  (defaults to: RPM and ZIP).
- Add license field and update vendor in RPM meta data

