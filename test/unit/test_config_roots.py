# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

from rbbuild.container import config_roots
from rbbuild.container.config_roots import ENTRY_POINT_GROUP, load_config_roots
from rbbuild.container.configuration import RBBuildConfiguration


# ---------------------------------------------------------------------------
# load_config_roots()
# ---------------------------------------------------------------------------

def _make_package(tmp_path, name):
    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / '__init__.py').write_text('')
    return pkg


def _patch_entry_points(monkeypatch, eps):
    monkeypatch.setattr(
        config_roots, 'entry_points',
        lambda group: [ep for ep in eps if ep.group == group],
    )


def _ep(name, value):
    return EntryPoint(name=name, value=value, group=ENTRY_POINT_GROUP)


def test_load_config_roots_returns_package_dirs_sorted_by_name(tmp_path, monkeypatch):
    pkg_a = _make_package(tmp_path, 'cfg_pkg_a')
    pkg_b = _make_package(tmp_path, 'cfg_pkg_b')
    monkeypatch.syspath_prepend(str(tmp_path))
    _patch_entry_points(monkeypatch, [_ep('b', 'cfg_pkg_b'), _ep('a', 'cfg_pkg_a')])
    assert load_config_roots() == [pkg_a, pkg_b]


def test_load_config_roots_skips_missing_module(tmp_path, monkeypatch):
    pkg = _make_package(tmp_path, 'cfg_pkg_ok')
    monkeypatch.syspath_prepend(str(tmp_path))
    _patch_entry_points(monkeypatch, [_ep('gone', 'cfg_pkg_does_not_exist'), _ep('ok', 'cfg_pkg_ok')])
    assert load_config_roots() == [pkg]


def test_load_config_roots_skips_plain_module(tmp_path, monkeypatch):
    (tmp_path / 'cfg_plain_module.py').write_text('')
    monkeypatch.syspath_prepend(str(tmp_path))
    _patch_entry_points(monkeypatch, [_ep('plain', 'cfg_plain_module')])
    assert load_config_roots() == []


def test_load_config_roots_does_not_import_the_package(tmp_path, monkeypatch):
    pkg = _make_package(tmp_path, 'cfg_pkg_noimport')
    (pkg / '__init__.py').write_text('raise RuntimeError("imported")')
    monkeypatch.syspath_prepend(str(tmp_path))
    _patch_entry_points(monkeypatch, [_ep('x', 'cfg_pkg_noimport')])
    assert load_config_roots() == [pkg]


# ---------------------------------------------------------------------------
# RBBuildConfiguration.load_profile() with config roots
# ---------------------------------------------------------------------------

def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _profile(base: Path, name: str, source: str):
    _write(base / 'profiles' / name / f'{name}.toml', f'[profile.marker]\nsource = "{source}"\n')


def _service(base: Path, name: str, url: str):
    _write(base / f'{name}.toml', f'[profile.services.{name}]\ntype = "x"\nurl = "{url}"\n')


@pytest.fixture
def dirs(tmp_path):
    return {
        'system': tmp_path / 'system',
        'root1':  tmp_path / 'root1',
        'root2':  tmp_path / 'root2',
        'user':   tmp_path / 'user',
    }


def _load(dirs, profile_name, roots=('root1', 'root2')):
    config = RBBuildConfiguration()
    config.load_profile(
        profile_name=profile_name,
        rbbuild_config_path=dirs['system'],
        user_config_path=dirs['user'],
        config_roots=[dirs[r] for r in roots],
    )
    return config


def test_load_profile_finds_profiles_of_all_sources(dirs):
    _profile(dirs['system'], 'sys', 'system')
    _profile(dirs['root1'], 'plug', 'root1')
    _profile(dirs['user'], 'usr', 'user')
    profiles = _load(dirs, 'plug').profiles()
    assert set(profiles) == {'sys', 'plug', 'usr'}


def test_load_profile_later_source_wins(dirs):
    _profile(dirs['system'], 'p', 'system')
    _profile(dirs['root1'], 'p', 'root1')
    _profile(dirs['root2'], 'p', 'root2')
    assert _load(dirs, 'p').profile.marker.source() == 'root2'

    _profile(dirs['user'], 'p', 'user')
    assert _load(dirs, 'p').profile.marker.source() == 'user'


