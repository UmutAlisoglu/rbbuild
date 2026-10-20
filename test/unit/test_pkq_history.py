# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

from rbbuild.ui.pkq.history import PkqHistory

# Unit tests for PkqHistory - the pickle-backed recent-queries/last-download
# -dir persistence used by the pkq GUI.


@pytest.fixture()
def history(tmp_path):
    return PkqHistory(tmp_path)


def test_new_history_is_empty(history):
    assert history.entries == []
    assert history.last() is None
    assert history.last_download_dir is None


def test_add_records_entry(history):
    history.add('foo-1.2.3', channel='dev', toolchain='linux-native')
    assert history.entries == ['foo-1.2.3']
    assert history.last() == {'package': 'foo-1.2.3', 'channel': 'dev', 'toolchain': 'linux-native'}


def test_add_ignores_empty_package(history):
    history.add('', channel='dev', toolchain='linux-native')
    assert history.entries == []


def test_add_moves_existing_entry_to_front(history):
    history.add('foo-1.0', channel='dev', toolchain=None)
    history.add('bar-2.0', channel='dev', toolchain=None)
    history.add('foo-1.0', channel='prod', toolchain=None)

    assert history.entries == ['foo-1.0', 'bar-2.0']
    assert history.last() == {'package': 'foo-1.0', 'channel': 'prod', 'toolchain': None}


def test_add_caps_history_length(history):
    for i in range(25):
        history.add(f'pkg-{i}', channel=None, toolchain=None)

    assert len(history.entries) == 20
    assert history.entries[0] == 'pkg-24'


def test_find_returns_matching_entry(history):
    history.add('foo-1.0', channel='dev', toolchain='linux-native')
    assert history.find('foo-1.0') == {'package': 'foo-1.0', 'channel': 'dev', 'toolchain': 'linux-native'}
    assert history.find('missing') is None


def test_last_download_dir_persists_across_instances(tmp_path):
    history = PkqHistory(tmp_path)
    history.last_download_dir = str(tmp_path / 'downloads')

    reloaded = PkqHistory(tmp_path)
    assert reloaded.last_download_dir == str(tmp_path / 'downloads')


def test_history_persists_across_instances(tmp_path):
    history = PkqHistory(tmp_path)
    history.add('foo-1.0', channel='dev', toolchain='linux-native')

    reloaded = PkqHistory(tmp_path)
    assert reloaded.entries == ['foo-1.0']


def test_corrupt_history_file_is_ignored(tmp_path):
    state_file = tmp_path / 'gui_state.pickle'
    state_file.write_bytes(b'not a pickle')

    history = PkqHistory(tmp_path)
    assert history.entries == []
    assert history.last_download_dir is None
