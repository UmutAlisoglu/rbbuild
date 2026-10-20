# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rbbuild.buildsystem.cmake import CMake

# Unit tests for the CMake arguments that depend on the toolchain.


def _setup_argv(tmp_path, python_path, cmake_file='file'):
    (tmp_path / 'CMakeLists.txt').write_text('')
    tc_file = tmp_path / 'tc.cmake'
    if cmake_file == 'file':
        tc_file.write_text('')
    cmake = CMake.__new__(CMake)
    cmake.settings = MagicMock()
    cmake.settings.op_mode.verbose = False
    cmake.settings.toolchain = SimpleNamespace(
        name='native', python_path=python_path,
        cmake_file=None if cmake_file == 'none' else tc_file)
    cmake.paths = MagicMock(source=tmp_path, build=tmp_path / 'obj', install_prefix=tmp_path / 'staging')
    cmake.maketool = MagicMock(setup_args=[], vs_architecture=None, cmake_generator='Ninja')
    cmake.cmake_config = {}
    cmake.metadata = MagicMock(environ={})
    cmake.__dict__['cmake_executable'] = 'cmake'

    with patch('rbbuild.buildsystem.cmake.subprocess.run') as run:
        run.return_value.returncode = 0
        cmake.setup(tmp_path / 'staging')
    return run.call_args.args[0]


def test_setup_passes_python_executable_of_toolchain(tmp_path):
    argv = _setup_argv(tmp_path, Path('/opt/py/python3.14'))
    assert '-DPython3_EXECUTABLE=/opt/py/python3.14' in argv


def test_setup_without_python_toolchain_passes_no_python(tmp_path):
    argv = _setup_argv(tmp_path, None)
    assert not any(arg.startswith('-DPython3_') for arg in argv)


@pytest.mark.parametrize('cmake_file', ['none', 'missing'])
def test_setup_rejects_toolchain_without_cmake_file(tmp_path, cmake_file):
    with pytest.raises(RuntimeError, match='no CMake toolchain file'):
        _setup_argv(tmp_path, None, cmake_file=cmake_file)
