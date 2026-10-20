#!/usr/bin/env python

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import hashlib
import json
import pytest
import re
import sys


def test_pkq_version(pkq):
    pkq.run(['--version'])
    output = pkq.read_console().strip()
    assert re.match(r'^\d+.\d+.\d+.\d+$', output)


def test_pkq_list(pkq):
    pkq.run(['-l', '-C', 'sample-development'])
    output = pkq.read_console().strip()
    assert output == (
'''Packages in channel sample-development:
[*] conflict_demo
[*] sample_tools''')


def test_pkq_list_package(pkq):
    pkq.run(['-l', 'sample_tools', '-C', 'sample-development'])
    output = pkq.read_console().strip()
    assert output == (
'''sample_tools
[*] sample_tools-2.0.0.4
[*] sample_tools-1.1.0.3
[*] sample_tools-1.0.0.2
[*] sample_tools-1.0.0.1''')


# "conflict_demo" fixture has a 5th "conflict" digit version (1.0.0.0.1)
# alongside its base 4-digit version (1.0.0.0), mirroring what
# bump_conflict_version() produces on a publish conflict. Verifies the
# 5-part version sorts as newer and is still matched/listed correctly.
def test_pkq_list_package_with_conflict_digit(pkq):
    pkq.run(['-l', 'conflict_demo', '-C', 'sample-development'])
    output = pkq.read_console().strip()
    assert output == (
'''conflict_demo
[*] conflict_demo-1.0.0.0.1
[*] conflict_demo-1.0.0.0''')


# Pinning the 5-part conflict version resolves and parses its manifest
# just like any other version.
def test_pkq_list_specific_version_conflict_digit(pkq):
    pkq.run(['-l', 'conflict_demo-1.0.0.0.1', '-C', 'sample-development'])
    output = pkq.read_console().strip()
    assert 'conflict_demo-1.0.0.0.1' in output
    assert 'channel:' in output
    assert 'sample-development' in output


# default channel of the test profile
def test_pkq_list_profile(pkq):
    pkq.run(['-l'])
    output = pkq.read_console().strip()
    assert output == (
'''Packages in channel example-development:
[*] libbar
[*] libbaz
[*] libfoo
[*] testlib
[*] testtool''')


# default channel of the test profile
def test_pkq_list_package_profile(pkq):
    pkq.run(['-l', 'libfoo'])
    output = pkq.read_console().strip()
    assert output == (
'''libfoo
[*] libfoo-2.0.0.3
[*] libfoo-1.1.0.2
[*] libfoo-1.0.0.1''')


# listing a package with many versions to verify sort order and count
def test_pkq_list_many_versions(pkq):
    pkq.run(['-l', 'libbaz'])
    output = pkq.read_console().strip()
    assert output == (
'''libbaz
[*] libbaz-2.0.0.5
[*] libbaz-1.1.0.4
[*] libbaz-1.1.0.3
[*] libbaz-1.0.0.2
[*] libbaz-1.0.0.1
[*] libbaz-0.9.0.1''')


# --max-query-items is ignored for mode 1 (no package)
def test_pkq_list_max_query_items_names(pkq):
    pkq.run(['-l', '--max-query-items', '2'])
    output = pkq.read_console().strip()
    lines = [line for line in output.splitlines() if line.startswith('[*]')]
    assert len(lines) == 5


# --max-query-items limits results in mode 2 (version constraint)
def test_pkq_list_max_query_items_constraint(pkq):
    pkq.run(['-l', 'libbaz>=1.0', '--max-query-items', '3'])
    output = pkq.read_console().strip()
    lines = [line for line in output.splitlines() if line.startswith('[*]')]
    assert len(lines) == 3


# querying a pinned version shows detail info and available toolchains
def test_pkq_list_specific_version(pkq):
    pkq.run(['-l', 'libfoo-2.0.0.3'])
    output = pkq.read_console().strip()
    assert 'libfoo-2.0.0.3' in output
    assert 'channel:' in output
    assert 'example-development' in output
    assert 'git repo:' in output
    assert 'https://example.com/git/libfoo.git' in output
    assert 'git hash:' in output
    assert hashlib.sha1(b'libfoo-2.0.0.3').hexdigest() in output
    assert 'toolchain:' in output
    # selected toolchain is listed first (no marker text; highlighted via terminal formatting)
    assert ('win32-mingw' if sys.platform == 'win32' else 'linux-native') in output


# querying a pinned version for a toolchain it was never published under
# reports which toolchain(s) it IS available for, instead of a bare "not found"
def test_pkq_list_specific_version_wrong_toolchain(pkq):
    with pytest.raises(RuntimeError):
        pkq.run(['-l', 'sample_tools-1.0.0.2', '-t', 'win32-mingw', '-C', 'sample-development'])
    output = pkq.read_console().strip()
    assert 'not available for selected toolchain' in output.lower()
    assert 'linux-native' in output


# tree shows package and all its transitive dependencies
def test_pkq_tree(pkq):
    pkq.run(['libbar-2.0.0.2', '--tree'])
    output = pkq.read_console().strip()
    assert output == (
'''libbar-2.0.0.2
libfoo-2.0.0.3
testtool-1.0.0.1 (build_only)
    testlib-1.0.0.1 (build_only)''')


# manifest command prints a header identifying the package
def test_pkq_manifest(pkq):
    pkq.run(['libfoo-2.0.0.3', '--manifest'])
    output = pkq.read_console().strip()
    assert 'Content of "manifest.json" file (libfoo-2.0.0.3):' in output


# resolve finds deps.json in the source directory and outputs resolved packages as TOML
def test_pkq_resolve(pkq):
    (pkq.workdir / 'deps.json').write_text(json.dumps({'/' : {'deps': ['libbar']}}))
    pkq.run(['-R'])
    output = pkq.read_console().strip()
    assert '[[dependencies]]' in output
    assert 'libbar-' in output


# changes between two libfoo versions shows the changed state and dependency diffs
def test_pkq_changes(pkq):
    pkq.run(['libfoo-1.0.0.1..2.0.0.3'])
    output = pkq.read_console().strip()
    assert 'libfoo:' in output
    assert '[changed]' in output
    assert '\u2192' in output


# changes with identical versions produces no output
def test_pkq_changes_same_version(pkq):
    pkq.run(['libfoo-2.0.0.3..2.0.0.3'])
    output = pkq.read_console().strip()
    assert output == ''


# reverse-search: find which of the listed packages contain libfoo
def test_pkq_reverse_search(pkq):
    pkq.run(['-r', 'libfoo', 'libbar'])
    output = pkq.read_console().strip()
    assert 'libfoo-2.0.0.3 is contained in' in output
    assert '[*] libbar-' in output


# reverse-search across all packages in the channel
def test_pkq_reverse_search_all(pkq):
    pkq.run(['-r', 'libfoo'])
    output = pkq.read_console().strip()
    assert '[*] libfoo-2.0.0.3' in output
    assert '[*] libbar-' in output
