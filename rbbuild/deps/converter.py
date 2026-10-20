# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import json

from pathlib import Path


# Convert a deps.json dict to the normalized dependencies config list consumed
# by DepsParser.walk().
#
# deps.json format:
#     {'/namespace': {'deps': [...], 'deps.linux': [...], <section_attrs>}}
#
# Normalized format:
#     [{'deps': [...], 'namespace': 'ns', 'restrict_platform': 'linux', ...}]
#
# Mapping rules:
#   'deps.linux' / 'deps.win32'  ->  restrict_platform
#   other 'deps.<suffix>'        ->  restrict_toolchain
def deps_json_to_config(deps_json: dict) -> list:
    dependencies_config = []
    for sec, section in deps_json.items():
        if not sec.startswith('/'):
            raise SyntaxError(f'parse error: deps.json item not recognized: "{sec}"')

        namespace = sec[1:]  # strip leading '/'

        reserved = {'installdir', 'namespace'} if namespace else set()
        sec_attrs = {}
        for key, value in section.items():
            if key.startswith('deps'):
                continue
            if key in reserved:
                raise SyntaxError(f'parse error: duplicate attribute {key} in section {sec}')
            sec_attrs[key] = value

        for key, pkg_items in section.items():
            if not key.startswith('deps'):
                continue

            entry = dict(sec_attrs)
            entry['deps'] = pkg_items
            if namespace:
                entry['namespace'] = namespace

            if key.startswith('deps.'):
                _, suffix = key.split('.', maxsplit=1)
                if suffix in ('linux', 'win32'):
                    entry['restrict_platform'] = suffix
                else:
                    entry['restrict_toolchain'] = suffix

            dependencies_config.append(entry)

    return dependencies_config


# Read a deps.json file and return its contents as a normalized config list.
def load_deps_json(path: Path) -> list:
    with open(path) as fd:
        return deps_json_to_config(json.load(fd))
