# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

import rbbuild.container.configuration as configuration


# Installed profile packages (rbbuild.config entry points) must not leak into tests.
@pytest.fixture(autouse=True)
def no_config_roots(monkeypatch):
    monkeypatch.setattr(configuration, 'load_config_roots', lambda: [])


# rbbuild -T exports the toolchain to pytest, which would override the default.
@pytest.fixture(autouse=True)
def no_selection_env(monkeypatch):
    monkeypatch.delenv('RBB_TOOLCHAIN_ID', raising=False)
    monkeypatch.delenv('RBB_CHANNEL', raising=False)
