# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import argparse
import re
import shutil
import subprocess
import sys

from pathlib import Path

import pytest

import rbbuild.__main__ as rbbuild_mod
import rbbuild.pkq      as pkq_mod
import rbbuild.promote  as promote_mod
import rbbuild.rbbconf  as rbbconf_mod
import rbbuild.rbfoss   as rbfoss_mod

from rbbuild.librbb.term import LogLevel


_SCRIPT = Path(__file__).resolve().parents[2] / 'share/bash-completion/completions/rbbuild'
_TOOLS = {
    'rbbuild': rbbuild_mod,
    'pkq':     pkq_mod,
    'rbbconf': rbbconf_mod,
    'promote': promote_mod,
    'rbfoss':  rbfoss_mod,
}


def _script_text():
    return _SCRIPT.read_text(encoding='utf-8')


# Single-quoted shell variable assignments, e.g. _rbb_opts_pkq='-h --help ...'
def _script_words():
    return {
        m.group(1): m.group(2).split()
        for m in re.finditer(r"^(\w+)='([^']*)'", _script_text(), re.M)
    }


# The parsers are built inside parse_command_line(), so grab them on parse
def _parser_options(module, monkeypatch):
    parsers = []

    def fake_parse_args(self, *args, **kwargs):
        parsers.append(self)
        return argparse.Namespace(action=[])

    monkeypatch.setattr(argparse.ArgumentParser, 'parse_args', fake_parse_args)
    monkeypatch.setattr(sys, 'argv', ['prog'])
    module.parse_command_line()
    return {
        option
        for action in parsers[0]._actions
        for option in action.option_strings
        if option not in ('-', '--')
    }


@pytest.mark.parametrize('tool', _TOOLS)
def test_completion_options_match_parser(tool, monkeypatch):
    script_options = _script_words()[f'_rbb_opts_{tool}']
    assert len(script_options) == len(set(script_options))
    assert set(script_options) == _parser_options(_TOOLS[tool], monkeypatch)


def test_completion_log_levels_match_term():
    assert _script_words()['_rbb_log_levels'] == list(LogLevel.__members__)


def test_completion_registered_for_all_tools():
    registered = re.findall(r'^complete .* (\w+)$', _script_text(), re.M)
    assert sorted(registered) == sorted(_TOOLS)


@pytest.mark.skipif(
    sys.platform == 'win32' or shutil.which('bash') is None,
    reason='bash not available',
)
def test_completion_script_has_valid_bash_syntax():
    result = subprocess.run(
        ['bash', '-n'], input=_script_text().encode(), capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
