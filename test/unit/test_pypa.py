# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from pathlib import Path
from unittest.mock import MagicMock

from rbbuild.buildsystem.pypa import PyPA


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Build a minimal PyPA instance whose source directory is tmp_path.
# Pass pyproject_toml_text to have a pyproject.toml written to disk.
def _make_pypa(tmp_path, pyproject_toml_text=None):
    paths = MagicMock()
    paths.source  = tmp_path
    paths.staging = tmp_path / 'staging'
    paths.build   = tmp_path / 'obj' / 'test-toolchain'
    paths.dist    = tmp_path / 'dist'
    if pyproject_toml_text:
        (tmp_path / 'pyproject.toml').write_text(pyproject_toml_text)
    return PyPA(
        paths=paths,
        remote_services_config=MagicMock(),
        uv_config=MagicMock(),
        user_config=MagicMock(),
        packaging=MagicMock(),
        metadata=MagicMock(),
        toolchain=MagicMock(),
    )


_PYPROJECT_RUNTIME_AND_BUILD = '''\
[project]
name = "myapp"
version = "1.0"
dependencies = ["packaging>=25.0", "requests>=2.0"]

[dependency-groups]
build-only = ["packaging>=25.0", "setuptools>=61.0"]

[build-system]
requires      = ["rbbuild"]
build-backend = "rbbuild.buildsystem.build"
'''

_PYPROJECT_BUILD_ONLY = '''\
[project]
name = "myapp"
version = "1.0"
dependencies = []

[dependency-groups]
build-only = ["setuptools>=61.0", "wheel>=0.43"]

[build-system]
requires      = ["setuptools>=61.0", "wheel>=0.43"]
build-backend = "setuptools.build_meta"
'''


# ---------------------------------------------------------------------------
# _normalize_pkg_name
# ---------------------------------------------------------------------------

def test_normalize_lowercase(tmp_path):
    p = _make_pypa(tmp_path)
    assert p._normalize_pkg_name('Packaging') == 'packaging'


def test_normalize_underscores_to_hyphens(tmp_path):
    p = _make_pypa(tmp_path)
    assert p._normalize_pkg_name('my_pkg') == 'my-pkg'


def test_normalize_strips_whitespace(tmp_path):
    p = _make_pypa(tmp_path)
    assert p._normalize_pkg_name('  PyYAML  ') == 'pyyaml'


def test_normalize_already_canonical(tmp_path):
    p = _make_pypa(tmp_path)
    assert p._normalize_pkg_name('packaging') == 'packaging'


def test_normalize_dots_and_repeated_separators(tmp_path):
    p = _make_pypa(tmp_path)
    assert p._normalize_pkg_name('  my..pkg__name---x  ') == 'my-pkg-name-x'


# ---------------------------------------------------------------------------
# _make_package
# ---------------------------------------------------------------------------

def test_make_package_name_and_version(tmp_path):
    p = _make_pypa(tmp_path)
    pkg = p._make_package({'name': 'packaging', 'version': '26.2'})
    assert pkg.name    == 'packaging'
    assert pkg.version == '26.2'


def test_make_package_purl(tmp_path):
    p = _make_pypa(tmp_path)
    pkg = p._make_package({'name': 'packaging', 'version': '26.2'})
    assert str(pkg.purl) == 'pkg:pypi/packaging@26.2'


def test_make_package_hyphenated_purl(tmp_path):
    p = _make_pypa(tmp_path)
    pkg = p._make_package({'name': 'charset-normalizer', 'version': '3.4.7'})
    assert str(pkg.purl) == 'pkg:pypi/charset-normalizer@3.4.7'


# ---------------------------------------------------------------------------
# _package_from_installed_entry — license resolution
# ---------------------------------------------------------------------------

def _installed_entry(**kwargs):
    # Minimal installed-entry dict; override fields as needed.
    base = {
        'name': 'testpkg',
        'version': '1.0',
        'home_page': None,
        'license': None,
        'license_expression': None,
        'author': None,
        'author_email': None,
        'maintainer': None,
        'maintainer_email': None,
        'classifiers': [],
    }
    base.update(kwargs)
    return base


def test_license_known_spdx_classifier_wins(tmp_path):
    # 'MIT License' classifier maps to 'MIT' — must produce License(id='MIT').
    p = _make_pypa(tmp_path)
    entry = _installed_entry(
        classifiers=['License :: OSI Approved :: MIT License'],
        license_expression='some-expression',  # must be ignored
    )
    pkg = p._make_package(entry)
    assert len(pkg.licenses) == 1
    assert pkg.licenses[0].id == 'MIT'


