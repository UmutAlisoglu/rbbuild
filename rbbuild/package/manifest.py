# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import json
import uuid

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from rbbuild.core.toolchain import Toolchain
from rbbuild.package.component import Component
from rbbuild.package.package import Package
from rbbuild.package.parser import ManifestJSONParser


class Manifest:
    def __init__(self, manifest_parser: ManifestJSONParser):
        self.json_version     = 5
        self.document_license = 'CC0-1.0'  # https://creativecommons.org/public-domain/cc0/
        self.manifest_parser  = manifest_parser


    # Plain:           mypkg-1.2.3.4-manifest.json
    # With toolchain:  mypkg-1.2.3.4-linux-native-manifest.json
    # legacy:          mypkg-1.2.3-master.4-native-manifest.json
    def make_filename(
        self,
        name: str,
        version: str,
        toolchain: Toolchain,
        legacy: bool=False,
    ) -> str:
        tcstr = ''
        if toolchain:
            tcstr = f'-{toolchain.name}' if legacy is True else f'-{toolchain!s}'

        return f'{name}-{version}{tcstr}-manifest.json'


    def from_package(self, pkg: Package, top_level=True) -> dict:
        manifest = {}

        #
        # top-level section
        #

        # These fields are only present on top-level manifest.json files
        if top_level:
            manifest = {
                'json_version':          self.json_version,
                'timestamp':             datetime.now(timezone.utc).isoformat(),  # ISO 8601
                'serial_number':         uuid.uuid4().urn,                        # RFC4122
                'document_license':      self.document_license,
            }

        #
        # package section
        #

        manifest['package'] = {
            'version_package': pkg.name,
            'version_string': pkg.version,
            'components': {},
        }

        if pkg.toolchain:
            manifest['package']['toolchain'] = str(pkg.toolchain)

        if pkg.channel:
            manifest['package']['channel']   = pkg.channel.name
            manifest['package']['url']       = pkg.url

        if pkg.git_repo or pkg.git_hash:
            manifest['package']['git'] = {
                'repo':   pkg.git_repo,
                'hash':   pkg.git_hash,
                'branch': pkg.branch,
            }

        if pkg.build_url:
            manifest['package']['build_url'] = pkg.build_url

        if pkg.purl:
            manifest['package']['purl'] = str(pkg.purl)

        if pkg.component_type:
            manifest['package']['component_type'] = str(pkg.component_type)

        if pkg.licenses:
            manifest['package']['licenses'] = [p.to_dict() for p in pkg.licenses]

        if pkg.copyright:
            manifest['package']['copyright'] = pkg.copyright

        if pkg.ancestors:
            manifest['package']['ancestors'] = pkg.ancestors

        if pkg.cpe:
            manifest['package']['cpe'] = pkg.cpe

        if pkg.integration_type:
            manifest['package']['integration_type'] = str(pkg.integration_type)

        if pkg.supplier:
            manifest['package']['supplier'] = asdict(pkg.supplier)

        # components
        if pkg.components:
            components = []
            for component in pkg.components:
                comp = {
                    'name':     component.name,
                    'suffix':   component.suffix,
                    'filename': component.filename,
                }
                # Only set these fields if they are defined
                for field in ['checksum', 'build_only']:
                    attr = getattr(component, field)
                    if attr:
                        comp[field] = attr

                components.append(comp)

            manifest['package']['components'] = components

        #
        # dependencies sections
        #

        if pkg.dependencies:
            manifest['dependencies'] = {}
            for pkgstr, child_pkg in pkg.dependencies.items():
                manifest['dependencies'][pkgstr] = self.from_package(child_pkg, top_level=False)

        #
        # Tools section
        #
        if pkg.tools:
            manifest['tools'] = []
            for tool in pkg.tools:
                mtool = {
                    'vendor': tool.vendor,
                    'name': tool.name,
                    'version': tool.version,
                }
                if tool.external_references:
                    mtool['external_references'] = []
                    for ext in tool.external_references:
                        mtool['external_references'].append({
                            'type': ext.type,
                            'url': ext.url,
                        })
                manifest['tools'].append(mtool)

        return manifest


    def load(
        self,
        manifest_path: Path,
    ):
        with open(manifest_path, 'r') as jfd:
            manifest = json.load(jfd)
            pkg = self.manifest_parser.parse(manifest)

        if not pkg:
            return

        pkg.manifest = Component(
            name = 'manifest',
            suffix = 'json',
            filename = manifest_path.name,
            localpath = manifest_path,
        )

        return pkg

