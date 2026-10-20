# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dataclasses import dataclass
from typing import Dict

from rbbuild.core.channel import Channel
from rbbuild.core.runtime_settings import RuntimeSettings
from rbbuild.core.toolchain import Toolchain
from rbbuild.deps.converter import deps_json_to_config
from rbbuild.deps.parser import DepsParser
from rbbuild.package.package import Package
from rbbuild.librbb.term import term


@dataclass
class Freezer:
    settings: RuntimeSettings
    toolchains: Dict[str, Toolchain]
    channels: Dict[str, Channel]


    def _patch_entry(self, line: str, arg0: str, pkg: Package) -> str:
        if ':' in arg0:
            _, pkgstr = arg0.split(':', maxsplit=1)
        else:
            pkgstr = arg0

        return line.replace(pkgstr, str(pkg), 1)


    def freeze(self, deps_json_in: dict, packages: Dict[str, Dict[str, Package]]):
        deps_parser = DepsParser(self.settings, self.toolchains, self.channels)
        deps_json = {}

        modified = False
        for pkg_items, attrs in deps_parser.walk(deps_json_to_config(deps_json_in)):
            namespace = attrs.get('namespace', '')
            term.info(term.bright_white(namespace))

            deps_json[f'/{namespace}'] = {}
            entries_new = []
            for item in pkg_items:
                arg0, _ = deps_parser.parse_attrs(item, None)
                entry = deps_parser.parse_item(item)

                if not entry.version:
                    pkg = packages[''][repr(entry)]
                    entry = self._patch_entry(item, arg0, pkg)
                    term.info('[%s] %s \u2192 %s' % (term.green('\u21c4'), arg0, entry.split()[0]))
                    modified = True

                entries_new.append(entry)

            deps_json[f'/{namespace}'].update(attrs)
            deps_json[f'/{namespace}']['deps'] = entries_new

        return deps_json if modified else deps_json_in