def test_license_expression_used_when_classifier_has_no_spdx_id(tmp_path):
    # 'BSD License' maps to None → fall through to license_expression.
    p = _make_pypa(tmp_path)
    entry = _installed_entry(
        classifiers=['License :: OSI Approved :: BSD License'],
        license_expression='BSD-2-Clause',
    )
    pkg = p._make_package(entry)
    assert len(pkg.licenses) == 1
    assert pkg.licenses[0].expression == 'BSD-2-Clause'


def test_license_raw_classifier_name_when_no_expression(tmp_path):
    # BSD License → None, no expression → keep raw classifier name.
    p = _make_pypa(tmp_path)
    entry = _installed_entry(
        classifiers=['License :: OSI Approved :: BSD License'],
    )
    pkg = p._make_package(entry)
    assert len(pkg.licenses) == 1
    assert pkg.licenses[0].name == 'License :: OSI Approved :: BSD License'


def test_license_expression_fallback_when_no_classifiers(tmp_path):
    p = _make_pypa(tmp_path)
    entry = _installed_entry(license_expression='Apache-2.0 OR BSD-2-Clause')
    pkg = p._make_package(entry)
    assert len(pkg.licenses) == 1
    assert pkg.licenses[0].expression == 'Apache-2.0 OR BSD-2-Clause'


def test_license_raw_field_last_resort(tmp_path):
    p = _make_pypa(tmp_path)
    entry = _installed_entry(license='Custom Internal License')
    pkg = p._make_package(entry)
    assert len(pkg.licenses) == 1
    assert pkg.licenses[0].expression == 'Custom Internal License'


def test_license_unknown_raw_field_ignored(tmp_path):
    p = _make_pypa(tmp_path)
    entry = _installed_entry(license='UNKNOWN')
    pkg = p._make_package(entry)
    assert pkg.licenses == []


def test_license_no_license_info(tmp_path):
    p = _make_pypa(tmp_path)
    entry = _installed_entry()
    pkg = p._make_package(entry)
    assert pkg.licenses == []


def test_license_multiple_known_classifiers(tmp_path):
    # Both 'MIT License' and 'Apache Software License' — only MIT maps to SPDX.
    p = _make_pypa(tmp_path)
    entry = _installed_entry(
        classifiers=[
            'License :: OSI Approved :: MIT License',
            'License :: OSI Approved :: Apache Software License',  # maps to None
        ],
    )
    pkg = p._make_package(entry)
    # MIT → id; Apache has no SPDX ID so only MIT survives in spdx_licenses.
    spdx_ids = {lic.id for lic in pkg.licenses if lic.id}
    assert 'MIT' in spdx_ids


def test_license_two_known_spdx_classifiers(tmp_path):
    p = _make_pypa(tmp_path)
    entry = _installed_entry(
        classifiers=[
            'License :: OSI Approved :: MIT License',
            'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
        ],
    )
    pkg = p._make_package(entry)
    ids = {lic.id for lic in pkg.licenses}
    assert 'MIT' in ids
    assert 'MPL-2.0' in ids


# ---------------------------------------------------------------------------
# _package_from_installed_entry — copyright
# ---------------------------------------------------------------------------

def test_copyright_author_only(tmp_path):
    p = _make_pypa(tmp_path)
    entry = _installed_entry(author='Alice')
    pkg = p._make_package(entry)
    assert pkg.copyright == 'Author: Alice'


def test_copyright_multiple_fields(tmp_path):
    p = _make_pypa(tmp_path)
    entry = _installed_entry(
        author='Alice',
        author_email='alice@example.com',
        maintainer='Bob',
        maintainer_email='bob@example.com',
    )
    pkg = p._make_package(entry)
    assert pkg.copyright == (
        'Author: Alice; Author-email: alice@example.com; '
        'Maintainer: Bob; Maintainer-email: bob@example.com'
    )


def test_copyright_none_when_no_contact_info(tmp_path):
    p = _make_pypa(tmp_path)
    entry = _installed_entry()
    pkg = p._make_package(entry)
    assert pkg.copyright is None


# ---------------------------------------------------------------------------
# _package_from_installed_entry — default wheel component
# ---------------------------------------------------------------------------

