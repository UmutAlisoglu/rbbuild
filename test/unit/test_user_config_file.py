# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest
import tomllib

from rbbuild.librbb.user_config_file import UserConfigFile


# --- __setitem__ ---

# Empty key raises SyntaxError
def test_set_empty_key(tmp_path):
    writer = UserConfigFile(tmp_path)
    with pytest.raises(SyntaxError):
        writer[''] = 'value'


# Normal key (no dot) is placed under [settings]
def test_set_simple_key(tmp_path):
    writer = UserConfigFile(tmp_path)
    writer['mykey'] = 'myvalue'
    assert writer.data == {'settings': {'mykey': 'myvalue'}}


# Dotted key is nested
def test_set_dotted_key(tmp_path):
    writer = UserConfigFile(tmp_path)
    writer['section.key'] = 'value'
    assert writer.data == {'section': {'key': 'value'}}


# --- write() — new file path ---

# Creates rbbuild.toml when it does not exist
def test_write_creates_new_file(tmp_path):
    writer = UserConfigFile(tmp_path)
    writer['section.mykey'] = 'hello'
    writer.write()

    config_file = tmp_path / 'rbbuild.toml'
    assert config_file.exists()
    with open(config_file, 'rb') as fd:
        data = tomllib.load(fd)
    assert data['section']['mykey'] == 'hello'


# --- write() — existing file path ---

# Loads existing rbbuild.toml, merges new values, and saves
def test_write_updates_existing_file(tmp_path):
    config_file = tmp_path / 'rbbuild.toml'
    # Write initial content
    config_file.write_text('[existing]\nfoo = "bar"\n')

    writer = UserConfigFile(tmp_path)
    writer['section.newkey'] = 'newvalue'
    writer.write()

    with open(config_file, 'rb') as fd:
        data = tomllib.load(fd)
    # Old key preserved
    assert data['existing']['foo'] == 'bar'
    # New key added
    assert data['section']['newkey'] == 'newvalue'


# --- context manager ---

# __enter__ / __exit__ automatically calls write()
def test_context_manager_calls_write(tmp_path):
    config_file = tmp_path / 'rbbuild.toml'
    with UserConfigFile(tmp_path) as writer:
        writer['section.key'] = 'ctx_value'

    with open(config_file, 'rb') as fd:
        data = tomllib.load(fd)
    assert data['section']['key'] == 'ctx_value'
