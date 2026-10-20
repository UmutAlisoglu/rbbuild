<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# Bash completion

A bash-completion script is provided for **rbbuild**, **pkq**, **rbbconf**,
**promote** and **rbfoss**. It completes all command line options as well as
the values of many options:

| Completed value                                          | Options (tools)                                          |
|----------------------------------------------------------|----------------------------------------------------------|
| Profiles                                                 | `-P`, `--profile` (all tools)                            |
| Toolchains of the selected profile and platform          | `-t`, `--toolchain` (rbbuild, pkq, rbbconf, promote)     |
| Channels of the selected profile                         | `-C`, `--channel` (rbbuild, pkq), `-m` (promote)         |
| Platforms (`linux`, `win32`)                             | `--platform`                                             |
| Log levels                                               | `--log-level`                                            |
| Config keys                                              | `-g`, `-s` (rbbconf)                                     |
| `profiles`, `channels`, `services`, `toolchains`, `all`  | `-l` (rbbconf)                                           |
| Fixed choices                                            | `--generate-files` (rbbuild), `--diff-mode`, `--filter-changes` (pkq), `--format` (rbbconf), `--report-type` (rbfoss) |
| File and directory names                                 | e.g., `--depsfile`, `--source-path` (rbbuild), `--out` (pkq), `--map-file` (promote), `--outfile` (rbbconf) |

Profiles, toolchains, channels and config keys are looked up by calling
`rbbconf`. If a profile is already selected with `-P` on the command line,
the lookup is done for this profile. Since each lookup starts a Python
process, completion of these values may take a moment.

For example:

```
rbbuild -P <tab><tab>              # list profiles
rbbuild -P buildcore -t <tab><tab> # list toolchains of profile buildcore
pkq --diff-mode <tab><tab>         # basic commits Jira git
rbbconf -g settings.<tab><tab>     # list config keys of section settings
```


## Enabling bash-completion

To enable bash-completion for rbbuild CLI tools, execute the following command in a bash shell (4.0 or higher):

```shell
# Enter rbbuild venv
source ~/.cache/rbbuild/bin/activate

# Register rbbuild bash-completion
_RBBUILD_BASH_COMPLETION=$(python -c "from rbbuild import data_path; print(data_path().parent / 'bash-completion/completions/rbbuild')")
if [ -f "$_RBBUILD_BASH_COMPLETION" ]; then
    echo "Enabling rbbuild bash completion: $_RBBUILD_BASH_COMPLETION"
    source $_RBBUILD_BASH_COMPLETION
fi
```

The snippet above can be placed in your personal `~/.bashrc` to automatically
enable rbbuild bash-completion.


## Limitations

* Package names (**pkq**, **promote**) are not completed.
* Combined short options such as `-sbp` and options with an attached value
  such as `-j4` are not completed.
