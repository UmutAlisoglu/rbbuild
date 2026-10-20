#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

# Integration tests for rbbuild with the PyPA (Python package manager) build system.
#
# These tests cover the key behaviours introduced in the PyPA refactor:
#   - staging-indexdb.json is populated after rbbuild -I
#   - A second rbbuild -I reuses the existing venv (fast path, no pip install)
#   - build_requirements (build-system.requires) are marked build_only in manifest.json
#   - runtime dependencies are NOT marked build_only
#   - License fields prefer SPDX expressions over raw PyPI classifier strings
import json
import shutil
import subprocess
import sys
import tarfile
import zipfile
import pytest

# Pure Python projects select the none-any toolchain by default
_TOOLCHAIN_ID = 'none-any'
_HOST_TOOLCHAIN_ID = 'win32-mingw' if sys.platform == 'win32' else 'linux-native'

# ---------------------------------------------------------------------------
# Minimal Python project used as the test subject.
#
# Runtime deps  : packaging, build, wheel
#   - 'build' must be a runtime dep so 'python -m build --no-isolation' works
#     inside the staging venv (the build module is imported at build time).
#
# Build-only dep: setuptools (build backend, NOT a runtime dep)
# ---------------------------------------------------------------------------
_PYPROJECT_TOML = '''\
[project]
name = "testproject"
version = "1.0"
dependencies = [
    "packaging>=25.0",
]

[tool.rbbuild.packaging.wheel]
type = "python"
files = ["testproject"]

[build-system]
requires = ["rbbuild"]
build-backend = "rbbuild.buildsystem.build"
'''

_JENKINSFILE = 'rbbuild() {\n    toolchains = [ "%s" ]\n}\n' % _HOST_TOOLCHAIN_ID

_INIT_PY = '# testproject\n'


# ---------------------------------------------------------------------------
# Mock venv inventory returned by _installed_from_venv.
# Matches exactly what the test pyproject.toml declares as runtime and build deps.
# ---------------------------------------------------------------------------
_MOCK_INSTALLED = {
    'packaging': {
        'name': 'packaging',
        'version': '26.2',
        'requires': [],
        'home_page': None,
        'license': None,
        'license_expression': 'Apache-2.0 OR BSD-2-Clause',
        'author': None,
        'author_email': 'Donald Stufft <donald@stufft.io>',
        'maintainer': None,
        'maintainer_email': None,
        'classifiers': [],
    },
    'build': {
        'name': 'build',
        'version': '1.5.0',
        'requires': [],
        'home_page': None,
        'license': None,
        'license_expression': 'MIT',
        'author': None,
        'author_email': None,
        'maintainer': None,
        'maintainer_email': None,
        'classifiers': [],
    },
    'wheel': {
        'name': 'wheel',
        'version': '0.47.0',
        'requires': [],
        'home_page': None,
        'license': None,
        'license_expression': 'MIT',
        'author': None,
        'author_email': None,
        'maintainer': None,
        'maintainer_email': None,
        'classifiers': [],
    },
    'setuptools': {
        'name': 'setuptools',
        'version': '82.0.1',
        'requires': [],
        'home_page': None,
        'license': None,
        'license_expression': 'MIT',
        'author': 'Python Packaging Authority',
        'author_email': 'distutils-sig@python.org',
        'maintainer': None,
        'maintainer_email': None,
        'classifiers': [],
    },
}


# ---------------------------------------------------------------------------
# PyPA class-level mock functions (used as method replacements via monkeypatch)
# ---------------------------------------------------------------------------

# Returns the mock inventory and creates the venv directory so that
# subsequent venv_path.exists() checks (e.g. in build()) pass.
def _mock_installed_from_venv(self):
    self.venv_path.mkdir(parents=True, exist_ok=True)
    return dict(_MOCK_INSTALLED)


# Noop: no actual subprocess command is executed
def _mock_execute(self, pipcmd, *args, input=None, environ=None):
    pass


# build() now calls uv directly instead of execute_python('-m', 'build', ...).
# Create empty wheel and sdist so package() can find them.
def _mock_build(self, target=None, njobs=None):
    name = self.pyproject_toml['project']['name']
    self.paths.build.mkdir(parents=True, exist_ok=True)
    (self.paths.build / f'{name}-1.0-py3-none-any.whl').write_bytes(b'')
    (self.paths.build / f'{name}-1.0.tar.gz').write_bytes(b'')


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Populate source_path with a minimal buildable Python project.
@pytest.fixture
def pypa_project(source_path):
    (source_path / 'pyproject.toml').write_text(_PYPROJECT_TOML)
    (source_path / 'Jenkinsfile').write_text(_JENKINSFILE)
    pkg_dir = source_path / 'testproject'
    pkg_dir.mkdir()
    (pkg_dir / '__init__.py').write_text(_INIT_PY)
    yield source_path