def test_load_profile_shared_services_later_root_wins(dirs):
    _profile(dirs['root1'], 'p', 'root1')
    _service(dirs['root1'] / 'remote-services', 'svc', 'root1')
    _service(dirs['root2'] / 'remote-services', 'svc', 'root2')
    _service(dirs['root1'] / 'remote-services', 'only_root1', 'root1')
    services = _load(dirs, 'p').profile.services()
    assert services['svc']['url'] == 'root2'
    assert services['only_root1']['url'] == 'root1'


def test_load_profile_profile_service_overrides_shared(dirs):
    _profile(dirs['root1'], 'p', 'root1')
    _service(dirs['root1'] / 'remote-services', 'svc', 'shared')
    _service(dirs['root1'] / 'profiles' / 'p' / 'remote-services', 'svc', 'profile')
    assert _load(dirs, 'p').profile.services()['svc']['url'] == 'profile'


def test_load_profile_shared_services_apply_to_every_profile(dirs):
    _profile(dirs['system'], 'sys', 'system')
    _service(dirs['root1'] / 'remote-services', 'svc', 'shared')
    assert _load(dirs, 'sys').profile.services()['svc']['url'] == 'shared'


def test_load_profile_without_roots_and_missing_dirs(dirs):
    _profile(dirs['system'], 'sys', 'system')
    config = _load(dirs, 'sys', roots=())
    assert config.profile.marker.source() == 'system'


def test_load_profile_unknown_profile_raises(dirs):
    _profile(dirs['system'], 'sys', 'system')
    with pytest.raises(LookupError, match='Could not find profile nope'):
        _load(dirs, 'nope')


# ---------------------------------------------------------------------------
# RBBuildConfiguration.load_profile() - toolchain definitions
# ---------------------------------------------------------------------------

def _toolchain(dirs, name, toml_text=None, cmake=True, profile='p'):
    toolchains = dirs['system'] / 'profiles' / profile / 'toolchains'
    if toml_text is not None:
        _write(toolchains / f'{name}.toml', toml_text)
    if cmake:
        _write(toolchains / 'cmake' / f'{name}.cmake', '')
    return toolchains


def _toolchains(dirs):
    _profile(dirs['system'], 'p', 'system')
    return _load(dirs, 'p', roots=()).profile.toolchains()


def test_toolchain_defined_by_toml(dirs):
    toolchains = _toolchain(dirs, 'linux-native', '[toolchain]\nnative = true\n')
    tc = _toolchains(dirs)['linux-native']
    assert tc['platform'] == 'linux'
    assert tc['tcid'] == 'native'
    assert tc['native'] is True
    assert Path(tc['cmake_file']) == toolchains / 'cmake' / 'linux-native.cmake'
    assert 'wheel_platform_tag' not in tc


def test_toolchain_wheel_platform_tag(dirs):
    _toolchain(dirs, 'linux-ubuntu-armhf', "[wheel]\nplatform-tag = 'linux_armv7l'\n")
    tc = _toolchains(dirs)['linux-ubuntu-armhf']
    assert tc['native'] is False
    assert tc['wheel_platform_tag'] == 'linux_armv7l'


def test_toolchain_empty_toml_is_valid(dirs):
    _toolchain(dirs, 'linux-stm32', '')
    assert _toolchains(dirs)['linux-stm32']['native'] is False


def test_toolchain_python_section(dirs):
    _toolchain(
        dirs, 'linux-pypy310',
        "[python]\nexecutable = 'pypy3.10'\n[python.environment]\nPYTHONPATH = '/opt/pypy/lib'\n")
    tc = _toolchains(dirs)['linux-pypy310']
    assert tc['python_executable'] == 'pypy3.10'
    assert tc['python_environment'] == {'PYTHONPATH': '/opt/pypy/lib'}


def _python_toolchains(dirs, **toml_texts):
    for name, text in toml_texts.items():
        _toolchain(dirs, name.replace('_', '-', 1), text)
    return _toolchains(dirs)


