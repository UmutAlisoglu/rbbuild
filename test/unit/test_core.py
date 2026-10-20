# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import os
import shutil
import sys
import sysconfig

import pytest

from pathlib import Path

from rbbuild.core.toolchain import Toolchain
from rbbuild.core.channel import Channel
from rbbuild.core.paths import Paths
from rbbuild.core.temp_folder import TempFolder

# Unit tests for rbbuild.core — Toolchain, Channel, Paths, TempFolder.


# ---------------------------------------------------------------------------
# Toolchain
# ---------------------------------------------------------------------------

_TOOLCHAINS = {
    'linux-native': {
        'platform': 'linux',
        'tcid':     'native',
        'cmake_file': Path('linux-native.cmake'),
        'native':   True,
    },
    'win32-mingw': {
        'platform': 'win32',
        'tcid':     'mingw',
        'cmake_file': Path('win32-mingw.cmake'),
        'wheel_platform_tag': 'win_amd64',
    },
}


def test_toolchain_by_full_id():
    tc = Toolchain(tcid='linux-native', toolchains_config=_TOOLCHAINS)
    assert tc.platform == 'linux'
    assert tc.name == 'native'
    assert tc.cmake_file == Path('linux-native.cmake')
    assert str(tc) == 'linux-native'


def test_toolchain_by_short_id():
    # Look up by tcid only (not the full key)
    tc = Toolchain(tcid='native', toolchains_config=_TOOLCHAINS)
    assert tc.platform == 'linux'
    assert tc.name == 'native'


def test_toolchain_repr():
    tc = Toolchain(tcid='linux-native', toolchains_config=_TOOLCHAINS)
    assert 'linux' in repr(tc)
    assert 'native' in repr(tc)


def test_toolchain_empty_tcid():
    tc = Toolchain(tcid=None, toolchains_config=_TOOLCHAINS)
    assert tc.platform == 'none'
    assert tc.name == 'any'
    assert tc.cmake_file is None
    assert str(tc) == 'none-any'


def test_toolchain_unknown_raises():
    with pytest.raises(LookupError):
        Toolchain(tcid='unknown-toolchain', toolchains_config=_TOOLCHAINS)


def test_toolchain_win32():
    tc = Toolchain(tcid='win32-mingw', toolchains_config=_TOOLCHAINS)
    assert tc.platform == 'win32'
    assert tc.name == 'mingw'
    assert str(tc) == 'win32-mingw'


def test_toolchain_native_and_wheel_platform_tag(monkeypatch):
    monkeypatch.setattr(sysconfig, 'get_platform', lambda: 'linux-aarch64')
    native = Toolchain(tcid='linux-native', toolchains_config=_TOOLCHAINS)
    assert native.native is True
    assert native.wheel_platform_tag == 'linux_aarch64'

    mingw = Toolchain(tcid='win32-mingw', toolchains_config=_TOOLCHAINS)
    assert mingw.native is False
    assert mingw.wheel_platform_tag == 'win_amd64'


# An explicit tag has precedence over the interpreter's platform.
def test_toolchain_wheel_platform_tag_wins_over_native(monkeypatch):
    monkeypatch.setattr(sysconfig, 'get_platform', lambda: 'linux-aarch64')
    config = {'linux-native': {
        **_TOOLCHAINS['linux-native'], 'wheel_platform_tag': 'linux_x86_64'}}
    tc = Toolchain(tcid='linux-native', toolchains_config=config)
    assert tc.wheel_platform_tag == 'linux_x86_64'


def test_toolchain_without_wheel_data():
    config = {'linux-a': {'platform': 'linux', 'tcid': 'a', 'cmake_file': None}}
    tc = Toolchain(tcid='linux-a', toolchains_config=config)
    assert tc.native is False
    assert tc.wheel_platform_tag is None
    assert tc.python_executable is None
    assert tc.python_environment == {}
    assert tc.python_path is None


def _python_toolchain(**python):
    config = {'linux-pypy310': {
        'platform': 'linux', 'tcid': 'pypy310', 'cmake_file': None, **python}}
    return Toolchain(tcid='linux-pypy310', toolchains_config=config)


# A name is looked up in PATH.
def test_toolchain_python_path_from_path(monkeypatch):
    monkeypatch.setattr(shutil, 'which', lambda name: f'/opt/bin/{name}')
    tc = _python_toolchain(python_executable='pypy3.10')
    assert tc.python_path == Path('/opt/bin/pypy3.10')


