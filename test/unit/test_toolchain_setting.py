# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

from rbbuild.core.toolchain import default_toolchain_setting

_CANONICAL = ('settings.toolchain-linux', 'linux-yocto-armhf-4.0')


@pytest.mark.parametrize('key, value', [
    ('toolchain-linux', 'linux-yocto-armhf-4.0'),
    ('toolchain', 'linux-yocto-armhf-4.0'),
    ('toolchain', 'yocto-armhf-4.0'),
    ('toolchain-linux', 'yocto-armhf-4.0'),
    ('settings.toolchain', 'yocto-armhf-4.0'),
    ('settings.toolchain-linux', 'linux-yocto-armhf-4.0'),
])
def test_equivalent_spellings(key, value):
    assert default_toolchain_setting(key, value, 'linux', {}) == _CANONICAL


def test_toolchain_without_platform_uses_current_platform():
    assert default_toolchain_setting('toolchain', 'native', 'win32', {}) == ('settings.toolchain-win32', 'win32-native')


def test_platform_prefix_of_value_selects_platform():
    assert default_toolchain_setting('toolchain', 'win32-vs2022', 'linux', {}) == ('settings.toolchain-win32', 'win32-vs2022')


def test_platforms_of_profile_toolchains_are_known():
    toolchains = {'qnx-aarch64': {'platform': 'qnx', 'tcid': 'aarch64'}}
    assert default_toolchain_setting('toolchain', 'qnx-aarch64', 'linux', toolchains) == ('settings.toolchain-qnx', 'qnx-aarch64')


def test_platform_of_key_and_value_must_match():
    with pytest.raises(SyntaxError):
        default_toolchain_setting('toolchain-linux', 'win32-vs2022', 'linux', {})


@pytest.mark.parametrize('key', ['toolchains', 'settings.profile', 'profile.services.a.url'])
def test_other_keys_are_unchanged(key):
    assert default_toolchain_setting(key, 'x', 'linux', {}) == (key, 'x')
