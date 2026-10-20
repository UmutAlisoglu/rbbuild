# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import re

from pathlib import Path
from typing import List, Callable

from rbbuild.core.channel import Channel
from rbbuild.core.toolchain import Toolchain
from rbbuild.librbb.term import term
from rbbuild.package.component import Component
from rbbuild.package.package import Package


class ManifestJSONParser:
    def __init__(
        self,
        channel_factory: Callable[..., Channel],
        toolchain_factory: Callable[..., Toolchain],
    ):
        self.toolchain_factory = toolchain_factory
        self.channel_factory = channel_factory

    # json_version < 4
    def _read_package_legacy_3(
        self,
        pkg: Package,
        manifest_json: dict,
    ):
        # expected: { "package" : { "toolchain" : "<tcid>" ... } }
        jnode = manifest_json['package']

        tcid = jnode.get('toolchain')
        if tcid == 'source':
            pkg.channel = self.channel_factory(name='gvci-sources')
            return

        if tcid:
            pkg.toolchain = self.toolchain_factory(tcid=tcid)

        chname = jnode.get('channel')
        if chname:
            pkg.channel = self.channel_factory(name=chname)

        pkg.components = []
        if 'subcomponents' in jnode:
            build_only_comps = jnode.get('build_only_comps', [])
            for name, suffixes in jnode['subcomponents'].items():
                build_only = name in build_only_comps
                for suffix, data in suffixes.items():
                    component = Component( name       = name,
                                           suffix     = suffix,
                                           filename   = data['filename'],
                                           checksum   = data['sha1sum'],
                                           localpath  = data.get('localpath'),
                                           build_only = build_only )
                    pkg.components.append(component)

        return


    # Legacy manifest.json are structured as follows:
    # {
    #     "version": 1",
    #     "visualstudio-2017": {
    #         "package": ...
    #         "dependencies": ...
    #     }
    # }
    def _read_package_legacy_1(
        self,
        pkg: Package,
        manifest_json: dict,
    ):
        for key in manifest_json:
            if key == 'version':
                continue
            elif key == 'source':
                # Legacy manifest support
                if isinstance(manifest_json['source'], list):
                    tokens = re.split(r'\W', manifest_json['source'][0]['name'], maxsplit=1)
                    if len(tokens) == 1:
                        # Corner-case: boost_1_64_0. We split at the first underscore '_'.
                        tokens = tokens[0].split('_', maxsplit=1)
                else:
                    tokens = [ manifest_json['source']['package']['version_package'],
                               manifest_json['source']['package']['version_string'] ]

                pkg.channel = self.channel_factory(name='gvci-sources')
                pkg.name = tokens[0]
                pkg.version = tokens[1]
                return None

            pkg.toolchain = self.toolchain_factory(tcid=key)

            # We can proceed with parsing the rest of the package normally (more or less)
            return manifest_json[key]


    def _read_package_section(
        self,
        pkg: Package,
        manifest_json: dict,
        json_version: int,
        namespace: str,
    ):
        pkg.namespace = namespace
        pkg.installdir = namespace

        if json_version == 1:
            manifest_json = self._read_package_legacy_1(pkg, manifest_json)
            if not manifest_json:
                # nothing left to parse
                return pkg

        if 'package' not in manifest_json:
            raise SyntaxError('Package section not found')

        jnode            = manifest_json['package']
        pkg.name         = jnode['version_package']
        pkg.version      = jnode['version_string']

        if 'git' in jnode:
            pkg.git_repo = jnode['git']['repo']
            pkg.git_hash = jnode['git']['hash']
            pkg.branch   = jnode['git']['branch']
        else:
            pkg.git_repo = jnode.get('git_repo')
            pkg.git_hash = jnode.get('git_hash')

        # If present, these fields will be read and set in the Package object
        optional_fields = [
            'ancestors',
            'copyright',
            'component_type',
            'cpe',
            'integration_type',
            'licenses',
            'purl',
            'url',
            'supplier',
            'build_url',
        ]
        for item in optional_fields:
            if item not in jnode:
                continue
            value = jnode[item]
            setattr(pkg, item, value)

        if json_version < 4:
            self._read_package_legacy_3(pkg, manifest_json)
            return

        # These fields are handled differently in json_version > 3
        if jnode.get('toolchain'):
            pkg.toolchain = self.toolchain_factory(tcid=jnode['toolchain'])
        if 'channel' in jnode:
            pkg.channel   = self.channel_factory(name=jnode.get('channel'))

        pkg.components = self._parse_components(jnode.get('components', []))


    def _parse_components(self, data: dict) -> List[Component]:
        components = []
        for comp_node in data:
            localfile = Path(comp_node['localpath']) if 'localpath' in comp_node else None
            component = Component(
                name       = comp_node['name'],
                suffix     = comp_node['suffix'],
                filename   = comp_node['filename'],
                checksum   = comp_node.get('checksum') or comp_node.get('sha1sum'),
                localpath  = localfile,
                build_only = comp_node.get('build_only', False),
            )
            components.append(component)

        return components


    def _read_dependencies_section(
        self,
        pkg: Package,
        manifest_json: dict,
        json_version: int,
        namespace: str,
    ):
        pkg.dependencies = {}
        if 'dependencies' in manifest_json:
            jnode_deps = manifest_json['dependencies']

            for pkgstr, child_jnode in jnode_deps.items():
                if pkgstr in pkg.dependencies:
                    term.warning('skipped', f'Duplicate package name in manifest: {pkgstr}')
                    continue

                if not child_jnode:
                    term.warning('skipped', f'Invalid child node for dependency {pkgstr}')
                    continue

                # Expected format: [<namespace>/]<pkg>@<platform>-<toolchain>
                if '/' in pkgstr:
                    ns, _ = pkgstr.rsplit('/', maxsplit=1)
                else:
                    ns = ''

                child_pkg = self.parse(
                    child_jnode,
                    json_version=json_version,
                    namespace=ns,
                )

                pkg.dependencies[repr(child_pkg)] = child_pkg


    def parse(
        self,
        manifest_json: dict,
        json_version: int=None,
        namespace: str='',
    ) -> Package:
        if not json_version:
            if 'json_version' in manifest_json:
                json_version = int(manifest_json['json_version'])
            elif 'version' in manifest_json:
                json_version = int(manifest_json['version'])
            else:
                json_version = 1

        pkg = Package()
        self._read_package_section(pkg, manifest_json, json_version, namespace)
        try:
            self._read_dependencies_section(pkg, manifest_json, json_version, namespace)
        except LookupError as ex:
            term.warning(str(pkg), f'Manifest parse error: {ex!s}')
            return None

        except Exception:
            raise

        pkg.manifest_loaded = True
        return pkg

