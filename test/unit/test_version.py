# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from packaging.version import Version

from rbbuild.version import __version__, RBBuildVersion
from rbbuild.package.metadata import Metadata

# Unit tests for rbbuild.version.


# ---------------------------------------------------------------------------
# __version__
# ---------------------------------------------------------------------------

# __version__ is a non-empty string in the form major.minor.revision.build.
def test_version_string_format():
    assert isinstance(__version__, str)
    assert len(__version__) > 0
    parts = __version__.split('.')
    assert len(parts) == 4
    assert all(part.isdigit() for part in parts)


# ---------------------------------------------------------------------------
# RBBuildVersion
# ---------------------------------------------------------------------------

# RBBuildVersion is a Metadata subclass.
def test_rbbuild_version_is_metadata():
    assert isinstance(RBBuildVersion(), Metadata)


# version property returns a packaging.version.Version with four numeric parts.
def test_rbbuild_version_has_four_parts():
    assert isinstance(RBBuildVersion().version, Version)
    assert len(RBBuildVersion().version.release) == 4


# root_path contains pyproject.toml — i.e. it points to the package root.
def test_rbbuild_version_root_path():
    assert (RBBuildVersion().root_path / 'pyproject.toml').exists()


# BUILD_NUMBER env var is picked up as the build component.
def test_rbbuild_version_build_number(monkeypatch):
    monkeypatch.setenv('BUILD_NUMBER', '99')
    assert RBBuildVersion().build == 99


# GITHUB_RUN_NUMBER is used as a fallback when BUILD_NUMBER (Jenkins) is
# not set.
def test_rbbuild_version_github_run_number(monkeypatch):
    monkeypatch.setenv('GITHUB_RUN_NUMBER', '55')
    assert RBBuildVersion().build == 55


# major and minor are consistent with the assembled version string.
def test_rbbuild_version_major_minor_match_version_string():
    v = RBBuildVersion()
    parts = str(v.version).split('.')
    assert v.major == int(parts[0])
    assert v.minor == int(parts[1])