# [python] import takes over the section of another toolchain.
def test_toolchain_python_import(dirs):
    toolchains = _python_toolchains(
        dirs,
        linux_cpython314="[python]\nexecutable = 'python3.14'\n[python.environment]\nPYTHONUTF8 = '1'\n",
        linux_native="[toolchain]\nnative = true\n[python]\nimport = 'linux-cpython314'\n",
    )
    tc = toolchains['linux-native']
    assert tc['native'] is True
    assert tc['python_executable'] == 'python3.14'
    assert tc['python_environment'] == {'PYTHONUTF8': '1'}


# Keys of the importing toolchain override the imported ones.
def test_toolchain_python_import_override(dirs):
    toolchains = _python_toolchains(
        dirs,
        linux_cpython314="[python]\nexecutable = 'python3.14'\n[python.environment]\nA = '1'\nB = '1'\n",
        linux_native="[python]\nimport = 'linux-cpython314'\nexecutable = '/opt/py'\n[python.environment]\nB = '2'\n",
    )
    tc = toolchains['linux-native']
    assert tc['python_executable'] == '/opt/py'
    assert tc['python_environment'] == {'A': '1', 'B': '2'}


def test_toolchain_python_import_is_transitive(dirs):
    toolchains = _python_toolchains(
        dirs,
        linux_a="[python]\nexecutable = 'python3.14'\n",
        linux_b="[python]\nimport = 'linux-a'\n",
        linux_c="[python]\nimport = 'linux-b'\n",
    )
    assert toolchains['linux-c']['python_executable'] == 'python3.14'


def test_toolchain_python_import_of_unknown_toolchain_raises(dirs):
    with pytest.raises(LookupError, match='linux-nope'):
        _python_toolchains(dirs, linux_a="[python]\nimport = 'linux-nope'\n")


@pytest.mark.parametrize('texts', [
    {'linux_a': "[python]\nimport = 'linux-a'\n"},
    {'linux_a': "[python]\nimport = 'linux-b'\n", 'linux_b': "[python]\nimport = 'linux-a'\n"},
])
def test_toolchain_python_import_cycle_raises(dirs, texts):
    with pytest.raises(RuntimeError, match='circular'):
        _python_toolchains(dirs, **texts)


def test_toolchain_cmake_file_override(dirs):
    toolchains = _toolchain(dirs, 'linux-a', "[cmake]\nfile = 'cmake/common.cmake'\n", cmake=False)
    _write(toolchains / 'cmake' / 'common.cmake', '')
    tc = _toolchains(dirs)['linux-a']
    assert Path(tc['cmake_file']) == toolchains / 'cmake' / 'common.cmake'


# The CMake file is not checked by the loader, but passed on to CMake.
def test_toolchain_without_cmake_file_is_valid(dirs):
    toolchains = _toolchain(dirs, 'linux-a', '', cmake=False)
    tc = _toolchains(dirs)['linux-a']
    assert Path(tc['cmake_file']) == toolchains / 'cmake' / 'linux-a.cmake'


# A CMake file without toolchain definition is not a toolchain.
def test_toolchain_cmake_file_without_toml_is_not_a_toolchain(dirs):
    _toolchain(dirs, 'linux-old', None)
    assert 'linux-old' not in (_toolchains(dirs) or {})


# ---------------------------------------------------------------------------
# RBBuildConfiguration.load_profile() - [profile] import
# ---------------------------------------------------------------------------

def _import_profile(dirs, name, text, base='system'):
    _write(dirs[base] / 'profiles' / name / f'{name}.toml', text)


def test_profile_import_is_base_of_importing_profile(dirs):
    _import_profile(dirs, 'base', '[settings]\nchannel = "a"\nprofile_version = "1"\n')
    _import_profile(dirs, 'p', '[profile]\nimport = "base"\n[settings]\nchannel = "b"\n')
    settings = _load(dirs, 'p', roots=()).settings()
    assert settings['default_channel'] == 'b'
    assert settings['profile_version'] == '1'


def test_profile_import_is_transitive(dirs):
    _import_profile(dirs, 'a', '[profile.marker]\nsource = "a"\n')
    _import_profile(dirs, 'b', '[profile]\nimport = "a"\n')
    _import_profile(dirs, 'c', '[profile]\nimport = "b"\n')
    assert _load(dirs, 'c', roots=()).profile.marker.source() == 'a'


