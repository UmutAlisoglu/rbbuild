# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from pathlib import Path
from unittest.mock import MagicMock, patch

from rbbuild.package.component import Component
from rbbuild.package.package import Package
from rbbuild.sourcedir.staging_folder import StagingFolder


def _make_component(name, suffix='tar.gz'):
    c = Component(name=name, suffix=suffix)
    c.filename = f'{name}.{suffix}'
    c.localpath = Path(f'/dist/{name}.{suffix}')
    return c


def _make_pkg(name, version, components):
    pkg = Package(name=name, version=version)
    pkg.components = components
    return pkg


def _make_staging_folder(index_db_data):
    repoman = MagicMock()
    index_db = MagicMock()
    index_db.data = index_db_data
    paths = MagicMock()
    staging = StagingFolder(
        toolchain=MagicMock(),
        index_db=index_db,
        paths=paths,
        repoman=repoman,
    )
    return staging, repoman, index_db


def test_install_package_fresh_install(tmp_path):
    comp_a = _make_component('libfoo')
    comp_b = _make_component('libfoo-headers')
    pkg = _make_pkg('libfoo', '1.0.0', [comp_a, comp_b])

    staging, repoman, index_db = _make_staging_folder({})
    repoman.download.return_value = [comp_a, comp_b]

    with patch.object(staging, 'install_component') as mock_install, \
         patch.object(staging, 'uninstall_component') as mock_uninstall:
        staging.install_package(pkg, tmp_path, skipped_components=[])

    mock_uninstall.assert_not_called()
    assert mock_install.call_count == 2
    assert index_db.data[repr(pkg)] is pkg


def test_install_package_same_version_same_components_is_noop(tmp_path):
    comp_a = _make_component('libfoo')
    pkg = _make_pkg('libfoo', '1.0.0', [comp_a])
    installed_pkg = _make_pkg('libfoo', '1.0.0', [comp_a])

    staging, repoman, index_db = _make_staging_folder({repr(pkg): installed_pkg})
    repoman.download.return_value = [comp_a]

    with patch.object(staging, 'install_component') as mock_install, \
         patch.object(staging, 'uninstall_component') as mock_uninstall:
        staging.install_package(pkg, tmp_path, skipped_components=[])

    mock_uninstall.assert_not_called()
    mock_install.assert_not_called()
    assert index_db.data[repr(pkg)] is pkg


def test_install_package_same_version_component_removed(tmp_path):
    comp_a = _make_component('libfoo')
    comp_b = _make_component('libfoo-headers')
    pkg = _make_pkg('libfoo', '1.0.0', [comp_a])
    installed_pkg = _make_pkg('libfoo', '1.0.0', [comp_a, comp_b])

    staging, repoman, index_db = _make_staging_folder({repr(pkg): installed_pkg})

    def download_side_effect(p):
        return [comp_a, comp_b] if p is installed_pkg else [comp_a]

    repoman.download.side_effect = download_side_effect

    with patch.object(staging, 'install_component') as mock_install, \
         patch.object(staging, 'uninstall_component') as mock_uninstall:
        staging.install_package(pkg, tmp_path, skipped_components=[])

    # comp_b should be uninstalled; comp_a should be left untouched
    mock_uninstall.assert_called_once()
    assert mock_uninstall.call_args[0][1] is comp_b
    mock_install.assert_not_called()


def test_install_package_same_version_component_added(tmp_path):
    comp_a = _make_component('libfoo')
    comp_b = _make_component('libfoo-extra')
    pkg = _make_pkg('libfoo', '1.0.0', [comp_a, comp_b])
    installed_pkg = _make_pkg('libfoo', '1.0.0', [comp_a])

    staging, repoman, index_db = _make_staging_folder({repr(pkg): installed_pkg})

    def download_side_effect(p):
        return [comp_a] if p is installed_pkg else [comp_a, comp_b]

    repoman.download.side_effect = download_side_effect

    with patch.object(staging, 'install_component') as mock_install, \
         patch.object(staging, 'uninstall_component') as mock_uninstall:
        staging.install_package(pkg, tmp_path, skipped_components=[])

    # comp_a already installed; only comp_b should be installed
    mock_uninstall.assert_not_called()
    mock_install.assert_called_once()
    assert mock_install.call_args[0][1] is comp_b


