# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import sys

import rbbuild

# Unit tests for rbbuild.data_path().


# ---------------------------------------------------------------------------
# Editable / development install (package_dir outside sys.prefix)
# ---------------------------------------------------------------------------

# When the package is running from a source tree outside sys.prefix (as with
# an editable install), the source tree's share/rbbuild/ is always used, even
# if a share/rbbuild/ happens to exist under sys.prefix.
def test_data_path_editable_prefers_source_tree(tmp_path, monkeypatch):
    src_root = tmp_path / 'src_root'
    venv_root = tmp_path / 'venv'
    (venv_root / 'share' / 'rbbuild').mkdir(parents=True)

    monkeypatch.setattr(rbbuild, '__file__', str(src_root / 'rbbuild' / '__init__.py'))
    monkeypatch.setattr(sys, 'prefix', str(venv_root))

    assert rbbuild.data_path() == src_root / 'share' / 'rbbuild'


# ---------------------------------------------------------------------------
# Real (non-editable) install (package_dir under sys.prefix)
# ---------------------------------------------------------------------------

# When the package is installed under sys.prefix and share/rbbuild/ exists
# there, that installed location is used.
def test_data_path_installed_uses_sys_prefix(tmp_path, monkeypatch):
    venv_root = tmp_path / 'venv'
    package_dir = venv_root / 'Lib' / 'site-packages' / 'rbbuild'
    (venv_root / 'share' / 'rbbuild').mkdir(parents=True)

    monkeypatch.setattr(rbbuild, '__file__', str(package_dir / '__init__.py'))
    monkeypatch.setattr(sys, 'prefix', str(venv_root))

    assert rbbuild.data_path() == venv_root / 'share' / 'rbbuild'


# When the package is installed under sys.prefix but share/rbbuild/ is
# missing there (e.g. a fresh/incomplete install), fall back to the
# directory next to the package.
def test_data_path_installed_missing_falls_back_to_package_dir(tmp_path, monkeypatch):
    venv_root = tmp_path / 'venv'
    package_dir = venv_root / 'Lib' / 'site-packages' / 'rbbuild'
    package_dir.mkdir(parents=True)

    monkeypatch.setattr(rbbuild, '__file__', str(package_dir / '__init__.py'))
    monkeypatch.setattr(sys, 'prefix', str(venv_root))

    assert rbbuild.data_path() == package_dir.parent / 'share' / 'rbbuild'
