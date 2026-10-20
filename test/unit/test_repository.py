# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from pathlib import Path
from unittest.mock import MagicMock, patch

from rbbuild.package.component import Component
from rbbuild.package.package import Package
from rbbuild.service.repository.repository import Repository


# ---------------------------------------------------------------------------
# Repository.list_versions — integration of caching + sort
# ---------------------------------------------------------------------------

def _make_repo(remote_versions, cached_versions=None):
    """Build a minimal concrete Repository backed by mocks."""
    if cached_versions is None:
        cached_versions = []

    cache = MagicMock()
    cache.get_versions.return_value = list(cached_versions)

    repo = MagicMock(spec=Repository)
    repo.cache = cache
    repo.get_versions.return_value = list(remote_versions)
    # Bind the real list_versions method to our mock instance
    repo.list_versions = Repository.list_versions.__get__(repo, Repository)
    return repo


# When a specific version is requested, it is returned as-is without sorting
def test_list_versions_pinned():
    repo = _make_repo(remote_versions=['1.0.0', '2.0.0'])
    result = repo.list_versions('mypkg', '1.0.0')
    assert result == ['1.0.0']


# Versions from remote are returned newest-first
def test_list_versions_sorted_newest_first():
    repo = _make_repo(remote_versions=['1.2.3-master.4', '1.2.3-master.5', '1.0.0-master.6'])
    result = repo.list_versions('mypkg', None)
    assert result == ['1.2.3-master.5', '1.2.3-master.4', '1.0.0-master.6']


# Cached versions no longer on remote are evicted
def test_list_versions_evicts_deleted():
    repo = _make_repo(
        remote_versions=['2.0.0'],
        cached_versions=['1.0.0', '2.0.0'],
    )
    result = repo.list_versions('mypkg', None)
    repo.cache.delete.assert_called_once_with('mypkg', '1.0.0')
    assert result == ['2.0.0']


# ---------------------------------------------------------------------------
# Repository.find_components — component_name is passed to get_component
# ---------------------------------------------------------------------------

def _make_component(name: str, filename: str) -> Component:
    """Return a minimal Component with the given name and filename."""
    return Component(name=name, suffix=None, filename=filename)


def _make_repo_for_find_components(cache_hit=False, downloaded_path=None):
    """
    Build a minimal concrete Repository backed by mocks for find_components
    testing.  cache.get_component returns a mock Path that reports .exists()
    according to *cache_hit*.  get_component returns *downloaded_path*.
    """
    cache = MagicMock()
    cache_path = MagicMock(spec=Path)
    cache_path.exists.return_value = cache_hit
    cache.get_component.return_value = cache_path

    repo = MagicMock(spec=Repository)
    repo.cache = cache
    repo.get_component.return_value = downloaded_path
    repo.find_components = Repository.find_components.__get__(repo, Repository)
    return repo, cache_path


# cache hit: get_component on the repo is never called; component_name is
# forwarded to cache.get_component as the third positional argument
def test_find_components_cache_hit_passes_component_name():
    comp = _make_component(name='mylib', filename='mylib-1.0.tar.gz')
    pkg = MagicMock(spec=Package)
    pkg.name = 'mypkg'
    pkg.version = '1.0.0'
    pkg.components = [comp]

    repo, cache_path = _make_repo_for_find_components(cache_hit=True)
    cache_path.exists.return_value = True
    cache_path.__truediv__ = MagicMock(return_value=cache_path)

    with patch('rbbuild.service.repository.repository.compute_sha1sum', return_value='abc123'):
        results = list(repo.find_components(pkg))

    repo.cache.get_component.assert_called_once_with(
        pkg, comp,
    )
    # repo.get_component must NOT have been called on a cache hit
    repo.get_component.assert_not_called()
    assert len(results) == 1
    assert results[0].name == 'mylib'


# cache miss: get_component on the repo IS called with component_name as the
# third positional argument, followed by filename
def test_find_components_cache_miss_passes_component_name():
    comp = _make_component(name='mylib', filename='mylib-1.0.tar.gz')
    pkg = MagicMock(spec=Package)
    pkg.name = 'mypkg'
    pkg.version = '1.0.0'
    pkg.components = [comp]

    downloaded = MagicMock(spec=Path)
    downloaded.name = 'mylib-1.0.tar.gz'
    repo, cache_path = _make_repo_for_find_components(
        cache_hit=False, downloaded_path=downloaded
    )

    with patch('rbbuild.service.repository.repository.compute_sha1sum', return_value='abc123'):
        with patch('shutil.move'):
            results = list(repo.find_components(pkg))

    assert len(results) == 1

    repo.get_component.assert_called_once_with(
        pkg, comp,
    )


# when get_component returns None (file not available) the component is skipped
def test_find_components_skips_unavailable_component():
    comp = _make_component(name='optional', filename='optional-1.0.tar.gz')
    pkg = MagicMock(spec=Package)
    pkg.name = 'mypkg'
    pkg.version = '1.0.0'
    pkg.components = [comp]

    repo, _ = _make_repo_for_find_components(cache_hit=False, downloaded_path=None)

    results = list(repo.find_components(pkg))
    assert results == []

