# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import subprocess

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from rbbuild.buildsystem.ctest import CTest


def _ctest(tmp_path, build_config_switch=None, verbose=False):
    paths = SimpleNamespace(source=tmp_path, build=tmp_path / 'obj' / 'native')
    settings = SimpleNamespace(op_mode=SimpleNamespace(verbose=verbose))
    maketool = SimpleNamespace(build_config_switch=build_config_switch)
    ctest = CTest(settings=settings, paths=paths, maketool=maketool, metadata=MagicMock())
    ctest.ctest_executable = 'ctest'
    return ctest


def test_available_with_cmakelists(tmp_path):
    (tmp_path / 'CMakeLists.txt').write_text('')
    assert _ctest(tmp_path).available


def test_not_available_without_cmakelists(tmp_path):
    assert not _ctest(tmp_path).available


def test_run_tests_requires_setup(tmp_path):
    with pytest.raises(FileNotFoundError, match='Run setup first'):
        _ctest(tmp_path).run_tests()


def test_run_tests_calls_ctest_in_build_folder(tmp_path, monkeypatch):
    ctest = _ctest(tmp_path)
    (ctest.paths.build / 'CMakeFiles').mkdir(parents=True)
    calls = []
    monkeypatch.setattr(
        subprocess, 'run',
        lambda argv, **kwargs: calls.append((argv, kwargs)) or SimpleNamespace(returncode=0))

    ctest.run_tests()

    argv, kwargs = calls[0]
    assert argv == ['ctest', '-T', 'test', '--no-compress-output', str(ctest.paths.build)]
    assert kwargs['cwd'] == ctest.paths.build


def test_run_tests_passes_build_config(tmp_path, monkeypatch):
    ctest = _ctest(tmp_path, build_config_switch='Release')
    (ctest.paths.build / 'CMakeFiles').mkdir(parents=True)
    calls = []
    monkeypatch.setattr(
        subprocess, 'run',
        lambda argv, **kwargs: calls.append(argv) or SimpleNamespace(returncode=0))

    ctest.run_tests()

    assert calls[0][-2:] == ['--build-config', 'Release']


def test_run_tests_fails_if_ctest_fails(tmp_path, monkeypatch):
    ctest = _ctest(tmp_path)
    (ctest.paths.build / 'CMakeFiles').mkdir(parents=True)
    monkeypatch.setattr(subprocess, 'run', lambda argv, **kwargs: SimpleNamespace(returncode=8))

    with pytest.raises(RuntimeError, match='error code 8'):
        ctest.run_tests()