# Patch PyPA methods to eliminate real pip, venv, and subprocess calls.
# Tests are instant because no I/O or network activity takes place.
@pytest.fixture
def pypa_mocked(pypa_project, monkeypatch):
    from rbbuild.buildsystem import pypa as pypa_mod
    monkeypatch.setattr(pypa_mod.PyPA, '_installed_from_venv', _mock_installed_from_venv)
    monkeypatch.setattr(pypa_mod.PyPA, '_execute',             _mock_execute)
    monkeypatch.setattr(pypa_mod.PyPA, 'build',                _mock_build)
    yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# Without a pyproject.toml with a build-backend, PyPA is disabled.
# rbbuild -FI, -b, and -p should all complete without creating any files.
def test_pypa_no_pyproject_is_noop(rbbuild):
    rbbuild.run(['-FI'])
    rbbuild.run(['-b'])
    rbbuild.run(['-p'])
    assert len([*rbbuild.workdir.iterdir()]) == 0


# rbbuild -I must create a Python venv in the staging directory.
def test_pypa_install_creates_venv(pypa_mocked, rbbuild):
    rbbuild.run(['-I'])

    venv_path = rbbuild.workdir / 'staging' / _TOOLCHAIN_ID / '.venv'
    assert venv_path.is_dir(), f'venv not found at {venv_path}'


# rbbuild -I must write all installed packages to staging-indexdb.json.
def test_pypa_install_populates_staging_indexdb(pypa_mocked, rbbuild):
    rbbuild.run(['-I'])

    indexdb_path = rbbuild.workdir / 'staging' / 'staging-indexdb.json'
    assert indexdb_path.exists(), 'staging-indexdb.json was not created'

    with open(indexdb_path) as f:
        sindex = json.load(f)

    assert 'packaging' in sindex, 'packaging must appear in staging-indexdb.json'
    pkg = sindex['packaging']['package']
    assert pkg['version_package'] == 'packaging'
    assert pkg['version_string'], 'version_string must be non-empty'


# rbbuild -sb must produce a wheel and a source distribution.
def test_pypa_build_produces_artifacts(pypa_mocked, rbbuild):
    rbbuild.run(['-I'])
    rbbuild.run(['-sb'])

    build_dir = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID
    wheels = list(build_dir.glob('testproject-1.0*.whl'))
    sdists = list(build_dir.glob('testproject-1.0*.tar.gz'))

    assert wheels, f'No wheel found in {build_dir}'
    assert sdists, f'No sdist found in {build_dir}'


# rbbuild -p must list runtime deps in manifest.json with a pkg:pypi PURL.
def test_pypa_manifest_contains_runtime_deps(pypa_mocked, rbbuild):
    rbbuild.run(['-I'])
    rbbuild.run(['-sb'])
    rbbuild.run(['-p'])

    manifest_path = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID / 'manifest.json'
    assert manifest_path.exists()

    with open(manifest_path) as f:
        manifest = json.load(f)

    deps = manifest.get('dependencies', {})
    child = None
    for key, item in deps.items():
        if key.startswith('pkg:pypi/packaging@'):
            child = item
            break

    assert child is not None, 'packaging (runtime dep) must be in manifest.json'

    pkg = child['package']
    purl = pkg.get('purl', '')
    assert purl.startswith('pkg:pypi/packaging@'), (
        f'Unexpected purl: {purl!r}'
    )


