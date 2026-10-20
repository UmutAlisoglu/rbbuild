<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

The promotion of artifacts from one binary repository into another is
often a crucial part of the software development lifecycle. For instance,
packages are copied from a *development* channel to *testing* when certain
quality criteria are met and the software can go into the next test phase.
Afterwards, if all quality criteria of the testing gate are met, the package
will eventually get copied from *testing* channel to *release*.

This is where the *promote* tool comes into play. This CLI tool copies
(or promotes) packages from one rbbuild channel into another.
In the following sections, the different use cases of *promote* are described.


# Usage

```
promote [-h] [-m CHANNEL_MAP] [-M MAP_FILE] [-t TCID] [-n] [-f]
        [-P PROFILE] [-g PACKAGE_LIST_FILE] [-i INPUT_LIST_FILE]
        [--range RANGE] [-A] [--retries RETRIES] [--no-traverse]
        [--platform PLATFORM] [--ignore-errors]
        [--log-level LOG_LEVEL] [--offline] [-T]
        [package]
```

| Option | Description |
|---|---|
| `package` | Package to promote. Syntax: `[<channel>:]<pkgname>[-<version>]` |
| `-m`, `--channel-map` | Channel mappings of the form `<in>:<out>[,<in>:<out>...]` |
| `-M`, `--map-file` | Path to a file with channel mappings (JSON or plain text) |
| `-t`, `--toolchain` | Select toolchain by name or ID |
| `-n`, `--dry-run` | Only show operations that would be executed — **no network calls are made** |
| `-f`, `--force` | Force action |
| `-P`, `--profile` | Select profile |
| `-g`, `--gather` | Create a package list file (plain text) and exit |
| `-i`, `--input-file` | Use a package list file (generated with `--gather`) as input |
| `--range` | Range for `--input-file` (e.g. `0-100`). Only the specified indices will be promoted |
| `-A`, `--all-packages` | Promote all packages in the source channel |
| `--retries` | Number of retries on failure (default: 0; negative value means infinite retries) |
| `--no-traverse` | Do not traverse the dependency tree — only promote the top-most entries |
| `--platform` | Specify target platform |
| `--ignore-errors` | Ignore dependency errors and continue with the next package |
| `--log-level` | Highest log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. Default: `INFO` |
| `--offline` | Do not connect to a server; work with the download cache only |
| `-T`, `--tag` | Tag the git hash for all promoted components with the version number |


# Copy packages in Artifactory

One of the most frequent use cases is to copy files within the same Artifactory,
but on different channels, i.e., paths or repositories.

Thereby, *promote* behaves as follows:
1. Resolve packages into specific versions for the selected input channel and
   toolchain.
2. Skip if the package and toolchain already exist on the destination channel.
3. Perform a copy of all data files to the target channel.
4. Modify `manifest.json` (`package.url` and `package.channel`) accordingly and
   deploy to the target channel.
5. Recursively repeat steps 2–5 for all dependency packages (unless `--no-traverse`
   is passed).

Example:

```
promote nng_cxx -t native -m sample-development:sample-testing
```

In this example, the latest version of `nng_cxx` will be promoted from
*sample-development* to *sample-testing*. Note that the search of `nng_cxx`
will be performed on the current user's profile settings and default channels.

Unless `--no-traverse` is passed, *promote* will also recurse into the
dependencies. Packages not found in `sample-development` will be skipped.
For instance, `-m` contains no mapping for `sample-sources`, so potential
source will be skipped in this example.


## Dry run

Pass `-n` / `--dry-run` to preview all operations without making any network
calls to Artifactory:

```
promote -n -m sample-development:sample-testing nng_cxx-1.5.0
```

When a package string includes an explicit channel prefix, only the
corresponding channel mapping is shown. When no channel prefix is given, all
configured channel mappings are displayed. In both cases, no REST requests
are made.


## Advanced channel mappings

With `-m`, promote accepts channel mappings from input to output.
For example, multiple channel mappings can be specified as follows:

```
promote nng_cxx -t native -m sample-development:sample-testing,sample-sources-legacy:sample-sources
```

Alternatively, more complex mappings can be specified in a file by passing
`-M <mapping-file>`. If the mapping file ends with `.json`, its content is
interpreted as a JSON object, e.g.:

```json
{
    "sample-development": "sample-testing",
    "sample-sources": "sample-sources-new"
}
```

Otherwise, the file is treated as a plain text file where each line has the
form `<channel-in>:<channel-out>`.


# Transfer packages to another server

The *promote* behaviour changes if the input channel and output channel point
at different servers:
1. The input package is resolved and locally downloaded with its dependencies,
   unless `--no-traverse` was passed.
2. The package files are deployed to the target location.
3. The original `manifest.json` is uploaded, with `package.url` and
   `package.channel` parameters adjusted.

Because this approach is very generic and flexible, it allows packages to be
transferred from one channel type to another (e.g., from Bitbucket to
Artifactory).


## Advanced package filtering

To transfer all packages from a channel to another server, pass `--all-packages`
(`-A`). Example:

```
promote -A -m sample-development:new-development
```

The promote behavior changes such that:
* The list of all packages is retrieved from the input channel.
* Each package version and toolchain is traversed and promoted.

The combination with individual packages and `-A` allows promoting all
toolchains for individual packages, e.g.:

```
promote nng_cxx -A -m sample-development:new-development
```


## Promoting from a pre-gathered list

For large channel promotions it can be useful to first collect the full list
of packages and then promote them in batches (e.g. to resume after a failure):

```shell
# Step 1: collect all packages from the source channel
promote -g packages.txt -m sample-development:sample-testing

# Step 2: promote entries 0–99
promote -i packages.txt --range 0-100 -m sample-development:sample-testing

# Step 3: promote entries 100 to end
promote -i packages.txt --range 100- -m sample-development:sample-testing
```

