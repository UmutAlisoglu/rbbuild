# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock

import pytest

from rbbuild.buildsystem.rbbuild_class import RBBuild
from rbbuild.package.package import Package
from rbbuild.resolver.resolver import ResolveResult


def _make_rbbuild(profile_supplier=None):
    rbbuild = RBBuild.__new__(RBBuild)
    rbbuild.settings = MagicMock(profile_name='myprofile', profile_version='1.2.3')
    rbbuild.profile_supplier = profile_supplier
    return rbbuild


def test_install_deps_installs_build_only_components_of_top_level_only(tmp_path):
    top = Package(name='a', version='1.0')
    nested = Package(name='b', version='1.0')
    rbbuild = RBBuild.__new__(RBBuild)
    rbbuild.settings = MagicMock(skipped_components=[])
    rbbuild.dependencies_config = []
    rbbuild.__dict__['dependencies'] = {'': {'a': top}}
    rbbuild.resolver = MagicMock()
    rbbuild.resolver.run.return_value = ResolveResult(
        packages={'a': top, 'b': nested}, problems=[], top_level=('a',))
    staging = MagicMock()

    rbbuild.install_deps(Package(), staging, tmp_path, fi_hint=False)

    flags = {
        call.args[0].name: call.kwargs['install_build_only']
        for call in staging.install_package.call_args_list
    }
    assert flags == {'a': True, 'b': False}


def test_tools_rbbuild_entry_has_fixed_vendor():
    tool = _make_rbbuild({'name': 'Example Corp'})._tools()[0]
    assert tool.name == 'rbbuild'
    assert tool.vendor == 'Robert Bosch GmbH'
    assert [r.url for r in tool.external_references] == ['https://github.com/boschglobal/rbbuild']


def test_tools_profile_vendor_is_profile_supplier_name():
    tool = _make_rbbuild({'name': 'Example Corp'})._tools()[1]
    assert tool.name == 'myprofile'
    assert tool.version == '1.2.3'
    assert tool.vendor == 'Example Corp'
    assert tool.external_references is None


def test_tools_without_profile_supplier_name_raises():
    with pytest.raises(RuntimeError, match='profile.supplier'):
        _make_rbbuild()._tools()
    with pytest.raises(RuntimeError, match='profile.supplier'):
        _make_rbbuild({'email': 'info@example.com'})._tools()
