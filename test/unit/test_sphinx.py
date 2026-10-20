# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from types import SimpleNamespace

from rbbuild.docsystem.sphinx import Sphinx


def _make_sphinx(tmp_path, sphinx_config=None, project_config=None):
    # Provide a minimal sphinx-conf.py.in template so _setup can write a conf.py
    templates_path = tmp_path / 'templates'
    templates_path.mkdir()
    (templates_path / 'sphinx-conf.py.in').write_text(
        'project = "$_RBB_PROJECT_NAME"\n'
        'author  = "$_RBB_AUTHOR_NAMES"\n'
        'release = "$_RBB_VERSION"\n'
        'rinoh_documents = [dict(doc="${_RBB_DOCUMENT_TITLE}")]\n'
        '$_RBB_LOGO_LINE\n'
    )

    paths = SimpleNamespace(
        source=tmp_path / 'src',
        documentation=tmp_path / 'doc',
        templates=templates_path,
    )

    return Sphinx(
        sphinx_config=sphinx_config,
        project_config=project_config,
        paths=paths,
        issueman=SimpleNamespace(),
    )


def _make_package(name='mypkg', version='1.0.0'):
    pkg = SimpleNamespace()
    pkg.name = name
    pkg.version = version
    return pkg


def test_setup_with_no_project_section(tmp_path):
    """project_config=None (no [project] in pyproject.toml) must not raise."""
    sphinx = _make_sphinx(
        tmp_path,
        sphinx_config={'manual': {'sourcedir': 'docs', 'title': 'My Manual'}},
        project_config=None,
    )

    # Should not raise AttributeError: 'NoneType' object has no attribute 'get'
    sphinx._setup(_make_package())

    conf_py = tmp_path / 'doc' / 'sphinx' / 'manual' / 'conf.py'
    assert conf_py.exists()
    content = conf_py.read_text()
    assert 'mypkg' in content


def test_setup_with_authors(tmp_path):
    sphinx = _make_sphinx(
        tmp_path,
        sphinx_config={'manual': {'sourcedir': 'docs'}},
        project_config={'authors': [{'name': 'Alice'}, {'name': 'Bob'}]},
    )

    sphinx._setup(_make_package())

    content = (tmp_path / 'doc' / 'sphinx' / 'manual' / 'conf.py').read_text()
    assert 'Alice' in content
    assert 'Bob' in content


def test_setup_skips_existing_conf_py(tmp_path):
    """If conf.py already exists it must not be overwritten."""
    sphinx = _make_sphinx(
        tmp_path,
        sphinx_config={'manual': {'sourcedir': 'docs'}},
        project_config=None,
    )

    conf_py = tmp_path / 'doc' / 'sphinx' / 'manual' / 'conf.py'
    conf_py.parent.mkdir(parents=True)
    conf_py.write_text('# already here\n')

    sphinx._setup(_make_package())

    assert conf_py.read_text() == '# already here\n'