def test_install_package_version_updated_full_reinstall(tmp_path):
    old_comp = _make_component('libfoo')
    new_comp = _make_component('libfoo')
    old_pkg = _make_pkg('libfoo', '1.0.0', [old_comp])
    new_pkg = _make_pkg('libfoo', '2.0.0', [new_comp])

    staging, repoman, index_db = _make_staging_folder({repr(new_pkg): old_pkg})

    def download_side_effect(p):
        return [old_comp] if p is old_pkg else [new_comp]

    repoman.download.side_effect = download_side_effect

    with patch.object(staging, 'install_component') as mock_install, \
         patch.object(staging, 'uninstall_component') as mock_uninstall:
        staging.install_package(new_pkg, tmp_path, skipped_components=[])

    mock_uninstall.assert_called_once()
    assert mock_uninstall.call_args[0][1] is old_comp
    mock_install.assert_called_once()
    assert mock_install.call_args[0][1] is new_comp
    assert index_db.data[repr(new_pkg)] is new_pkg


def test_install_package_skipped_component_not_installed(tmp_path):
    comp_a = _make_component('libfoo')
    comp_b = _make_component('libfoo-debug')
    pkg = _make_pkg('libfoo', '1.0.0', [comp_a, comp_b])

    staging, repoman, index_db = _make_staging_folder({})
    repoman.download.return_value = [comp_a, comp_b]

    with patch.object(staging, 'install_component') as mock_install, \
         patch.object(staging, 'uninstall_component') as mock_uninstall:
        staging.install_package(pkg, tmp_path, skipped_components=['libfoo-debug'])

    mock_uninstall.assert_not_called()
    mock_install.assert_called_once()
    assert mock_install.call_args[0][1] is comp_a


def test_install_package_build_only_component_installed_by_default(tmp_path):
    comp_a = _make_component('libfoo')
    comp_b = _make_component('libfoo-dev')
    comp_b.build_only = True
    pkg = _make_pkg('libfoo', '1.0.0', [comp_a, comp_b])

    staging, repoman, index_db = _make_staging_folder({})
    repoman.download.return_value = [comp_a, comp_b]

    with patch.object(staging, 'install_component') as mock_install:
        staging.install_package(pkg, tmp_path, skipped_components=[])

    assert mock_install.call_count == 2


def test_install_package_build_only_component_skipped_for_nested(tmp_path):
    comp_a = _make_component('libfoo')
    comp_b = _make_component('libfoo-dev')
    comp_b.build_only = True
    pkg = _make_pkg('libfoo', '1.0.0', [comp_a, comp_b])

    staging, repoman, index_db = _make_staging_folder({})
    repoman.download.return_value = [comp_a, comp_b]

    with patch.object(staging, 'install_component') as mock_install:
        staging.install_package(
            pkg, tmp_path, skipped_components=[], install_build_only=False)

    mock_install.assert_called_once()
    assert mock_install.call_args[0][1] is comp_a


def test_remove_keeps_other_toolchains_and_updates_index(tmp_path):
    (tmp_path / 'tc-a').mkdir()
    (tmp_path / 'tc-b').mkdir()
    (tmp_path / 'staging-indexdb.json').write_text('{}')
    pkg_a = _make_pkg('liba', '1.0.0', [])
    pkg_a.toolchain = 'tc-a'
    pkg_b = _make_pkg('libb', '1.0.0', [])
    pkg_b.toolchain = 'tc-b'

    staging, _, index_db = _make_staging_folder(
        {repr(pkg_a): pkg_a, repr(pkg_b): pkg_b})
    staging.toolchain = 'tc-a'
    staging.paths.staging_root = tmp_path
    staging.paths.staging = tmp_path / 'tc-a'

    staging.remove()

    assert not (tmp_path / 'tc-a').exists()
    assert (tmp_path / 'tc-b').exists()
    assert list(index_db.data) == [repr(pkg_b)]
    index_db.store.assert_called_once()