def test_default_wheel_component_present(tmp_path):
    p = _make_pypa(tmp_path)
    entry = _installed_entry(name='mypkg', version='2.3')
    pkg = p._make_package(entry)
    assert len(pkg.components) == 1
    comp = pkg.components[0]
    assert comp.name   == 'wheel'
    assert comp.suffix == 'whl'
    assert 'mypkg' in comp.filename
    assert '2.3'   in comp.filename


# ---------------------------------------------------------------------------
# _build_only_names
# ---------------------------------------------------------------------------

def test_build_only_names_pure_build_dep(tmp_path):
    # setuptools/wheel only in build-system.requires → build_only
    p = _make_pypa(tmp_path, _PYPROJECT_BUILD_ONLY)
    names = p._build_only_names
    assert 'setuptools' in names
    assert 'wheel' in names


def test_build_only_names_runtime_dep_not_included(tmp_path):
    p = _make_pypa(tmp_path, _PYPROJECT_BUILD_ONLY)
    names = p._build_only_names
    # only setuptools and wheel are in build-system.requires
    assert 'packaging' not in names


def test_build_only_names_shared_dep_excluded(tmp_path):
    # packaging is in both [project.dependencies] and [build-system.requires]
    # → it is a runtime dep, must NOT be in build_only_names
    p = _make_pypa(tmp_path, _PYPROJECT_RUNTIME_AND_BUILD)
    names = p._build_only_names
    assert 'packaging' not in names
    assert 'setuptools' in names


def test_build_only_names_empty_when_no_build_system(tmp_path):
    toml = '[project]\nname="x"\nversion="1.0"\ndependencies=[]\n'
    p = _make_pypa(tmp_path, toml)
    assert p._build_only_names == set()


def test_requirements_empty_when_project_section_missing(tmp_path):
    toml = '[build-system]\nrequires=["setuptools>=61.0"]\nbuild-backend="setuptools.build_meta"\n'
    p = _make_pypa(tmp_path, toml)
    assert p.requirements == []


def test_execute_uv_calls(tmp_path, monkeypatch):
    p = _make_pypa(tmp_path)

    calls = {'ensure': 0, 'argv': None}
    def _fake_uv(*argv):
        calls['argv'] = list(argv)

    monkeypatch.setattr(p, 'uv', _fake_uv)

    p.uv('pip', 'install', 'packaging>=25.0')

    assert calls['argv'] == ['pip', 'install', 'packaging>=25.0']


# ---------------------------------------------------------------------------
# available
# ---------------------------------------------------------------------------

def test_available_true_with_pyproject(tmp_path):
    p = _make_pypa(tmp_path, _PYPROJECT_BUILD_ONLY)
    assert p.available is True


def test_available_false_without_pyproject_or_packaging(tmp_path):
    p = _make_pypa(tmp_path)
    assert p.available is False


def test_available_true_with_python_type_packaging(tmp_path):
    # pypa must be active even with no pyproject.toml when the rbbuild.toml
    # declares a packaging entry with type='python'.
    p = _make_pypa(tmp_path)
    p.packaging.items.return_value = [('lib', {'type': 'python', 'files': ['pkg']})]
    assert p.available is True


def test_available_false_with_rbbuild_type_only(tmp_path):
    p = _make_pypa(tmp_path)
    p.packaging.items.return_value = [('lib', {'type': 'rbbuild', 'files': ['artifact.tar.xz']})]
    assert p.available is False


# uv only creates the staging venv; the toolchain's Python must be available.
def test_ensure_venv_uses_python_of_toolchain(tmp_path):
    p = _make_pypa(tmp_path)
    p.toolchain.python_path = Path('/opt/py/python3.14')
    p.toolchain.apply_python_environment.side_effect = lambda environ: {**environ, 'X': '1'}
    p.__dict__['_uv_executable'] = 'uv'
    p._execute = MagicMock()

    p._ensure_venv()

    argv = p._execute.call_args.args[0]
    assert argv == ['uv', 'venv', str(p.venv_path), '--python', str(Path('/opt/py/python3.14')), '--no-python-downloads']
    assert p._execute.call_args.kwargs['environ']['X'] == '1'


def test_ensure_venv_without_python_of_toolchain(tmp_path):
    p = _make_pypa(tmp_path)
    p.toolchain.python_path = None
    p.toolchain.apply_python_environment.side_effect = lambda environ: environ
    p.__dict__['_uv_executable'] = 'uv'
    p._execute = MagicMock()

    p._ensure_venv()

    assert p._execute.call_args.args[0] == ['uv', 'venv', str(p.venv_path)]