# An absolute path does not depend on PATH.
def test_toolchain_python_path_absolute(tmp_path, monkeypatch):
    monkeypatch.setenv('PATH', '')
    python = tmp_path / ('python.exe' if sys.platform == 'win32' else 'python')
    python.write_text('')
    python.chmod(0o755)
    tc = _python_toolchain(python_executable=str(python))
    assert tc.python_path == python


def test_toolchain_python_path_missing_raises(monkeypatch):
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    with pytest.raises(FileNotFoundError, match='pypy3.10'):
        _python_toolchain(python_executable='pypy3.10').python_path


def test_toolchain_python_environment_prepends_path_variables():
    tc = _python_toolchain(python_environment={'PYTHONPATH': '/opt/lib'})
    result = tc.apply_python_environment({'PYTHONPATH': '/existing'})
    assert result['PYTHONPATH'] == f'/opt/lib{os.pathsep}/existing'


def test_toolchain_python_environment_sets_path_variable_if_empty():
    tc = _python_toolchain(python_environment={'PYTHONPATH': '/opt/lib'})
    assert tc.apply_python_environment({})['PYTHONPATH'] == '/opt/lib'


def test_toolchain_python_environment_keeps_existing_other_variables():
    tc = _python_toolchain(python_environment={'PYTHONHOME': '/opt/py', 'PYTHONUTF8': '1'})
    result = tc.apply_python_environment({'PYTHONHOME': '/mine'})
    assert result['PYTHONHOME'] == '/mine'
    assert result['PYTHONUTF8'] == '1'


# The given environment is not modified.
def test_toolchain_python_environment_returns_copy():
    tc = _python_toolchain(python_environment={'PYTHONUTF8': '1'})
    environ = {}
    tc.apply_python_environment(environ)
    assert environ == {}


def test_toolchain_without_python_environment_is_noop():
    tc = Toolchain(tcid=None, toolchains_config={})
    assert tc.apply_python_environment({'A': '1'}) == {'A': '1'}


def test_toolchain_empty_tcid_has_no_wheel_data():
    tc = Toolchain(tcid=None, toolchains_config=_TOOLCHAINS)
    assert tc.native is False
    assert tc.wheel_platform_tag is None


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------

_CHANNELS = {
    'sample-development': {
        'type':           'rbbuild',
        'remote_service': 'artifactory_service',
        'repository':     'sample-development-local',
        'root_path':      'components',
        'redirect_repos': ['sample-release'],
    },
    'sample-release': {
        'type':           'rbbuild',
        'remote_service': 'artifactory_service',
        'repository':     'sample-release-local',
        'root_path':      'components',
        'permissions':    'upload',
        'branch_pattern': ['master', 'release/*'],
    },
    'example-git': {
        'type':           'git',
        'remote_service': 'git_service',
        'repository':     'EXAMPLE',
        'project':        'my_project',
    },
}


def test_channel_by_name(tmp_path):
    ch = Channel(
        name='sample-development',
        default_channel='sample-development',
        channels_config=_CHANNELS,
        source_path=str(tmp_path),
    )
    assert ch.name == 'sample-development'
    assert ch.type == 'rbbuild'
    assert ch.repository == 'sample-development-local'
    assert ch.root_path == 'components'
    assert ch.redirect_repos == ['sample-release']
    assert str(ch) == 'sample-development'


def test_channel_repr(tmp_path):
    ch = Channel(
        name='sample-development',
        default_channel='sample-development',
        channels_config=_CHANNELS,
        source_path=str(tmp_path),
    )
    assert 'sample-development' in repr(ch)
    assert 'rbbuild' in repr(ch)


def test_channel_default_fallback(tmp_path):
    # name=None, no git repo → falls back to default_channel
    ch = Channel(
        name=None,
        default_channel='sample-release',
        channels_config=_CHANNELS,
        source_path=str(tmp_path),
    )
    assert ch.name == 'sample-release'


def test_channel_unknown_raises(tmp_path):
    with pytest.raises(LookupError):
        Channel(
            name='no-such-channel',
            default_channel='sample-development',
            channels_config=_CHANNELS,
            source_path=str(tmp_path),
        )


def test_channel_permissions_default(tmp_path):
    ch = Channel(
        name='sample-development',
        default_channel='sample-development',
        channels_config=_CHANNELS,
        source_path=str(tmp_path),
    )
    assert ch.permissions == 'delete'


