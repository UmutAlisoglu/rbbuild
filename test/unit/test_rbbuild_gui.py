# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import argparse
import shutil

import pytest

from pathlib import Path

from rbbuild.rbbuild_gui import build_application
from rbbuild.ui.pkq.control import PkqController

# Unit tests for rbbuild.rbbuild_gui.build_application().

_RBB_ROOT = Path('rbbuild')
_CONFIG_PATH = Path('share/rbbuild/config')


def _args(**overrides):
    defaults = dict(
        tcid=None,
        verbose=False,
        profile=None,
        channel=None,
        platform='linux',
        log_level=None,
        version=False,
        package=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    user_home = tmp_path / 'home/user'
    shutil.copytree('test/data/user_home', user_home)
    monkeypatch.setenv('HOME', str(user_home))
    yield user_home


# ---------------------------------------------------------------------------
# Initial bootstrap (no profile_name) — explicit CLI overrides must apply
# ---------------------------------------------------------------------------

# An explicit -C/--channel value is honored on initial bootstrap.
def test_initial_bootstrap_respects_cli_channel_override(home):
    args = _args(channel='rbbuild-test')
    application = build_application(_RBB_ROOT, _CONFIG_PATH, args)
    try:
        assert application.core.channel().name == 'rbbuild-test'
    finally:
        application.unwire()


# An explicit -t/--toolchain value is honored on initial bootstrap.
def test_initial_bootstrap_respects_cli_tcid_override(home):
    args = _args(tcid='linux-ubuntu-armhf')
    application = build_application(_RBB_ROOT, _CONFIG_PATH, args)
    try:
        assert str(application.core.toolchain()) == 'linux-ubuntu-armhf'
    finally:
        application.unwire()


# ---------------------------------------------------------------------------
# Profile switch (profile_name given) — CLI overrides from the original
# launch must NOT carry over to the new profile (this was the bug).
# ---------------------------------------------------------------------------

# Switching profile must not crash and must fall back to the new profile's
# own default channel, even though the original args' channel does not
# exist there (this reproduces the originally reported bug exactly).
def test_profile_switch_resets_cli_channel_override(home):
    args = _args(channel='rbbuild-test')
    app1 = build_application(_RBB_ROOT, _CONFIG_PATH, args)
    try:
        assert app1.core.channel().name == 'rbbuild-test'

        app2 = build_application(_RBB_ROOT, _CONFIG_PATH, args, profile_name='standalone')
        try:
            assert app2.config.settings.profile() == 'standalone'
            assert app2.core.channel().name == 'local'
        finally:
            app2.unwire()
    finally:
        app1.unwire()


# Switching profile must not keep a non-default toolchain selected via the
# original launch's -t flag; the new profile's own default must apply.
def test_profile_switch_resets_cli_tcid_override(home):
    args = _args(tcid='linux-ubuntu-armhf')
    app1 = build_application(_RBB_ROOT, _CONFIG_PATH, args)
    try:
        assert str(app1.core.toolchain()) == 'linux-ubuntu-armhf'

        app2 = build_application(_RBB_ROOT, _CONFIG_PATH, args, profile_name='standalone')
        try:
            assert app2.config.settings.profile() == 'standalone'
            assert str(app2.core.toolchain()) == 'linux-native'
        finally:
            app2.unwire()
    finally:
        app1.unwire()


# ---------------------------------------------------------------------------
# Consistency: a runtime toolchain override made via the combobox
# (PkqController.select_platform_toolchain, i.e. config.override()) must be
# discarded on profile switch exactly like a CLI -t override is.
# ---------------------------------------------------------------------------

def test_profile_switch_resets_runtime_toolchain_override(home):
    args = _args()
    app1 = build_application(_RBB_ROOT, _CONFIG_PATH, args)
    try:
        PkqController(app1, args).select_platform_toolchain('linux-ubuntu-armhf')
        assert str(app1.core.toolchain()) == 'linux-ubuntu-armhf'

        app2 = build_application(_RBB_ROOT, _CONFIG_PATH, args, profile_name='standalone')
        try:
            assert app2.config.settings.profile() == 'standalone'
            assert str(app2.core.toolchain()) == 'linux-native'
        finally:
            app2.unwire()
    finally:
        app1.unwire()
