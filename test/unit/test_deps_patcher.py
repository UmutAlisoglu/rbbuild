# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest
import tomlkit

from rbbuild.deps.patcher import Patcher
from rbbuild.package.package import Package


@pytest.fixture
def patcher():
    yield Patcher()


# patch_dependencies_text() is the pure-text counterpart of
# update_dependencies_in_file() - same table-rewrite behavior, but neither
# reads nor writes a file.
def test_patch_dependencies_text_preserves_other_sections():
    original = (
        '[project]\n'
        'name = "myproject"\n'
    )

    result = Patcher().patch_dependencies_text(
        original, [{'namespace': 'ns1', 'deps': ['mypkg-1.0.0']}])

    assert '[project]' in result
    assert 'name = "myproject"' in result
    assert '[[dependencies]]' in result
    assert 'namespace = "ns1"' in result


# Appends a fresh [[dependencies]] table when the file has none yet, leaving
# existing content untouched.
def test_update_dependencies_in_file_appends_when_absent(tmp_path, patcher):
    path = tmp_path / 'rbbuild.toml'
    path.write_text(
        '[project]\n'
        'name = "myproject"\n'
    )

    patcher.update_dependencies_in_file(str(path), [{'namespace': 'ns1', 'deps': ['mypkg-1.0.0']}])

    text = path.read_text()
    assert '[project]' in text
    assert 'name = "myproject"' in text
    assert '[[dependencies]]' in text
    assert 'namespace = "ns1"' in text
    assert '"mypkg-1.0.0"' in text


# Replaces only the existing [[dependencies]] block, preserving comments and
# other tables verbatim.
def test_update_dependencies_in_file_replaces_existing_block(tmp_path, patcher):
    path = tmp_path / 'rbbuild.toml'
    path.write_text(
        '# top comment\n'
        '[project]\n'
        'name = "myproject"\n'
        '\n'
        '[[dependencies]]\n'
        'namespace = "old_ns"\n'
        'deps = [\n'
        '    "oldpkg-0.1.0",\n'
        ']\n'
        '\n'
        '[packaging.wheel]\n'
        'type = "python"\n'
    )

    patcher.update_dependencies_in_file(str(path), [{'namespace': 'new_ns', 'deps': ['newpkg-2.0.0']}])

    text = path.read_text()
    assert '# top comment' in text
    assert 'name = "myproject"' in text
    assert '[packaging.wheel]' in text
    assert 'type = "python"' in text
    assert 'old_ns' not in text
    assert 'oldpkg-0.1.0' not in text
    assert 'namespace = "new_ns"' in text
    assert '"newpkg-2.0.0"' in text


# Multiple pre-existing [[dependencies]] blocks are all removed and replaced
# by the single freshly generated set of sections.
def test_update_dependencies_in_file_replaces_multiple_blocks(tmp_path, patcher):
    path = tmp_path / 'rbbuild.toml'
    path.write_text(
        '[[dependencies]]\n'
        'namespace = "ns_a"\n'
        'deps = ["a-1.0.0"]\n'
        '\n'
        '[[dependencies]]\n'
        'namespace = "ns_b"\n'
        'deps = ["b-1.0.0"]\n'
    )

    patcher.update_dependencies_in_file(str(path), [{'namespace': 'ns_c', 'deps': ['c-1.0.0']}])

    text = path.read_text()
    assert text.count('[[dependencies]]') == 1
    assert 'ns_a' not in text
    assert 'ns_b' not in text
    assert 'ns_c' in text


# An empty dependencies_config removes the existing block without inserting
# a replacement.
def test_update_dependencies_in_file_removes_when_empty(tmp_path, patcher):
    path = tmp_path / 'rbbuild.toml'
    path.write_text(
        '[project]\n'
        'name = "myproject"\n'
        '\n'
        '[[dependencies]]\n'
        'namespace = "ns1"\n'
        'deps = ["mypkg-1.0.0"]\n'
    )

    patcher.update_dependencies_in_file(str(path), [])

    text = path.read_text()
    assert '[project]' in text
    assert '[[dependencies]]' not in text
    assert 'mypkg-1.0.0' not in text


# A nonexistent target file is created from scratch rather than raising.
def test_update_dependencies_in_file_creates_missing_file(tmp_path, patcher):
    path = tmp_path / 'rbbuild.toml'
    assert not path.exists()

    patcher.update_dependencies_in_file(
        str(path), [{'namespace': 'ns1', 'deps': ['mypkg-1.0.0']}])

    text = path.read_text()
    assert '[[dependencies]]' in text
    assert 'namespace = "ns1"' in text
    assert '"mypkg-1.0.0"' in text