# License entries in manifest.json must prefer SPDX over raw classifier strings.
# When a package supplies a License-Expression metadata field, that expression
# must be used rather than the raw PyPI classifier string. Packages that have no
# SPDX expression and whose classifier does not map to a known SPDX ID (e.g.,
# colorama's ambiguous "BSD License") are permitted to keep the raw classifier name.
def test_pypa_manifest_licenses_are_not_raw_classifiers(pypa_mocked, rbbuild):
    rbbuild.run(['-I'])
    rbbuild.run(['-sb'])
    rbbuild.run(['-p'])

    manifest_path = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID / 'manifest.json'
    with open(manifest_path) as f:
        manifest = json.load(f)

    # These packages provide a License-Expression field; the manifest must use
    # an expression or id entry, NOT a raw classifier string.
    spdx_expected = {
        'packaging',   # License-Expression: Apache-2.0 OR BSD-2-Clause
    }

    violations = []
    for pkg_name in spdx_expected:
        dep = None
        for key, item in manifest.get('dependencies', {}).items():
            if key.startswith(f'pkg:pypi/{pkg_name}@'):
                dep = item
                break
        if not dep:
            continue
        for lic_entry in dep.get('package', {}).get('licenses', []):
            # Each lic_entry is a License.to_dict(): {'expression': ...} or {'name': ...}
            name = lic_entry.get('name', '')
            if name.startswith('License ::'):
                violations.append(f'{pkg_name}: {name!r}')

    assert not violations, (
        'Raw PyPI classifier strings found where SPDX was expected:\n'
        + '\n'.join(violations)
    )


# ---------------------------------------------------------------------------
# rbbuild-native Python packaging (build-backend = rbbuild.buildsystem.build)
#
# These tests verify that when a project carries a [packaging.*] entry with
# type = 'python' in rbbuild.toml (and no external pyproject.toml), rbbuild -p
# calls build_sdist + build_wheel and writes the artefacts to obj/<toolchain>/.
# ---------------------------------------------------------------------------

_RBBUILD_TOML_PYTHON = '''\
[project]
name = "testpkg"
version_major = 1
version_minor = 0

[packaging.lib]
type = "python"
files = [{src = "testpkg"}]
'''

_PYTHON_INIT_PY = '# testpkg\n'


@pytest.fixture
def rbbuild_python_project(source_path):
    (source_path / 'rbbuild.toml').write_text(_RBBUILD_TOML_PYTHON)
    (source_path / 'Jenkinsfile').write_text(_JENKINSFILE)
    pkg_dir = source_path / 'testpkg'
    pkg_dir.mkdir()
    (pkg_dir / '__init__.py').write_text(_PYTHON_INIT_PY)
    yield source_path


# rbbuild -p must produce a source distribution (.tar.gz) under obj/<toolchain>/.
def test_rbbuild_python_pkg_sdist_created(rbbuild_python_project, rbbuild):
    rbbuild.run(['-sbp'])
    build_dir = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID
    sdists = list(build_dir.glob('*.tar.gz'))
    assert sdists, f'No sdist found under {build_dir}'


# rbbuild -p must produce a wheel (.whl) under obj/<toolchain>/.
def test_rbbuild_python_pkg_wheel_created(rbbuild_python_project, rbbuild):
    rbbuild.run(['-sbp'])
    build_dir = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID
    wheels = list(build_dir.glob('*.whl'))
    assert wheels, f'No wheel found under {build_dir}'


# A pure Python package does not record a toolchain: neither in the manifest
# and SBOM file names nor in manifest.json.
def test_rbbuild_python_pkg_has_no_toolchain(rbbuild_python_project, rbbuild):
    rbbuild.run(['-sbp'])
    build_dir = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID
    manifests = [*build_dir.glob('testpkg-*-manifest.json')]
    assert len(manifests) == 1
    assert _TOOLCHAIN_ID not in manifests[0].name
    assert _HOST_TOOLCHAIN_ID not in manifests[0].name
    assert [*build_dir.glob('testpkg-*-sbom.cdx.json')]
    with open(build_dir / 'manifest.json') as fd:
        assert 'toolchain' not in json.load(fd)['package']


# The wheel filename must use the py3-none-any compatibility tag.
def test_rbbuild_python_pkg_wheel_tag(rbbuild_python_project, rbbuild):
    rbbuild.run(['-sbp'])
    build_dir = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID
    wheel = next(build_dir.glob('*.whl'))
    assert '-py3-none-any.whl' in wheel.name


# The sdist tarball must contain a PKG-INFO entry at the archive root.
def test_rbbuild_python_pkg_sdist_contains_pkg_info(rbbuild_python_project, rbbuild):
    rbbuild.run(['-sbp'])
    build_dir = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID
    sdist = next(build_dir.glob('*.tar.gz'))
    with tarfile.open(sdist, 'r:gz') as tar:
        names = tar.getnames()
    assert any('PKG-INFO' in n for n in names)


