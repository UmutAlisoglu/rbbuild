# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import os
import sys

from unittest.mock import MagicMock

from rbbuild.__main__ import RBBuildMain
from rbbuild.core.toolchain import Toolchain
from rbbuild.package.metadata import Metadata
from rbbuild.package.package import Package
from rbbuild.package.sbom import SBOM, SBOMFormat

# Unit tests for packages that do not record a toolchain (none-any) and the
# resulting names.

_TOOLCHAINS = {
    'linux-native': {'platform': 'linux', 'tcid': 'native', 'cmake_file': None},
}


def _make_mypkg(toolchain):
    metadata = MagicMock()
    metadata.name = 'mypkg'
    metadata.version = '1.0.0.0'
    return RBBuildMain().make_mypkg(
        paths=MagicMock(),
        channel=MagicMock(development=False),
        toolchain=toolchain,
        metadata=metadata,
        repoman=MagicMock(),
        ciman=MagicMock(),
        ci_key=None,
        supplier=None,
    )


# ---------------------------------------------------------------------------
# Package toolchain follows the selected toolchain
# ---------------------------------------------------------------------------

def test_package_has_the_selected_toolchain():
    toolchain = Toolchain(tcid='linux-native', toolchains_config=_TOOLCHAINS)
    assert _make_mypkg(toolchain).toolchain is toolchain


def test_package_has_no_toolchain_for_none_any():
    toolchain = Toolchain(tcid='none-any', toolchains_config=_TOOLCHAINS)
    assert _make_mypkg(toolchain).toolchain is None


def test_toolchain_is_any():
    assert Toolchain(tcid=None, toolchains_config={}).is_any is True
    assert Toolchain(tcid='linux-native', toolchains_config=_TOOLCHAINS).is_any is False


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

def test_sbom_filename_without_toolchain():
    pkg = Package(name='pure', version='1.0.0.0')
    assert SBOM(SBOMFormat.AUTO).make_filename(pkg) == 'pure-1.0.0.0-sbom.cdx.json'


def test_sbom_filename_with_toolchain():
    pkg = Package(name='lib', version='1.0.0.0')
    pkg.toolchain = 'linux-native'
    assert SBOM(SBOMFormat.AUTO).make_filename(pkg) == 'lib-1.0.0.0-linux-native-sbom.cdx.json'


# ---------------------------------------------------------------------------
# Child process environment
# ---------------------------------------------------------------------------

def _environ(monkeypatch, prefix, base_prefix, toolchain=None):
    monkeypatch.setattr(sys, 'prefix', prefix)
    monkeypatch.setattr(sys, 'base_prefix', base_prefix)
    metadata = MagicMock()
    metadata.paths = MagicMock()
    metadata.git_repo = None
    metadata.git_hash = None
    metadata.toolchain = toolchain or Toolchain(tcid=None, toolchains_config={})
    return Metadata.environ.fget(metadata)


def _python_toolchain(**python):
    config = {'linux-pypy310': {
        'platform': 'linux', 'tcid': 'pypy310', 'cmake_file': None, **python}}
    return Toolchain(tcid='linux-pypy310', toolchains_config=config)


# CMake's FindPython only selects the venv interpreter if VIRTUAL_ENV is set.
def test_environ_exports_virtual_env_in_venv(monkeypatch):
    environ = _environ(monkeypatch, '/venv', '/usr')
    assert environ['VIRTUAL_ENV'] == '/venv'


def test_environ_without_venv_keeps_virtual_env(monkeypatch):
    monkeypatch.delenv('VIRTUAL_ENV', raising=False)
    environ = _environ(monkeypatch, '/usr', '/usr')
    assert 'VIRTUAL_ENV' not in environ


# The Python of a toolchain comes first in PATH; the venv of rbbuild is not exported.
def test_environ_python_toolchain_executable_first_in_path(monkeypatch, tmp_path):
    python = tmp_path / ('pypy.exe' if sys.platform == 'win32' else 'pypy')
    python.write_text('')
    python.chmod(0o755)
    toolchain = _python_toolchain(python_executable=str(python))

    environ = _environ(monkeypatch, '/venv', '/usr', toolchain)

    assert environ['PATH'].split(os.pathsep)[0] == str(tmp_path)
    assert environ.get('VIRTUAL_ENV') != '/venv'


def test_environ_python_toolchain_environment(monkeypatch):
    monkeypatch.setenv('PYTHONPATH', '/existing')
    toolchain = _python_toolchain(python_environment={'PYTHONPATH': '/opt/lib'})

    environ = _environ(monkeypatch, '/usr', '/usr', toolchain)

    assert environ['PYTHONPATH'] == f'/opt/lib{os.pathsep}/existing'