# table='tool.rbbuild.dependencies' (pyproject.toml's form) both matches an
# existing block by its full dotted header and writes new blocks under it,
# leaving a same-named bare [[dependencies]] untouched if present.
def test_update_dependencies_in_file_with_dotted_table(tmp_path, patcher):
    path = tmp_path / 'pyproject.toml'
    path.write_text(
        '[project]\n'
        'name = "myproject"\n'
        '\n'
        '[[tool.rbbuild.dependencies]]\n'
        'namespace = "old_ns"\n'
        'deps = ["oldpkg-0.1.0"]\n'
    )

    patcher.update_dependencies_in_file(
        str(path), [{'namespace': 'new_ns', 'deps': ['newpkg-2.0.0']}],
        table='tool.rbbuild.dependencies')

    text = path.read_text()
    assert '[project]' in text
    assert 'old_ns' not in text
    assert '[[tool.rbbuild.dependencies]]' in text
    assert 'namespace = "new_ns"' in text
    assert '"newpkg-2.0.0"' in text


# entry_comments' leading lines are written as standalone comment lines
# above their entry, and the inline comment trails on the entry's own line.
def test_update_dependencies_in_file_preserves_entry_comments(tmp_path, patcher):
    path = tmp_path / 'rbbuild.toml'
    pkg = Package(name='mypkg', version='1.0.0')

    patcher.update_dependencies_in_file(
        str(path), [{'deps': [pkg]}],
        entry_comments={id(pkg): {
            'leading': ['pinned for CVE-1234'], 'inline': 'do not upgrade'}})

    text = path.read_text()
    assert '# pinned for CVE-1234' in text
    assert '"mypkg-1.0.0", # do not upgrade' in text


# render_toml() renders the same comment-bearing TOML as
# update_dependencies_in_file() would write, without touching disk.
def test_render_toml_includes_comments(patcher):
    pkg = Package(name='mypkg', version='1.0.0')

    text = patcher.render_toml(
        [{'deps': [pkg]}],
        entry_comments={id(pkg): {'leading': ['a note']}})

    assert '# a note' in text
    assert '"mypkg-1.0.0"' in text


# read_array_comments() maps each entry's 0-based array position to its
# leading/inline comments, based on a freshly tomlkit-parsed Array.
def test_read_array_comments():
    doc = tomlkit.parse(
        'deps = [\n'
        '    # a leading note\n'
        '    "pkg1-1.0.0", # an inline note\n'
        '    "pkg2-1.0.0",\n'
        ']\n')

    comments = Patcher.read_array_comments(doc['deps'])

    assert comments == {
        0: {'leading': ['a leading note'], 'inline': 'an inline note'},
    }


# Arrays with no comments (or plain lists, not tomlkit Arrays) yield an
# empty mapping rather than raising.
def test_read_array_comments_returns_empty_for_plain_list():
    assert Patcher.read_array_comments(['pkg1-1.0.0']) == {}


# A standalone comment with no following entry (e.g. a fully commented-out
# example left in an otherwise-empty array) has no real index to attach
# to, so it's reported under the key equal to the array's length.
def test_read_array_comments_captures_trailing_comment_in_empty_array():
    doc = tomlkit.parse(
        'deps = [\n'
        "#    'sample-sources:sonar_build_wrapper-6.7-linux-x86',\n"
        ']\n')

    comments = Patcher.read_array_comments(doc['deps'])

    assert comments == {
        0: {'leading': ["'sample-sources:sonar_build_wrapper-6.7-linux-x86',"]},
    }


# update_dependencies_in_file()/render_toml() re-emit a section's trailing
# comment (passed via dependencies_config's '_deps_trailing_comment' key)
# even when its deps list is empty, instead of collapsing to 'deps = []'
# and silently dropping the comment.
def test_update_dependencies_in_file_preserves_trailing_comment_in_empty_section(tmp_path, patcher):
    path = tmp_path / 'rbbuild.toml'

    patcher.update_dependencies_in_file(
        str(path),
        [{'namespace': 'sonar', 'deps': [],
          '_deps_trailing_comment': ['a commented-out example']}])

    text = path.read_text()
    assert '# a commented-out example' in text
    assert 'deps = []' not in text


def test_render_toml_preserves_trailing_comment_in_empty_section(patcher):
    text = patcher.render_toml(
        [{'namespace': 'sonar', 'deps': [],
          '_deps_trailing_comment': ['a commented-out example']}])

    assert '# a commented-out example' in text
    assert 'deps = []' not in text

