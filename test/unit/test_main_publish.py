# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock

import pytest

from rbbuild.__main__ import RBBuildMain
from rbbuild.package.package import Package
from rbbuild.service.repository.repository import VersionConflictError

# Unit tests for RBBuildMain.publish() version-conflict retry loop.
# build_tools()/package() are stubbed on the instance so only the
# orchestration logic in publish() itself is under test.


def _make_paths(tmp_path):
    (tmp_path / 'manifest.json').write_text('{}')
    paths = MagicMock()
    paths.build = tmp_path
    return paths


def _make_manifest(pkg):
    manifest = MagicMock()
    manifest.manifest_parser.parse.return_value = pkg
    manifest.make_filename.return_value = f'{pkg.name}-{pkg.version}-manifest.json'
    return manifest


def _make_channel_factory(permissions='upload'):
    channel = MagicMock()
    channel.permissions = permissions
    return lambda name: channel


def _make_rbbuild_main(pkg, pkgman, tmp_path, permissions='upload'):
    rbbuild_main = RBBuildMain()
    rbbuild_main.build_tools = lambda: [pkgman]
    rbbuild_main.package = MagicMock()

    def _call(chname='development'):
        return rbbuild_main.publish(
            chname,
            paths=_make_paths(tmp_path),
            manifest=_make_manifest(pkg),
            channel_factory=_make_channel_factory(permissions),
        )

    return rbbuild_main, _call


# No conflict: publish succeeds on the first attempt, no repackage happens.
def test_publish_succeeds_without_conflict(tmp_path):
    pkg = Package(name='mypkg', version='1.2.3.4')
    pkg.toolchain = None
    pkg.components = []

    pkgman = MagicMock()
    rbbuild_main, call = _make_rbbuild_main(pkg, pkgman, tmp_path)

    call()

    pkgman.publish.assert_called_once()
    rbbuild_main.package.assert_not_called()
    assert pkg.version == '1.2.3.4'


# A single conflict appends a 5th version digit, repackages once, and
# succeeds on retry.
def test_publish_retries_once_on_single_conflict(tmp_path):
    pkg = Package(name='mypkg', version='1.2.3.4')
    pkg.toolchain = None
    pkg.components = []

    pkgman = MagicMock()
    pkgman.publish.side_effect = [VersionConflictError('already published'), None]
    rbbuild_main, call = _make_rbbuild_main(pkg, pkgman, tmp_path)

    call()

    assert pkgman.publish.call_count == 2
    rbbuild_main.package.assert_called_once()
    assert pkg.version == '1.2.3.4.1'


# A pre-existing 5th digit is incremented (not reset) on each conflict, and
# repackage is called once per conflict encountered.
def test_publish_increments_existing_fifth_digit_on_repeated_conflicts(tmp_path):
    pkg = Package(name='mypkg', version='1.2.3.4')
    pkg.toolchain = None
    pkg.components = []

    pkgman = MagicMock()
    pkgman.publish.side_effect = [
        VersionConflictError('already published'),
        VersionConflictError('already published'),
        None,
    ]
    rbbuild_main, call = _make_rbbuild_main(pkg, pkgman, tmp_path)

    call()

    assert pkgman.publish.call_count == 3
    assert rbbuild_main.package.call_count == 2
    assert pkg.version == '1.2.3.4.2'


# A non-conflict error must propagate immediately without repackaging.
def test_publish_propagates_non_conflict_errors(tmp_path):
    pkg = Package(name='mypkg', version='1.2.3.4')
    pkg.toolchain = None
    pkg.components = []

    pkgman = MagicMock()
    pkgman.publish.side_effect = RuntimeError('network down')
    rbbuild_main, call = _make_rbbuild_main(pkg, pkgman, tmp_path)

    with pytest.raises(RuntimeError, match='network down'):
        call()

    pkgman.publish.assert_called_once()
    rbbuild_main.package.assert_not_called()


# publish() must reject channels without at least upload permission before
# ever attempting to publish (unchanged pre-existing behavior).
def test_publish_rejects_insufficient_permissions(tmp_path):
    pkg = Package(name='mypkg', version='1.2.3.4')
    pkg.toolchain = None
    pkg.components = []

    pkgman = MagicMock()
    rbbuild_main, call = _make_rbbuild_main(pkg, pkgman, tmp_path, permissions='read')

    with pytest.raises(PermissionError):
        call()

    pkgman.publish.assert_not_called()
