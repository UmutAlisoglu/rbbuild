# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import subprocess
import sys
import tomllib

from types import SimpleNamespace

import pytest

from rbbuild.buildsystem.ruff import Ruff


def _paths(tmp_path):
    return SimpleNamespace(
        source=tmp_path,
        build=tmp_path / 'obj' / 'none-any',
        build_root=tmp_path / 'obj',
        staging_root=tmp_path / 'staging',
    )


def _ruff(tmp_path, profile_config=None):
    if profile_config is not None:
        profile = tmp_path / 'profile' / 'ruff.toml'
        profile.parent.mkdir(exist_ok=True)
        profile.write_text(profile_config)
        profile_config = str(profile)
    return Ruff(paths=_paths(tmp_path), profile_ruff_config=profile_config)


def _generated(tmp_path):
    with open(tmp_path / 'obj' / 'none-any' / 'ruff.toml', 'rb') as fd:
        return tomllib.load(fd)


@pytest.mark.parametrize('name', ['pyproject.toml', 'ruff.toml', '.ruff.toml'])
def test_available_with_python_config_file(tmp_path, name):
    (tmp_path / name).write_text('')
    assert _ruff(tmp_path).available


def test_not_available_without_python_config_file(tmp_path):
    assert not _ruff(tmp_path).available


def test_no_profile_config_leaves_discovery_to_ruff(tmp_path):
    (tmp_path / 'ruff.toml').write_text("line-length = 100\n")
    assert _ruff(tmp_path).config_arguments() == []
    assert not (tmp_path / 'obj').exists()


def test_profile_config_is_used_as_is_without_project_config(tmp_path):
    ruff = _ruff(tmp_path, '[lint]\nselect = ["F"]\n')
    assert ruff.config_arguments() == ['--config', str(ruff.profile_ruff_config)]
    assert not (tmp_path / 'obj').exists()


def test_profile_config_is_used_as_is_with_pyproject_without_ruff_section(tmp_path):
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "x"\n')
    ruff = _ruff(tmp_path, '[lint]\nselect = ["F"]\n')
    assert ruff.config_arguments() == ['--config', str(ruff.profile_ruff_config)]
    assert not (tmp_path / 'obj').exists()


def test_profile_config_is_used_as_is_with_empty_ruff_toml(tmp_path):
    (tmp_path / 'ruff.toml').write_text('')
    ruff = _ruff(tmp_path, '[lint]\nselect = ["F"]\n')
    assert ruff.config_arguments() == ['--config', str(ruff.profile_ruff_config)]


def test_project_ruff_toml_is_merged_via_generated_config(tmp_path):
    (tmp_path / 'ruff.toml').write_text(
        'line-length = 100\n'
        '[lint.per-file-ignores]\n'
        '"tests/*" = ["F841"]\n'
    )
    ruff = _ruff(tmp_path, '[lint]\nselect = ["F"]\n')

    assert ruff.config_arguments() == ['--config', str(tmp_path / 'obj' / 'none-any' / 'ruff.toml')]

    generated = _generated(tmp_path)
    assert generated['extend'] == str(ruff.profile_ruff_config)
    assert generated['line-length'] == 100
    assert generated['lint']['per-file-ignores'] == {'tests/*': ['F841']}


def test_project_pyproject_ruff_section_is_merged(tmp_path):
    (tmp_path / 'pyproject.toml').write_text(
        '[project]\nname = "x"\n'
        '[tool.ruff.lint]\nextend-select = ["B"]\n'
    )
    ruff = _ruff(tmp_path, '[lint]\nselect = ["F"]\n')

    ruff.config_arguments()

    generated = _generated(tmp_path)
    assert generated['extend'] == str(ruff.profile_ruff_config)
    assert generated['lint'] == {'extend-select': ['B']}
    assert 'project' not in generated


def test_project_dot_ruff_toml_takes_precedence(tmp_path):
    (tmp_path / '.ruff.toml').write_text('line-length = 100\n')
    (tmp_path / 'ruff.toml').write_text('line-length = 120\n')
    (tmp_path / 'pyproject.toml').write_text('[tool.ruff]\nline-length = 140\n')

    _ruff(tmp_path, '').config_arguments()
    assert _generated(tmp_path)['line-length'] == 100