def test_profile_import_reuses_and_overrides_toolchains(dirs):
    _import_profile(dirs, 'base', '')
    _import_profile(dirs, 'p', '[profile]\nimport = "base"\n')
    base_tcs = _toolchain(dirs, 'linux-a', '[toolchain]\nnative = true\n', profile='base')
    _toolchain(dirs, 'linux-b', '', profile='base')
    own_tcs = _toolchain(dirs, 'linux-b', '[toolchain]\nnative = true\n')
    toolchains = _load(dirs, 'p', roots=()).profile.toolchains()
    assert Path(toolchains['linux-a']['cmake_file']) == base_tcs / 'cmake' / 'linux-a.cmake'
    assert toolchains['linux-b']['native'] is True
    assert Path(toolchains['linux-b']['cmake_file']) == own_tcs / 'cmake' / 'linux-b.cmake'


def test_profile_import_reuses_and_overrides_services(dirs):
    _import_profile(dirs, 'base', '')
    _import_profile(dirs, 'p', '[profile]\nimport = "base"\n')
    _service(dirs['system'] / 'profiles' / 'base' / 'remote-services', 'svc', 'base')
    _service(dirs['system'] / 'profiles' / 'base' / 'remote-services', 'only_base', 'base')
    _service(dirs['system'] / 'profiles' / 'p' / 'remote-services', 'svc', 'own')
    services = _load(dirs, 'p', roots=()).profile.services()
    assert services['svc']['url'] == 'own'
    assert services['only_base']['url'] == 'base'


def test_profile_import_of_profile_from_config_root(dirs):
    _profile(dirs['root1'], 'base', 'root1')
    _import_profile(dirs, 'p', '[profile]\nimport = "base"\n', base='user')
    assert _load(dirs, 'p').profile.marker.source() == 'root1'


def test_profile_import_of_unknown_profile_raises(dirs):
    _import_profile(dirs, 'p', '[profile]\nimport = "nope"\n')
    with pytest.raises(LookupError, match='Could not find profile nope'):
        _load(dirs, 'p', roots=())


def test_profile_import_cycle_raises(dirs):
    _import_profile(dirs, 'a', '[profile]\nimport = "b"\n')
    _import_profile(dirs, 'b', '[profile]\nimport = "a"\n')
    with pytest.raises(RuntimeError, match='circular'):
        _load(dirs, 'a', roots=())


# ---------------------------------------------------------------------------
# RBBuildConfiguration.load_profile() - ruff.toml
# ---------------------------------------------------------------------------

def test_profile_ruff_config_is_not_set_without_ruff_toml(dirs):
    _import_profile(dirs, 'p', '')
    assert _load(dirs, 'p', roots=()).profile.ruff_config() is None


def test_profile_ruff_config_is_path_of_ruff_toml(dirs):
    _import_profile(dirs, 'p', '')
    _write(dirs['system'] / 'profiles' / 'p' / 'ruff.toml', '')
    ruff_config = _load(dirs, 'p', roots=()).profile.ruff_config()
    assert Path(ruff_config) == dirs['system'] / 'profiles' / 'p' / 'ruff.toml'


def test_profile_ruff_config_is_taken_from_imported_profile(dirs):
    _import_profile(dirs, 'base', '')
    _import_profile(dirs, 'p', '[profile]\nimport = "base"\n')
    _write(dirs['system'] / 'profiles' / 'base' / 'ruff.toml', '')
    ruff_config = _load(dirs, 'p', roots=()).profile.ruff_config()
    assert Path(ruff_config) == dirs['system'] / 'profiles' / 'base' / 'ruff.toml'


def test_profile_ruff_config_of_importing_profile_wins(dirs):
    _import_profile(dirs, 'base', '')
    _import_profile(dirs, 'p', '[profile]\nimport = "base"\n')
    _write(dirs['system'] / 'profiles' / 'base' / 'ruff.toml', '')
    _write(dirs['system'] / 'profiles' / 'p' / 'ruff.toml', '')
    ruff_config = _load(dirs, 'p', roots=()).profile.ruff_config()
    assert Path(ruff_config) == dirs['system'] / 'profiles' / 'p' / 'ruff.toml'