def test_channel_permissions_explicit(tmp_path):
    ch = Channel(
        name='sample-release',
        default_channel='sample-release',
        channels_config=_CHANNELS,
        source_path=str(tmp_path),
    )
    assert ch.permissions == 'upload'


def test_channel_project(tmp_path):
    ch = Channel(
        name='example-git',
        default_channel='example-git',
        channels_config=_CHANNELS,
        source_path=str(tmp_path),
    )
    assert ch.project == 'my_project'


def test_channel_no_redirect_repos(tmp_path):
    ch = Channel(
        name='example-git',
        default_channel='example-git',
        channels_config=_CHANNELS,
        source_path=str(tmp_path),
    )
    assert ch.redirect_repos == []


# When name=None and git branch matches a branch_pattern, that channel is chosen.
def test_channel_name_from_git_branch_match(tmp_path):
    from unittest.mock import MagicMock, patch
    mock_repo = MagicMock()
    mock_repo.head.is_detached = False
    mock_repo.head.ref.name = 'master'  # matches sample-release branch_pattern
    with patch('rbbuild.core.channel.Repo', return_value=mock_repo):
        ch = Channel(
            name=None,
            default_channel='sample-development',
            channels_config=_CHANNELS,
            source_path=str(tmp_path),
        )
    assert ch.name == 'sample-release'


# When name=None and git branch does not match any pattern, default_channel is used.
def test_channel_name_from_git_branch_no_match(tmp_path):
    from unittest.mock import MagicMock, patch
    mock_repo = MagicMock()
    mock_repo.head.is_detached = False
    mock_repo.head.ref.name = 'feature/xyz'  # no pattern matches
    with patch('rbbuild.core.channel.Repo', return_value=mock_repo):
        ch = Channel(
            name=None,
            default_channel='sample-development',
            channels_config=_CHANNELS,
            source_path=str(tmp_path),
        )
    assert ch.name == 'sample-development'


def _core(tmp_path, **settings):
    from dependency_injector import providers
    from rbbuild.core.container import Core
    core = Core(config=providers.Configuration())
    core.config.from_dict({
        'settings': {
            'platform': 'linux',
            'default_channel': 'sample-development',
            'toolchain-linux': 'linux-native',
            **settings,
        },
        'profile': {
            'channels': _CHANNELS,
            'toolchains': {'linux-native': {
                'platform': 'linux', 'tcid': 'native', 'cmake_file': 'native.cmake'}},
        },
        'paths': {'source': str(tmp_path)},
    })
    return core


def _on_branch(name):
    from unittest.mock import MagicMock, patch
    mock_repo = MagicMock()
    mock_repo.head.is_detached = False
    mock_repo.head.ref.name = name
    return patch('rbbuild.core.channel.Repo', return_value=mock_repo)


# The channel of the profile is only the default: a matching branch pattern comes first.
def test_core_channel_branch_pattern_before_profile_default(tmp_path):
    with _on_branch('master'):
        assert _core(tmp_path).channel().name == 'sample-release'


# An explicit selection (-C) wins over the branch pattern.
def test_core_channel_explicit_selection_wins(tmp_path):
    with _on_branch('master'):
        core = _core(tmp_path, channel='sample-development')
        assert core.channel().name == 'sample-development'


# A project without toolchain selects none-any, but packages without toolchain are
# looked up for the default of the profile.
def test_core_selected_and_target_toolchain_without_toolchain_need(tmp_path):
    core = _core(tmp_path, toolchain_required=False)
    assert str(core.toolchain()) == 'none-any'
    assert str(core.target_toolchain()) == 'linux-native'


def test_core_explicit_none_any_is_also_the_target(tmp_path):
    core = _core(tmp_path, toolchain='none-any', toolchain_required=True)
    assert str(core.toolchain()) == 'none-any'
    assert str(core.target_toolchain()) == 'none-any'


def test_core_toolchain_is_profile_default_if_project_needs_one(tmp_path):
    core = _core(tmp_path, toolchain_required=True)
    assert str(core.toolchain()) == 'linux-native'
    assert str(core.target_toolchain()) == 'linux-native'


