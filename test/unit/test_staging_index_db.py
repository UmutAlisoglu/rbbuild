# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import json

from unittest.mock import MagicMock

from rbbuild.sourcedir.staging_index_db import StagingIndexDB


def _make_index_db(tmp_path):
    paths = MagicMock()
    paths.staging_root = tmp_path / 'staging'
    manifest = MagicMock()
    return StagingIndexDB(paths=paths, manifest=manifest), manifest


def test_store_skips_write_when_manifest_data_is_empty(tmp_path):
    index_db, _ = _make_index_db(tmp_path)
    index_db.data = {}

    index_db.store()

    assert not index_db.index_db_file.exists()


def test_store_writes_file_when_manifest_data_exists(tmp_path):
    index_db, manifest = _make_index_db(tmp_path)

    pkg = MagicMock()
    manifest.from_package.return_value = {
        'package': {
            'name': 'example',
            'version': '1.0.0',
        },
        'dependencies': {'x': {'y': 1}},
        'tools': {'a': {'b': 2}},
    }

    index_db.data = {'example-1.0.0': pkg}
    index_db.store()

    assert index_db.index_db_file.exists()
    manifest.from_package.assert_called_once_with(pkg, top_level=False)

    stored = json.loads(index_db.index_db_file.read_text())
    assert 'example-1.0.0' in stored
    assert 'dependencies' not in stored['example-1.0.0']
    assert 'tools' not in stored['example-1.0.0']
