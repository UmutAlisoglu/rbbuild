# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import argparse
import pytest

from unittest.mock import patch, PropertyMock

from rbbuild.package.package import Package
from rbbuild.service.repository.manager import RepositoryManager
from rbbuild.ui.pkq.control import PkqController
from rbbuild.ui.pkq.history import PkqHistory


def _args(**overrides):
    defaults = dict(verbose=False, package=None)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# No-op report_progress callback - these tests don't exercise progressive
# rendering, just the final result, but PkqController.query() requires a
# callback to be passed (see rbbuild.ui.async_task.AsyncTaskQueue).
def _no_progress(payload):
    pass


@pytest.fixture()
def controller(app_test):
    return PkqController(app_test, _args())


# --- history ---

def test_history_is_pkq_history_instance(controller):
    assert isinstance(controller.history, PkqHistory)


# --- profile ---

def test_profiles_lists_available(controller):
    profiles = controller.profiles
    assert isinstance(profiles, list)
    assert 'test' in profiles


def test_profile_reflects_currently_loaded_profile(controller):
    assert controller.profile == 'test'


# --- toolchain / platform switching ---

def test_toolchains_lists_available(controller):
    toolchains = controller.toolchains
    assert isinstance(toolchains, list)
    assert len(toolchains) > 0


def test_toolchains_includes_default_entry_first(controller):
    assert controller.toolchains[0] == controller.DEFAULT_TOOLCHAIN


def test_toolchain_reflects_current_selection(controller):
    assert str(controller.toolchain) in controller.toolchains


def test_select_platform_toolchain_overrides_config(controller):
    tcid = controller.toolchains[1]
    controller.select_platform_toolchain(tcid)
    assert str(controller.toolchain) == tcid


# Regression test: dependency_injector's ConfigurationOption has no
# reset_override(), so once the toolchain dropdown is changed away from the
# platform's default, there was previously no way back within the same
# session - selecting the virtual DEFAULT_TOOLCHAIN entry must restore it.
def test_select_default_toolchain_restores_original_default(controller):
    original = str(controller.toolchain)
    other_tcid = next(tc for tc in controller.toolchains[1:] if tc != original)

    controller.select_platform_toolchain(other_tcid)
    assert str(controller.toolchain) == other_tcid

    controller.select_platform_toolchain(controller.DEFAULT_TOOLCHAIN)
    assert str(controller.toolchain) == original


# --- query() — normal tree ---

def test_query_resolves_tree(controller):
    ok = controller.query(text='libfoo', report_progress=_no_progress)
    assert ok is True
    assert not controller.diff_mode
    assert len(controller.entries) > 0

    root_pkg, root_depth = controller.entries[0]
    assert root_depth == 0
    assert root_pkg.name == 'libfoo'


def test_query_not_found_returns_false(controller):
    ok = controller.query(text='this_package_does_not_exist_anywhere', report_progress=_no_progress)
    assert ok is False
    assert controller.entries == []


# --- query() — diff mode (pkgA..verB) ---

def test_query_diff_mode(controller):
    ok = controller.query(text='libfoo-1.0.0.1..2.0.0.3', report_progress=_no_progress)
    assert ok is True
    assert controller.diff_mode is True
    assert len(controller.cmp_entries) > 0


def test_query_diff_mode_not_found_returns_false(controller):
    ok = controller.query(text='libfoo-1.0.0.1..9.9.9999.99', report_progress=_no_progress)
    assert ok is False
    assert controller.cmp_entries == []


# --- selection ---

def test_set_package_and_package_property(controller):
    controller.query(text='libfoo', report_progress=_no_progress)
    controller.set_package(0)
    assert controller.package is not None
    assert controller.package.name == 'libfoo'


def test_package_is_none_without_selection(controller):
    controller.query(text='libfoo', report_progress=_no_progress)
    assert controller.package is None


def test_package_prev_is_none_outside_diff_mode(controller):
    controller.query(text='libfoo', report_progress=_no_progress)
    controller.set_package(0)
    assert controller.package_prev is None


def test_package_prev_available_in_diff_mode(controller):
    controller.query(text='libfoo-1.0.0.1..2.0.0.3', report_progress=_no_progress)
    controller.set_package(0)
    assert controller.package_prev is not None
    assert controller.package_prev.version == '1.0.0.1'


# --- conflict diagnostics ---

def test_is_conflicted_false_for_clean_query(controller):
    controller.query(text='libfoo', report_progress=_no_progress)
    for pkg, _ in controller.entries:
        assert controller.is_conflicted(pkg) is False
    assert controller.conflict_message(controller.entries[0][0]) is None


# --- downloads ---

def test_download_package_returns_none_without_selection(controller):
    assert controller.download_package('whatever.tar.xz') is None


# --- channel selection propagates to every query mode ---
#
# RepositoryManager (repoman) is a DI Singleton; its own selected_channel is
# resolved once, at first construction, and never updates afterward. If a
# query method doesn't pass channel= explicitly, RepositoryManager.search()
# silently falls back to that stale default instead of the controller's
# currently selected channel (e.g. after PkqController.select_channel()).

def test_query_versions_passes_current_channel(controller):
    with patch.object(RepositoryManager, 'search_versions', return_value=iter([])) as mock_search:
        controller.query(text='libfoo', report_progress=_no_progress)

    assert mock_search.call_args.kwargs.get('channel').name == controller.channel.name


