# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from typing import Dict

from rbbuild.deps.parser import DepsParser
from rbbuild.resolver.resolver import Resolver
from rbbuild.package.package import Package


class DepsFile:
    def __init__(
        self,
        deps_parser: DepsParser,
        resolver: Resolver,
    ):
        self.resolver = resolver
        self.deps_parser = deps_parser


    def from_string(self, deps_line: str) -> Dict[str, Dict[str, Package]]:
        return self.from_config([{'deps': deps_line.split(',')}])


    def from_config(self, dependencies_config: list) -> Dict[str, Dict[str, Package]]:
        dependencies = {}

        for pkg_items, sec_attrs in self.deps_parser.walk(dependencies_config):
            namespace = sec_attrs.get('namespace', '')
            entries = {}
            for item in pkg_items:
                pkg = self.deps_parser.parse_item(item, sec_attrs)
                if not pkg:
                    continue
                pkgid = repr(pkg)
                if pkgid in entries:
                    entries[pkgid].merge(pkg)
                else:
                    entries[pkgid] = pkg

            if namespace not in dependencies:
                dependencies[namespace] = {}
            dependencies[namespace].update(entries)

        return dependencies