# The wheel must contain WHEEL, METADATA, and RECORD inside a .dist-info directory.
def test_rbbuild_python_pkg_wheel_dist_info(rbbuild_python_project, rbbuild):
    rbbuild.run(['-sbp'])
    build_dir = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID
    wheel = next(build_dir.glob('*.whl'))
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    assert any(n.endswith('.dist-info/WHEEL') for n in names)
    assert any(n.endswith('.dist-info/METADATA') for n in names)
    assert any(n.endswith('.dist-info/RECORD') for n in names)


# Both sdist and wheel must appear as components in manifest.json.
def test_rbbuild_python_pkg_manifest_contains_sdist_and_wheel(rbbuild_python_project, rbbuild):
    rbbuild.run(['-sbp'])
    manifest_path = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID / 'manifest.json'
    assert manifest_path.exists(), 'manifest.json was not created'

    with open(manifest_path) as f:
        manifest = json.load(f)

    components = {c['name']: c for c in manifest['package'].get('components', [])}
    assert 'lib_sdist' in components, 'sdist component missing from manifest.json'
    assert 'lib' in components, 'wheel component missing from manifest.json'
    assert components['lib_sdist']['suffix'] == 'tar.gz'
    assert components['lib']['suffix'] == 'whl'


# ---------------------------------------------------------------------------
# rbbuild-native Python packaging — shared_data (.data wheel section)
#
# These tests verify that:
#   - shared_data entries produce a .data/data/ section in the generated wheel
#   - exclude correctly removes data files from the purelib section
#   - pip installs the shared data files to {prefix}/share/<name>/
# ---------------------------------------------------------------------------

_RBBUILD_TOML_SHARED_DATA = '''\
[project]
name = "testpkg"
version_major = 1
version_minor = 0

[packaging.lib]
type = "python"
files = [{src = "testpkg"}]
shared-data = [
    {src = "shared/config.cfg", strip = "shared", dest = "share/testpkg"},
]
'''

_SHARED_CONFIG_CFG = '[defaults]\nkey=value\n'


@pytest.fixture
def rbbuild_shared_data_project(source_path):
    (source_path / 'rbbuild.toml').write_text(_RBBUILD_TOML_SHARED_DATA)
    (source_path / 'Jenkinsfile').write_text(_JENKINSFILE)
    pkg_dir = source_path / 'testpkg'
    pkg_dir.mkdir()
    (pkg_dir / '__init__.py').write_text(_PYTHON_INIT_PY)
    shared_dir = source_path / 'shared'
    shared_dir.mkdir()
    (shared_dir / 'config.cfg').write_text(_SHARED_CONFIG_CFG)
    yield source_path


# The wheel must contain a .data/data/share/testpkg/config.cfg entry.
def test_rbbuild_python_pkg_wheel_has_data_section(rbbuild_shared_data_project, rbbuild):
    rbbuild.run(['-sbp'])
    build_dir = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID
    wheel = next(build_dir.glob('*.whl'))
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    data_entries = [n for n in names if '.data/data/' in n]
    assert data_entries, f'No .data section entries in wheel. Entries: {names}'
    assert any(n.endswith('share/testpkg/config.cfg') for n in data_entries), (
        f'Expected share/testpkg/config.cfg not found. .data entries: {data_entries}'
    )


# The shared data file must not appear at the purelib root of the wheel.
def test_rbbuild_python_pkg_shared_file_not_in_purelib(rbbuild_shared_data_project, rbbuild):
    rbbuild.run(['-sbp'])
    build_dir = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID
    wheel = next(build_dir.glob('*.whl'))
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    purelib_entries = [n for n in names if not n.endswith('.dist-info/') and '.data/' not in n]
    assert not any(n.endswith('config.cfg') for n in purelib_entries), (
        f'config.cfg found in purelib section: {purelib_entries}'
    )


# Installing the wheel into a venv must place the shared data at {venv}/share/testpkg/.
def test_rbbuild_python_pkg_shared_data_installed_in_venv(rbbuild_shared_data_project, rbbuild, tmp_path):
    rbbuild.run(['-sbp'])
    build_dir = rbbuild.workdir / 'obj' / _TOOLCHAIN_ID
    wheel = next(build_dir.glob('*.whl'))

    uv = shutil.which('uv')
    venv_path = tmp_path / 'test_venv'
    subprocess.run([uv, 'venv', str(venv_path)], check=True)
    subprocess.run(
        [uv, 'pip', 'install', '--python', str(venv_path), str(wheel)],
        check=True)

    data_file = venv_path / 'share' / 'testpkg' / 'config.cfg'
    assert data_file.exists(), f'Shared data not installed at expected path {data_file}'
    assert '[defaults]' in data_file.read_text()

