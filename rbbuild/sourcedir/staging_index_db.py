#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import json

from pathlib import Path

from rbbuild.core.paths import Paths
from rbbuild.package.manifest import Manifest


class StagingIndexDB:
    def __init__(
        self,
        paths: Paths,
        manifest: Manifest,
    ):
        self.index_db_file: Path = paths.staging_root / 'staging-indexdb.json'
        self.data: dict = None
        self.manifest = manifest


    def load(self):
        self.data = {}
        if self.index_db_file.is_file():
            with open(self.index_db_file, 'r') as fd:
                manifest_data = json.load(fd)
                for pkgid, item in manifest_data.items():
                    pkg = self.manifest.manifest_parser.parse(
                        item,
                        json_version=self.manifest.json_version,
                    )
                    if pkg:
                        self.data[pkgid] = pkg


    def store(self):
        manifest_data = {}
        for pkgid, pkg in self.data.items():
            # Staging index entries are package snapshots, not top-level
            # manifest documents. Avoid top-level metadata fields.
            manifest_data[pkgid] = self.manifest.from_package(pkg, top_level=False)
            # Remove not needed top-level entries
            del_items = ['dependencies', 'tools']
            for item in del_items:
                manifest_data[pkgid].pop(item, None)

        if not manifest_data:
            return

        self.index_db_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_db_file, 'w') as fd:
            json.dump(manifest_data, fd, indent=4)

