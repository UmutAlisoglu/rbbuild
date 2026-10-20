#!/usr/bin/env python

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

# Integration tests for the examples that build a Python wheel with compiled
# C code (documentation/examples/python-ctypes-c and python-cext-c).
import re
import shutil
import subprocess
import sys
import sysconfig
import zipfile

from pathlib import Path

import pytest

_TOOLCHAIN_ID = 'win32-mingw' if sys.platform == 'win32' else 'linux-native'
_EXAMPLES     = Path(__file__).resolve().parents[2] / 'documentation' / 'examples'
_PLATFORM_TAG = re.sub(r'[-.]', '_', sysconfig.get_platform())
_CPXY         = f'cp{sys.version_info.major}{sys.version_info.minor}'

_has_c_toolchain = (
    shutil.which('cmake') is not None
    and (shutil.which('gcc') is not None or shutil.which('cc') is not None)
)
_has_python_headers = (Path(sysconfig.get_paths()['include']) / 'Python.h').exists()

_skip_without_c_toolchain = pytest.mark.skipif(
    not _has_c_toolchain,
    reason='cmake and a C compiler are required',
)
_skip_without_python_headers = pytest.mark.skipif(
    not _has_python_headers,
    reason='Python development headers are required',
)


# Copies an example into the project folder.
def _setup_example(source_path: Path, name: str):
    shutil.copytree(_EXAMPLES / name, source_path, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('obj', 'staging'))


# Builds the project, returns the wheel and its extracted content.
def _build_and_extract(rbbuild, tmp_path: Path):
    rbbuild.run(['-sbp'])
    wheels = [*(rbbuild.workdir / 'obj' / _TOOLCHAIN_ID).glob('*.whl')]
    assert len(wheels) == 1
    # Compiled code ties the package to the toolchain
    assert [*(rbbuild.workdir / 'obj' / _TOOLCHAIN_ID).glob(f'*-{_TOOLCHAIN_ID}-manifest.json')]
    extracted = tmp_path / 'installed'
    with zipfile.ZipFile(wheels[0]) as zf:
        zf.extractall(extracted)
    return wheels[0], extracted


def _run_python(code: str, cwd: Path) -> str:
    proc = subprocess.run(
        [sys.executable, '-c', code],
        cwd=cwd, capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip()


# The library is loaded with ctypes: the tag only depends on the platform.
@_skip_without_c_toolchain
def test_python_ctypes_c_example(rbbuild, source_path, tmp_path):
    _setup_example(source_path, 'python-ctypes-c')

    wheel, extracted = _build_and_extract(rbbuild, tmp_path)

    assert wheel.name.endswith(f'-py3-none-{_PLATFORM_TAG}.whl')
    wheel_txt = next(extracted.glob('*.dist-info/WHEEL')).read_text()
    assert 'Root-Is-Purelib: false' in wheel_txt
    assert [*(extracted / 'greet_ctypes').glob('*greet.*')]
    out = _run_python(
        'import greet_ctypes as g; print(g.add(2, 3), g.hello())', extracted)
    assert out == '5 Hello from C'


# The extension module depends on the Python version and the platform.
@_skip_without_c_toolchain
@_skip_without_python_headers
def test_python_cext_c_example(rbbuild, source_path, tmp_path):
    _setup_example(source_path, 'python-cext-c')

    wheel, extracted = _build_and_extract(rbbuild, tmp_path)

    assert wheel.name.endswith(f'-{_CPXY}-{_CPXY}-{_PLATFORM_TAG}.whl')
    wheel_txt = next(extracted.glob('*.dist-info/WHEEL')).read_text()
    assert 'Root-Is-Purelib: false' in wheel_txt
    assert [*(extracted / 'greet_cext').glob('_greet.*')]
    out = _run_python(
        'import greet_cext as g; print(g.add(2, 3), g.hello())', extracted)
    assert out == '5 Hello from C'
