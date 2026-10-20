#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest
import re
import json
import os
import shutil
import subprocess
import sys

from pathlib import Path

from rbbuild.docsystem.documentation_runner import DocumentationRunner
from rbbuild.docsystem.sphinx import Sphinx

_TOOLCHAIN_ID    = 'win32-mingw' if sys.platform == 'win32' else 'linux-native'
# Explicit toolchain of a dependency; without it, the default toolchain of the profile is used
_DEP_TC          = f'toolchain={_TOOLCHAIN_ID}'
_MAIN_EXE        = 'main.exe'   if sys.platform == 'win32' else 'main'

_skip_without_toolchain = pytest.mark.skipif(
    shutil.which('cmake') is None,
    reason='cmake not available in PATH',
)


def test_version(rbbuild):
    rbbuild.run(['--version'])
    output = rbbuild.read_console().strip()
    assert re.match(r'^\d+.\d+.\d+.\d+$', output)


# rbbuild with unknown parameters will yield in an error
def test_invalid_parameters(rbbuild):
    with pytest.raises(SystemExit) as e:
        rbbuild.run(['-Y'])
        assert e.value.code == 2

    with pytest.raises(SystemExit) as e:
        rbbuild.run(['--unknown-parameter'])
        assert e.value.code == 2


def test_empty_project_dir(rbbuild):
    # These commands are part of the default build pipeline and should not
    # fail with an exception or sys.exit(1)
    rbbuild.run([])
    rbbuild.run(['-s'])
    rbbuild.run(['-b'])
    rbbuild.run(['-F'])
    rbbuild.run(['-I'])
    # Publish expects obj/<tcid>/manifest.json to be present
    with pytest.raises(FileNotFoundError):
        rbbuild.run(['--publish', 'sample-development'])
    rbbuild.run(['-T'])
    rbbuild.run(['-D'])
    rbbuild.run(['--sca'])

    # None of the above commands should have created any files, e.g., obj or staging folders
    assert len([*rbbuild.workdir.iterdir()]) == 0

    # Package will not create manifest and SBOM
    rbbuild.run(['-p'])
    assert len([*rbbuild.workdir.iterdir()]) == 0


def test_documentation_action_dispatches_builder(rbbuild, monkeypatch):
    called = {'count': 0}

    (rbbuild.workdir / 'pyproject.toml').write_text(
        '[tool.rbbuild]\n'
        'documentation_tools = ["pandoc"]\n'
    )

    def _mock_build_documentation(self, mypkg):
        called['count'] += 1

    monkeypatch.setattr(DocumentationRunner, 'build_documentation', _mock_build_documentation)

    rbbuild.run(['-sD'])

    assert called['count'] == 1


def test_project_section_is_passed_to_sphinx(rbbuild, monkeypatch):
    """[project] authors must reach Sphinx — regression for self.config.project vs self.project."""
    received = {}

    (rbbuild.workdir / 'pyproject.toml').write_text(
        '[project]\n'
        'name = "oss_policy"\n'
        'authors = [{name = "Alice"}]\n'
        '\n'
        '[tool.rbbuild]\n'
        'documentation-tools = ["sphinx"]\n'
        '\n'
        '[tool.rbbuild.sphinx.oss-policy]\n'
        'sourcedir = "source"\n'
        'title = "OSS Policy"\n'
    )

    original_init = Sphinx.__init__

    def _capture_init(self, sphinx_config, project_config, paths, issueman):
        received['project_config'] = project_config
        original_init(self, sphinx_config, project_config, paths, issueman)

    monkeypatch.setattr(Sphinx, '__init__', _capture_init)
    monkeypatch.setattr(DocumentationRunner, 'build_documentation', lambda self, mypkg: None)

    rbbuild.run(['-sD'])

    assert received.get('project_config') is not None, \
        '[project] was not passed to Sphinx (self.config.project bug)'
    assert received['project_config'].get('authors') == [{'name': 'Alice'}]


def test_clean_removes_documentation_dir(rbbuild):
    # Pre-create a documentation directory (obj/documentation)
    doc_dir = rbbuild.workdir / 'obj' / 'documentation'
    doc_dir.mkdir(parents=True)
    assert doc_dir.exists()

    rbbuild.run(['-c'])

    assert not doc_dir.exists()