# When git HEAD is detached, branch is not read and default_channel is used.
def test_channel_git_detached_head(tmp_path):
    from unittest.mock import MagicMock, patch
    mock_repo = MagicMock()
    mock_repo.head.is_detached = True
    with patch('rbbuild.core.channel.Repo', return_value=mock_repo):
        ch = Channel(
            name=None,
            default_channel='sample-development',
            channels_config=_CHANNELS,
            source_path=str(tmp_path),
        )
    assert ch.name == 'sample-development'


# Exceptions other than InvalidGitRepositoryError are re-raised.
def test_channel_git_other_exception_reraises(tmp_path):
    from unittest.mock import patch
    with patch('rbbuild.core.channel.Repo', side_effect=RuntimeError('unexpected')):
        with pytest.raises(RuntimeError, match='unexpected'):
            Channel(
                name=None,
                default_channel='sample-development',
                channels_config=_CHANNELS,
                source_path=str(tmp_path),
            )


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _make_paths(tmp_path, toolchain=None, install_prefix=None):
    if toolchain is None:
        toolchain = Toolchain(tcid='linux-native', toolchains_config=_TOOLCHAINS)
    return Paths(
        rbbuild_root=str(tmp_path / 'rbbuild'),
        source=str(tmp_path / 'project'),
        staging_root='staging',
        build_root='obj',
        documentation_root='obj',
        dist=str(tmp_path / 'dist'),
        install_prefix=install_prefix,
        toolchain=toolchain,
    )


def test_paths_basic(tmp_path):
    p = _make_paths(tmp_path)
    assert p.staging.name == 'linux-native'
    assert p.build.name == 'linux-native'
    assert p.documentation == p.documentation_root / 'documentation'
    assert p.install_prefix == p.staging


def test_paths_explicit_install_prefix(tmp_path):
    install = str(tmp_path / 'my_prefix')
    p = _make_paths(tmp_path, install_prefix=install)
    assert p.install_prefix == Path(install)


def test_paths_dotdot_raises(tmp_path):
    with pytest.raises(RuntimeError, match='must not contain'):
        Paths(
            rbbuild_root=str(tmp_path),
            source=str(tmp_path),
            staging_root='../bad',
            build_root='obj',
            documentation_root='obj',
            dist=str(tmp_path),
            install_prefix=None,
            toolchain=Toolchain(tcid=None, toolchains_config={}),
        )


def test_paths_absolute_staging_raises(tmp_path):
    import sys
    abs_path = 'C:\\absolute\\path' if sys.platform == 'win32' else '/absolute/path'
    with pytest.raises(RuntimeError, match='must be a relative path'):
        Paths(
            rbbuild_root=str(tmp_path),
            source=str(tmp_path),
            staging_root=abs_path,
            build_root='obj',
            documentation_root='obj',
            dist=str(tmp_path),
            install_prefix=None,
            toolchain=Toolchain(tcid=None, toolchains_config={}),
        )


# ---------------------------------------------------------------------------
# TempFolder
# ---------------------------------------------------------------------------

def test_temp_folder_with_explicit_path(tmp_path):
    folder_path = tmp_path / 'myfolder'
    tf = TempFolder(path=folder_path)
    result = tf.path
    assert result == folder_path
    assert folder_path.exists()
    # Cleanup and prevent double __del__
    folder_path.rmdir()
    tf._path = None

    
def test_temp_folder_without_path():
    tf = TempFolder(path=None)
    result = tf.path
    assert result.exists()
    assert result.name.startswith('rbbuild-')
    # Cleanup temp dir so __del__ doesn't raise
    result.rmdir()


# __del__ raises ResourceWarning when the folder still has contents.
def test_temp_folder_del_warns_if_not_empty(tmp_path):
    folder_path = tmp_path / 'nonempty'
    folder_path.mkdir()
    (folder_path / 'leftover.txt').write_text('data')

    tf = TempFolder(path=folder_path)
    with pytest.raises(ResourceWarning):
        tf.__del__()
    # Prevent GC from calling __del__ again on the still-live path
    tf._path = None
    # Cleanup manually
    (folder_path / 'leftover.txt').unlink()
    folder_path.rmdir()


# __del__ removes the folder when it is empty.
def test_temp_folder_del_removes_empty_dir(tmp_path):
    folder_path = tmp_path / 'empty_folder'
    folder_path.mkdir()
    tf = TempFolder(path=folder_path)
    tf.__del__()
    # Prevent GC from calling __del__ again after folder was removed
    tf._path = None
    assert not folder_path.exists()