def test_query_package_passes_current_channel(controller):
    with patch.object(RepositoryManager, 'search', return_value=iter([])) as mock_search:
        controller.query(text='libfoo-1.0.0.1', report_progress=_no_progress)

    assert mock_search.call_args.kwargs.get('channel').name == controller.channel.name


def test_query_changes_passes_current_channel(controller):
    with patch.object(RepositoryManager, 'search', return_value=iter([])) as mock_search:
        controller.query(text='libfoo-1.0.0.1..2.0.0.3', report_progress=_no_progress)

    for call in mock_search.call_args_list:
        assert call.kwargs.get('channel').name == controller.channel.name


# --- toolchain resolution for pinned versions (query()'s pkg parameter/_query_pinned()) ---
#
# search_versions() no longer guesses a toolchain (see RepositoryManager).
# _query_pinned() defaults an unset pkg.toolchain to the currently selected
# one, so a Package is only genuinely ambiguous when no toolchain is
# selected at all (PkqController.toolchain is None) - simulated below by
# patching that property.

def test_query_package_lists_all_toolchain_variants_when_ambiguous(controller):
    variant_a = Package(name='mypkg', version='1.0')
    variant_a.toolchain = 'linux-native'
    variant_b = Package(name='mypkg', version='1.0')
    variant_b.toolchain = 'win32-mingw'

    pkg = Package(name='mypkg', version='1.0')  # toolchain unset - ambiguous

    with patch.object(PkqController, 'toolchain', new_callable=PropertyMock, return_value=None), \
         patch.object(RepositoryManager, 'search_toolchains', return_value=iter([variant_a, variant_b])):
        ok = controller.query(pkg=pkg, report_progress=_no_progress)

    assert ok is True
    assert not controller.diff_mode
    assert len(controller.entries) == 2
    assert {p.toolchain for p, _ in controller.entries} == {'linux-native', 'win32-mingw'}


def test_query_package_resolves_tree_directly_when_single_toolchain(controller):
    variant = Package(name='mypkg', version='1.0')
    variant.toolchain = 'linux-native'

    pkg = Package(name='mypkg', version='1.0')

    with patch.object(PkqController, 'toolchain', new_callable=PropertyMock, return_value=None), \
         patch.object(RepositoryManager, 'search_toolchains', return_value=iter([variant])), \
         patch('rbbuild.resolver.resolver.Resolver.walk_deps_with_count', return_value=iter([])):
        ok = controller.query(pkg=pkg, report_progress=_no_progress)

    assert ok is True
    assert len(controller.entries) == 1
    root_pkg, depth = controller.entries[0]
    assert root_pkg is variant
    assert depth == 0


def test_query_package_not_found_for_any_toolchain_returns_false(controller):
    pkg = Package(name='mypkg', version='1.0')

    with patch.object(PkqController, 'toolchain', new_callable=PropertyMock, return_value=None), \
         patch.object(RepositoryManager, 'search_toolchains', return_value=iter([])):
        ok = controller.query(pkg=pkg, report_progress=_no_progress)

    assert ok is False


def test_query_package_wrong_toolchain_lists_available_toolchains(controller):
    pkg = Package(name='mypkg', version='1.0')
    pkg.toolchain = 'linux-native'

    variant = Package(name='mypkg', version='1.0')
    variant.toolchain = 'win32-mingw'

    with patch.object(RepositoryManager, 'search', return_value=iter([])), \
         patch.object(RepositoryManager, 'search_toolchains', return_value=iter([variant])):
        with pytest.raises(LookupError, match='win32-mingw'):
            controller.query_service.query(
                pkg=pkg,
                channel=controller.channel,
                toolchain=controller.toolchain,
                report_progress=_no_progress,
            )


def test_query_package_wrong_toolchain_no_other_variants(controller):
    pkg = Package(name='mypkg', version='1.0')
    pkg.toolchain = 'linux-native'

    with patch.object(RepositoryManager, 'search', return_value=iter([])), \
         patch.object(RepositoryManager, 'search_toolchains', return_value=iter([])):
        with pytest.raises(LookupError, match=r'^Could not find package mypkg-1\.0'):
            controller.query_service.query(
                pkg=pkg,
                channel=controller.channel,
                toolchain=controller.toolchain,
                report_progress=_no_progress,
            )


def test_query_package_honors_already_known_toolchain(controller):
    pkg = Package(name='mypkg', version='1.0')
    pkg.toolchain = 'linux-native'

    with patch.object(RepositoryManager, 'search_toolchains') as mock_search_toolchains, \
         patch.object(RepositoryManager, 'search', return_value=iter([pkg])), \
         patch('rbbuild.resolver.resolver.Resolver.walk_deps_with_count', return_value=iter([])):
        ok = controller.query(pkg=pkg, report_progress=_no_progress)

    assert ok is True
    mock_search_toolchains.assert_not_called()


# A typed query (e.g. 'libfoo-1.0.0.1') resolves against the
# currently selected toolchain by default, same as `pkq -l` - the dropdown
# must have an actual effect on this path.
def test_typed_query_defaults_to_current_toolchain(controller):
    with patch.object(RepositoryManager, 'search', return_value=iter([])) as mock_search:
        controller.query(text='libfoo-1.0.0.1', report_progress=_no_progress)

    # The first call is the actual lookup; if it comes up empty, the "not
    # found" error path probes other toolchains too (see
    # test_query_package_wrong_toolchain_lists_available_toolchains).
    called_pkg = mock_search.call_args_list[0].kwargs.get('pkg')
    assert str(called_pkg.toolchain) == str(controller.toolchain)