def test_clean_force_removes_all_toolchains(rbbuild):
    for root in ['obj', 'staging']:
        for tcid in [_TOOLCHAIN_ID, 'other-tc']:
            folder = rbbuild.workdir / root / tcid
            folder.mkdir(parents=True)
            (folder / 'file.txt').write_text('x')
    (rbbuild.workdir / 'staging' / 'staging-indexdb.json').write_text('{}')

    rbbuild.run(['-cf'])

    assert not (rbbuild.workdir / 'obj').exists()
    assert not (rbbuild.workdir / 'staging').exists()


def test_clean_force_with_toolchain_keeps_other_toolchains(rbbuild):
    for root in ['obj', 'staging']:
        for tcid in [_TOOLCHAIN_ID, 'other-tc']:
            folder = rbbuild.workdir / root / tcid
            folder.mkdir(parents=True)
            (folder / 'file.txt').write_text('x')
    (rbbuild.workdir / 'staging' / 'staging-indexdb.json').write_text('{}')

    rbbuild.run(['-cf', '-t', _TOOLCHAIN_ID])

    assert not (rbbuild.workdir / 'obj' / _TOOLCHAIN_ID).exists()
    assert not (rbbuild.workdir / 'staging' / _TOOLCHAIN_ID).exists()
    assert (rbbuild.workdir / 'obj' / 'other-tc' / 'file.txt').exists()
    assert (rbbuild.workdir / 'staging' / 'other-tc' / 'file.txt').exists()


def test_fetch_not_found(rbbuild):
    deps_json_path = rbbuild.workdir / 'deps.json'
    deps_json = {
        '/': {
            'deps': ['unknown_package']
        }
    }
    with open(deps_json_path, 'w') as jfd:
        json.dump(deps_json, jfd, indent=4)
    with pytest.raises(Exception):
        rbbuild.run(['-F'])


def test_install_not_found(rbbuild):
    deps_json_path = rbbuild.workdir / 'deps.json'
    deps_json = {
        '/': {
            'deps': ['unknown_package']
        }
    }
    with open(deps_json_path, 'w') as jfd:
        json.dump(deps_json, jfd, indent=4)
    with pytest.raises(Exception):
        rbbuild.run(['-I'])


def _write_deps(rbbuild, deps):
    (rbbuild.workdir / 'deps.json').write_text(json.dumps(deps, indent=4))


def _staging(rbbuild):
    return rbbuild.workdir / 'staging/none-any'


def _read_indexdb(rbbuild):
    with open(rbbuild.workdir / 'staging/staging-indexdb.json', 'r') as jfd:
        return json.load(jfd)