@pytest.mark.parametrize('name, content', [
    ('ruff.toml', 'extend = "../base.toml"\n'),
    ('pyproject.toml', '[tool.ruff]\nextend = "../base.toml"\n'),
])
def test_project_extend_ignores_profile_config(tmp_path, name, content):
    (tmp_path / name).write_text(content)
    assert _ruff(tmp_path, '[lint]\nselect = ["F"]\n').config_arguments() == []
    assert not (tmp_path / 'obj').exists()


def _pyproject_requires_python(tmp_path, spec):
    (tmp_path / 'pyproject.toml').write_text(f'[project]\nname = "x"\nrequires-python = "{spec}"\n')


def test_target_version_is_derived_from_requires_python(tmp_path):
    _pyproject_requires_python(tmp_path, '>= 3.14')
    ruff = _ruff(tmp_path, '[lint]\nselect = ["F"]\n')
    assert ruff.config_arguments() == [
        '--config', str(ruff.profile_ruff_config),
        '--config', "target-version = 'py314'",
    ]


@pytest.mark.parametrize('spec, expected', [
    ('>=3.10,<3.13', 'py310'),
    ('~=3.12', 'py312'),
    ('<3.13', None),
    ('>=3', None),
])
def test_target_version_derivation(tmp_path, spec, expected):
    _pyproject_requires_python(tmp_path, spec)
    argv = _ruff(tmp_path, '').config_arguments()
    assert argv[2:] == (['--config', f"target-version = '{expected}'"] if expected else [])


@pytest.mark.parametrize('project, profile', [
    ('[tool.ruff]\ntarget-version = "py312"\n', ''),
    ('', 'target-version = "py312"\n'),
])
def test_configured_target_version_is_not_overridden(tmp_path, project, profile):
    (tmp_path / 'pyproject.toml').write_text(
        '[project]\nname = "x"\nrequires-python = ">=3.14"\n' + project)
    ruff = _ruff(tmp_path, profile)
    assert '--config' not in ruff.config_arguments()[2:]


def test_static_code_analysis_runs_ruff_in_source_folder(tmp_path, monkeypatch):
    (tmp_path / 'ruff.toml').write_text('')
    calls = []
    monkeypatch.setattr(
        subprocess, 'run',
        lambda argv, **kwargs: calls.append((argv, kwargs)) or SimpleNamespace(returncode=0))

    _ruff(tmp_path).static_code_analysis()

    argv, kwargs = calls[0]
    assert argv[:4] == [sys.executable, '-m', 'ruff', 'check']
    assert '--config' not in argv
    assert str(tmp_path / 'obj') in argv
    assert str(tmp_path / 'staging') in argv
    assert kwargs['cwd'] == tmp_path


def test_static_code_analysis_passes_profile_config(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        subprocess, 'run',
        lambda argv, **kwargs: calls.append(argv) or SimpleNamespace(returncode=0))
    ruff = _ruff(tmp_path, '[lint]\nselect = ["F"]\n')

    ruff.static_code_analysis()

    assert ['--config', str(ruff.profile_ruff_config)] == calls[0][4:6]


def test_static_code_analysis_fails_on_findings(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda argv, **kwargs: SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError, match='error code 1'):
        _ruff(tmp_path).static_code_analysis()


def _run_and_collect_messages(ruff, monkeypatch, returncode):
    monkeypatch.setattr(subprocess, 'run', lambda argv, **kwargs: SimpleNamespace(returncode=returncode))
    messages = []
    monkeypatch.setattr('rbbuild.buildsystem.ruff.term.info', lambda *args, **kwargs: messages.append(' '.join(map(str, args))))
    with pytest.raises(RuntimeError):
        ruff.static_code_analysis()
    return messages


def test_findings_show_complete_fix_command(tmp_path, monkeypatch):
    ruff = _ruff(tmp_path, '[lint]\nselect = ["F"]\n')

    messages = _run_and_collect_messages(ruff, monkeypatch, returncode=1)

    assert '-m ruff check' in messages[-1]
    assert str(ruff.profile_ruff_config) in messages[-1]
    assert messages[-1].rstrip().endswith('--fix')


def test_ruff_error_shows_no_fix_command(tmp_path, monkeypatch):
    messages = _run_and_collect_messages(_ruff(tmp_path), monkeypatch, returncode=2)

    assert not any('--fix' in message for message in messages)