def test_rbbuild_fetch_no_freeze(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': [f'sample-development:sample_tools-2.0.0.4 {_DEP_TC}']}})
    rbbuild.run(['-F'])
    # Check that only deps.json exists (no frozen_deps.json is generated in obj)
    assert len([*rbbuild.workdir.iterdir()]) == 1


@pytest.mark.skip('reason=Freeze mechanism is currently not implemented')
def test_rbbuild_fetch_with_freeze(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': ['sample_tools']}})

    rbbuild.run(['-F'])
    rbbuild.read_console()
    assert len([*rbbuild.workdir.iterdir()]) == 2
    assert (rbbuild.workdir / 'deps.json').exists()
    assert (rbbuild.workdir / 'obj/generated/deps.json').exists()


def test_rbbuild_fi(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': [f'sample-development:sample_tools components=alpha,beta {_DEP_TC}']}})

    rbbuild.run(['-FI'])
    # Expected content:
    # * deps.json
    # * staging/staging-indexdb.json
    # * staging/<tcid>/alpha/alpha.toml
    # * staging/<tcid>/beta/beta.toml
    assert len([*rbbuild.workdir.iterdir()]) == 2
    assert (rbbuild.workdir / 'staging/staging-indexdb.json').exists()
    assert (_staging(rbbuild) / 'alpha/alpha.toml').exists()
    assert (_staging(rbbuild) / 'beta/beta.toml').exists()
    assert not (_staging(rbbuild) / 'gamma/gamma.toml').exists()


# The latest version (libbar-3.0.0.3) exists, but not for the selected toolchain.
# It is expected that an earlier package version is returned that has a build
# for this toolchain.
def test_rbbuild_fi_missing_toolchain_for_latest_version(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': [f'libbar {_DEP_TC}']}})

    rbbuild.run(['-FI'])
    sindex = _read_indexdb(rbbuild)
    assert sindex[f'libbar@{_TOOLCHAIN_ID}']['package']['version_string'] == '2.0.0.2'
    assert sindex[f'libbar@{_TOOLCHAIN_ID}']['package']['toolchain'] == _TOOLCHAIN_ID
    assert sindex[f'libfoo@{_TOOLCHAIN_ID}']['package']['version_string'] == '2.0.0.3'


# The project has no toolchain (none-any), the dependency does not name one:
# the default toolchain of the profile is used.
def test_rbbuild_fi_dependency_without_toolchain(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': ['libbar']}})

    rbbuild.run(['-FI'])
    sindex = _read_indexdb(rbbuild)
    assert sindex[f'libbar@{_TOOLCHAIN_ID}']['package']['version_string'] == '2.0.0.2'
    assert sindex[f'libbar@{_TOOLCHAIN_ID}']['package']['toolchain'] == _TOOLCHAIN_ID
    assert (rbbuild.workdir / 'staging/none-any').is_dir()


def test_rbbuild_fi_profile(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': [f'libfoo {_DEP_TC}']}})

    rbbuild.run(['-FI'])
    # Expected content:
    # * deps.json
    # * staging/staging-indexdb.json
    # * staging/<tcid>/usr/lib/libfoo.so (from prod)
    # * staging/<tcid>/usr/include/foo.h (from dev)
    # The other components (licenses and debug) do not provide relevant files
    assert len([*rbbuild.workdir.iterdir()]) == 2
    assert (rbbuild.workdir / 'staging/staging-indexdb.json').exists()
    assert (_staging(rbbuild) / 'usr/lib/libfoo.so').exists()
    assert (_staging(rbbuild) / 'usr/include/foo.h').exists()


def test_rbbuild_fi_transient(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': [f'libbar-1.0.0.1 {_DEP_TC}']}})

    rbbuild.run(['-FI'])
    # Expected content:
    # * deps.json
    # * staging
    assert len([*rbbuild.workdir.iterdir()]) == 2
    assert (rbbuild.workdir / 'staging/staging-indexdb.json').exists()
    # from libfoo
    assert (_staging(rbbuild) / 'usr/lib/libfoo_v1.so').exists()
    assert (_staging(rbbuild) / 'usr/include/foo_v1.h').exists()
    # from libbar
    assert (_staging(rbbuild) / 'usr/lib/libbar.so').exists()
    assert (_staging(rbbuild) / 'licenses/libbar-license.txt').exists()
    assert (_staging(rbbuild) / 'usr/include/bar.h').exists()
    # from testtool --> build_only and not in deps
    assert not (_staging(rbbuild) / 'usr/bin/testtool').exists()
    assert not (_staging(rbbuild) / 'usr/include/testtool.h').exists()
    assert not (_staging(rbbuild) / 'usr/include/testlib.h').exists()


def test_rbbuild_fi_transient_with_build_only(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': [f'libbar-1.0.0.1 {_DEP_TC}', f'testtool build_only {_DEP_TC}']}})

    rbbuild.run(['-FI'])
    assert len([*rbbuild.workdir.iterdir()]) == 2
    assert (rbbuild.workdir / 'staging/staging-indexdb.json').exists()
    # from libfoo
    assert (_staging(rbbuild) / 'usr/lib/libfoo_v1.so').exists()
    # from libbar
    assert (_staging(rbbuild) / 'usr/lib/libbar.so').exists()
    # from testtool --> should be installed because it is in deps.json
    assert (_staging(rbbuild) / 'usr/bin/testtool').exists()
    assert (_staging(rbbuild) / 'usr/include/testtool.h').exists()


def test_rbbuild_fi_downgrade(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': [f'libfoo {_DEP_TC}']}})

    rbbuild.run(['-FI'])
    assert (_staging(rbbuild) / 'usr/lib/libfoo.so').exists()
    assert (_staging(rbbuild) / 'usr/include/foo.h').exists()
    sindex = _read_indexdb(rbbuild)
    assert sindex[f'libfoo@{_TOOLCHAIN_ID}']['package']['version_string'] == '2.0.0.3'

    # repeat, but with libfoo-1.0.0.1
    _write_deps(rbbuild, {'/': {'deps': [f'libfoo-1.0.0.1 {_DEP_TC}']}})

    rbbuild.run(['-FI'])

    sindex = _read_indexdb(rbbuild)
    assert sindex[f'libfoo@{_TOOLCHAIN_ID}']['package']['version_string'] == '1.0.0.1'

    # removed from prod 2.x
    assert not (_staging(rbbuild) / 'usr/lib/libfoo.so').exists()
    # removed from dev 2.x
    assert not (_staging(rbbuild) / 'usr/include/foo.h').exists()
    # added to prod 1.x
    assert (_staging(rbbuild) / 'usr/lib/libfoo_v1.so').exists()
    # added to dev 1.x
    assert (_staging(rbbuild) / 'usr/include/foo_v1.h').exists()


def test_rbbuild_fi_upgrade(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': [f'libfoo-1.0.0.1 {_DEP_TC}']}})

    rbbuild.run(['-FI'])

    assert (_staging(rbbuild) / 'usr/lib/libfoo_v1.so').exists()
    assert (_staging(rbbuild) / 'usr/include/foo_v1.h').exists()

    # repeat, but with the latest version (libfoo-2.0.0.3)
    _write_deps(rbbuild, {'/': {'deps': [f'libfoo {_DEP_TC}']}})

    rbbuild.run(['-FI'])

    assert (_staging(rbbuild) / 'usr/lib/libfoo.so').exists()
    # removed from prod
    assert not (_staging(rbbuild) / 'usr/lib/libfoo_v1.so').exists()
    # removed from dev
    assert not (_staging(rbbuild) / 'usr/include/foo_v1.h').exists()
    # added to dev
    assert (_staging(rbbuild) / 'usr/include/foo.h').exists()


def test_rbbuild_fi_prod_only(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': [f'libfoo components=prod {_DEP_TC}']}})

    rbbuild.run(['-FI'])
    # Expected content:
    # * deps.json
    # * staging/staging-indexdb.json
    # * staging/<tcid>/usr/lib/libfoo.so (from prod)
    assert len([*rbbuild.workdir.iterdir()]) == 2
    assert (rbbuild.workdir / 'staging/staging-indexdb.json').exists()
    assert (_staging(rbbuild) / 'usr/lib/libfoo.so').exists()
    assert not (_staging(rbbuild) / 'usr/include/foo.h').exists()


def test_rbbuild_fi_prod_purl_syntax(rbbuild):
    _write_deps(rbbuild, {'/': {'deps': [f'pkg:rbbuild/libfoo?components=prod&toolchain={_TOOLCHAIN_ID}']}})

    rbbuild.run(['-FI'])
    assert len([*rbbuild.workdir.iterdir()]) == 2
    assert (_staging(rbbuild) / 'usr/lib/libfoo.so').exists()
    assert not (_staging(rbbuild) / 'usr/include/foo.h').exists()


def test_rbbuild_fi_different_ns_path(rbbuild):
    _write_deps(rbbuild, {
        '/': {'deps': [f'libfoo components=prod {_DEP_TC}']},
        '/dev_path': {'deps': [f'libfoo components=dev {_DEP_TC}']},
    })

    rbbuild.run(['-FI'])
    # Expected content:
    # * deps.json
    # * staging/staging-indexdb.json
    # * staging/<tcid>/usr/lib/libfoo.so (from prod)
    # * staging/<tcid>/dev_path/usr/include/foo.h (from dev)
    assert len([*rbbuild.workdir.iterdir()]) == 2
    assert (rbbuild.workdir / 'staging/staging-indexdb.json').exists()
    assert (_staging(rbbuild) / 'usr/lib/libfoo.so').exists()
    assert (_staging(rbbuild) / 'dev_path/usr/include/foo.h').exists()


def test_rbbuild_fi_deps_syntax_error(rbbuild):
    _write_deps(rbbuild, {'/': [{'deps': ['libfoo components=prod']}]})

    # In this case, we expect an AttributeError. However, for now, this is an implementation
    # detail from CLI point of view
    with pytest.raises(Exception):
        rbbuild.run(['-FI'])


cmakelists = (
'''
cmake_minimum_required(VERSION 3.17)
project($ENV{RBB_PACKAGE_NAME})

include(RBBuild)

add_executable(main main.cc)

install( TARGETS main
         COMPONENT component )

RBPackage()
''')


main_source = (
'''
#include <iostream>

int main() {
     std::cout << "Hello rbbuild test\\n";
     return 0;
}
''')


@_skip_without_toolchain
def test_rbbuild_setup_basic(rbbuild):
    cmakelists_path = rbbuild.workdir / 'CMakeLists.txt'
    with open(cmakelists_path, 'w') as fd:
        fd.write(cmakelists)

    main_source_path = rbbuild.workdir / 'main.cc'
    with open(main_source_path, 'w') as fd:
        fd.write(main_source)

    rbbuild.run(['-s'])
    # CMake and ninja build files
    assert (rbbuild.workdir / f'obj/{_TOOLCHAIN_ID}/build.ninja').exists()
    assert (rbbuild.workdir / f'obj/{_TOOLCHAIN_ID}/generated/cmake.properties').exists()
    # Version info
    assert (rbbuild.workdir / f'obj/{_TOOLCHAIN_ID}/version/project_version.c').exists()
    assert (rbbuild.workdir / f'obj/{_TOOLCHAIN_ID}/version/project_version.h').exists()
    assert (rbbuild.workdir / f'obj/{_TOOLCHAIN_ID}/version/rbversioninfo.h').exists()
    # Manifest and SBOM are NOT generated (needs -p)
    obj_path = rbbuild.workdir / f'obj/{_TOOLCHAIN_ID}'
    assert not [*obj_path.glob('*-manifest.json')]
    assert not [*obj_path.glob('*-sbom.cdx.json')]


@_skip_without_toolchain
def test_rbbuild_sb_and_p_basic(rbbuild):
    cmakelists_path = rbbuild.workdir / 'CMakeLists.txt'
    with open(cmakelists_path, 'w') as fd:
        fd.write(cmakelists)

    main_source_path = rbbuild.workdir / 'main.cc'
    with open(main_source_path, 'w') as fd:
        fd.write(main_source)

    rbbuild.run(['-sb'])
    main = rbbuild.workdir / f'obj/{_TOOLCHAIN_ID}/{_MAIN_EXE}'
    assert main.exists()
    proc = subprocess.run(main, capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout == 'Hello rbbuild test\n'

    rbbuild.run(['-p'])
    obj_path = rbbuild.workdir / f'obj/{_TOOLCHAIN_ID}'
    assert [*obj_path.glob(f'project-0.0.*.0-{_TOOLCHAIN_ID}-component.tar.xz')][0].exists()
    # Manifest and SBOM
    assert (obj_path / 'manifest.json').exists()
    if sys.platform != 'win32':
        assert (obj_path / 'manifest.json').is_symlink()
    assert [*obj_path.glob(f'project-0.0.*.0-{_TOOLCHAIN_ID}-manifest.json')][0].exists()
    assert [*obj_path.glob(f'project-0.0.*.0-{_TOOLCHAIN_ID}-sbom.cdx.json')][0].exists()


# The 'test' profile ships a ruff.toml that selects F rules (e.g., unused imports)
def _write_python_project(rbbuild, source, ruff_section=''):
    (rbbuild.workdir / 'pyproject.toml').write_text(
        '[project]\nname = "sample"\nversion = "0.0"\nrequires-python = ">=3.14"\n' + ruff_section)
    (rbbuild.workdir / 'sample.py').write_text(source)


def _generated_ruff_toml(rbbuild):
    return rbbuild.workdir / 'obj/none-any/ruff.toml'


def test_rbbuild_sca_uses_profile_config_as_is(rbbuild):
    _write_python_project(rbbuild, 'import os\n')

    with pytest.raises(RuntimeError):
        rbbuild.run(['-P', 'test', '--sca'])

    assert not _generated_ruff_toml(rbbuild).exists()


def test_rbbuild_sca_without_findings(rbbuild):
    _write_python_project(rbbuild, 'import os\n\nos.getcwd()\n')

    rbbuild.run(['-P', 'test', '--sca'])


def test_rbbuild_sca_project_config_overrides_profile(rbbuild):
    _write_python_project(rbbuild, 'import os\n', '\n[tool.ruff.lint]\nignore = ["F401"]\n')

    rbbuild.run(['-P', 'test', '--sca'])

    assert _generated_ruff_toml(rbbuild).exists()


def test_rbbuild_sca_project_config_extends_profile(rbbuild):
    _write_python_project(rbbuild, f'# {"a" * 120}\n', '\n[tool.ruff.lint]\nextend-select = ["E501"]\n')

    # E501 is not selected by the profile
    with pytest.raises(RuntimeError):
        rbbuild.run(['-P', 'test', '--sca'])

    assert _generated_ruff_toml(rbbuild).exists()


def test_rbbuild_sca_project_extend_ignores_profile(rbbuild):
    (rbbuild.workdir / 'base.toml').write_text('[lint]\nselect = ["E4"]\n')
    _write_python_project(rbbuild, 'import os\n', '\n[tool.ruff]\nextend = "base.toml"\n')

    rbbuild.run(['-P', 'test', '--sca'])

    assert not _generated_ruff_toml(rbbuild).exists()


def test_rbbuild_sca_tools_can_be_disabled(rbbuild):
    _write_python_project(rbbuild, 'import os\n', '\n[tool.rbbuild]\nsca-tools = []\n')

    rbbuild.run(['-P', 'test', '--sca'])


# Actions of the project override the default actions
def test_rbbuild_project_actions_are_used(rbbuild):
    _write_python_project(rbbuild, 'import os\n', '\n[tool.rbbuild]\nactions = ["static_code_analysis"]\n')

    with pytest.raises(RuntimeError):
        rbbuild.run(['-P', 'test'])


# [settings] toolchain of rbbuild 5 does not select the toolchain of a Python project
def test_rbbuild_legacy_toolchain_setting_is_ignored(rbbuild):
    config_file = rbbuild.user_home / '.config/rbbuild/rbbuild.toml'
    config_file.write_text(config_file.read_text().replace(
        "profile = 'test'", "profile = 'test'\ntoolchain = 'linux-native'\ntoolchains = 'linux-native'"))
    _write_python_project(rbbuild, 'import os\n')

    rbbuild.run(['-s'])

    assert (rbbuild.workdir / 'obj/none-any').is_dir()
    assert not (rbbuild.workdir / 'obj/linux-native').exists()


def _write_pytest_project(rbbuild, rbbuild_toml, test_source):
    (rbbuild.workdir / 'rbbuild.toml').write_text(rbbuild_toml)
    (rbbuild.workdir / 'test_sample.py').write_text(test_source)


def _use_pytest_of_venv(monkeypatch):
    monkeypatch.setenv('PATH', f'{Path(sys.executable).parent}{os.pathsep}{os.environ["PATH"]}')


def test_rbbuild_test_tools_pytest_in_project_without_pypa(rbbuild, monkeypatch):
    _use_pytest_of_venv(monkeypatch)
    _write_pytest_project(rbbuild, '[rbbuild]\ntest-tools = ["pytest"]\n', 'def test_ok():\n    assert True\n')

    rbbuild.run(['-T'])

    assert (rbbuild.workdir / 'obj/none-any/Testing/pytest/Test.xml').exists()


def test_rbbuild_test_tools_pytest_failure_fails(rbbuild, monkeypatch):
    _use_pytest_of_venv(monkeypatch)
    _write_pytest_project(rbbuild, '[rbbuild]\ntest-tools = ["pytest"]\n', 'def test_fail():\n    assert False\n')

    with pytest.raises(RuntimeError):
        rbbuild.run(['-T'])


# pytest only runs if it is configured (or if pypa is active)
def test_rbbuild_pytest_does_not_run_if_not_configured(rbbuild):
    _write_pytest_project(rbbuild, '[project]\nname = "sample"\n', 'def test_fail():\n    assert False\n')

    rbbuild.run(['-T'])

    assert not (rbbuild.workdir / 'obj').exists()

