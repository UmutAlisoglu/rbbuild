# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

from rbbuild.package.package import Package
from rbbuild.ui.deps.control import DepsEditorController


@pytest.fixture
def active_deps():
    return [Package('mypkg', '1.0.0'), Package('otherpkg', '2.0.0')]


@pytest.fixture
def controller(active_deps):
    return DepsEditorController(active_deps)


# --- select() ---

def test_select_sets_selected_package(controller, active_deps):
    controller.select(0)
    assert controller.selected is active_deps[0]


def test_select_out_of_range_clears_selected(controller):
    controller.select(5)
    assert controller.selected is None


# --- remove_selected() ---

def test_remove_selected_removes_package_and_clears_selection(controller, active_deps):
    pkg = active_deps[0]
    controller.select(0)
    controller.remove_selected()
    assert pkg not in active_deps
    assert controller.selected is None


def test_remove_selected_noop_when_nothing_selected(controller, active_deps):
    original = list(active_deps)
    controller.remove_selected()
    assert active_deps == original


# --- apply_flags() ---

def test_apply_flags_sets_build_only_and_traverse(controller, active_deps):
    controller.select(0)
    controller.apply_flags(True, False, '', '')
    pkg = active_deps[0]
    assert pkg.component_specifier.check(None, None, 'build_only') is True
    assert pkg.component_specifier.check(None, None, 'traverse') is False


def test_apply_flags_sets_components_and_suffixes(controller, active_deps):
    controller.select(0)
    controller.apply_flags(False, True, 'dev, prod', 'tar.gz')
    pkg = active_deps[0]
    keys = set(pkg.component_specifier.items.keys())
    assert keys == {('dev', 'tar.gz'), ('prod', 'tar.gz')}


# --- apply_sbom() ---

def test_apply_sbom_sets_plain_fields(controller, active_deps):
    controller.select(0)
    controller.apply_sbom(
        'cpe:2.3:a:Example:mypkg:1.0.0:*:*:*:*:*:*:*',
        'Copyright 2025 Example Corp',
        'MIT OR Apache-2.0',
        'dynamic_link',
        'library',
        '', '', '')

    pkg = active_deps[0]
    assert pkg.cpe == 'cpe:2.3:a:Example:mypkg:1.0.0:*:*:*:*:*:*:*'
    assert pkg.copyright == 'Copyright 2025 Example Corp'
    assert str(pkg.licenses[0]) == 'MIT OR Apache-2.0'
    assert str(pkg.integration_type) == 'dynamic_link'
    assert str(pkg.component_type) == 'library'


def test_apply_sbom_sets_supplier(controller, active_deps):
    controller.select(0)
    controller.apply_sbom('', '', '', '', '', 'Example', 'foo@example.com', 'https://example.com')

    supplier = active_deps[0].supplier
    assert supplier.name == 'Example'
    assert supplier.email == 'foo@example.com'
    assert supplier.url == 'https://example.com'


def test_apply_sbom_clears_supplier_when_all_fields_blank(controller, active_deps):
    controller.select(0)
    controller.apply_sbom('', '', '', '', '', 'Example', '', '')
    controller.apply_sbom('', '', '', '', '', '', '', '')

    assert active_deps[0].supplier is None


def test_apply_sbom_defaults_component_type_to_application_when_blank(controller, active_deps):
    controller.select(0)
    controller.apply_sbom('', '', '', '', '', '', '', '')
    assert str(active_deps[0].component_type) == 'application'


# --- open_file() / save_file() ---

@pytest.fixture
def deps_parser(app):
    yield app.deps.parser()


@pytest.fixture
def controller_with_parser(deps_parser):
    return DepsEditorController([], deps_parser)


def test_open_file_loads_entries_into_active_deps(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        "[dependencies]\n"
        "deps = ['pkg1-1.0.0', 'pkg2-2.0.0']\n")

    controller_with_parser.open_file(toml_path)

    names = sorted(pkg.name for pkg in controller_with_parser.active_deps)
    assert names == ['pkg1', 'pkg2']
    assert controller_with_parser.loaded_path == toml_path


def test_open_file_replaces_existing_active_deps_in_place(deps_parser, tmp_path):
    active_deps = [Package('stale', '0.0.1')]
    controller = DepsEditorController(active_deps, deps_parser)

    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text("[dependencies]\ndeps = ['pkg1-1.0.0']\n")
    controller.open_file(toml_path)

    assert controller.active_deps is active_deps
    assert [pkg.name for pkg in active_deps] == ['pkg1']


def test_new_document_clears_active_deps_in_place(deps_parser, tmp_path):
    active_deps = [Package('stale', '0.0.1')]
    controller = DepsEditorController(active_deps, deps_parser)
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text("[dependencies]\ndeps = ['pkg1-1.0.0']\n")
    controller.open_file(toml_path)

    controller.new_document('rbbuild.toml')

    assert controller.active_deps is active_deps
    assert active_deps == []
    assert controller.loaded_path is None
    assert controller.selected is None


def test_new_document_derives_table_from_target_filename(controller_with_parser):
    controller_with_parser.new_document('pyproject.toml')
    assert controller_with_parser._table == 'tool.rbbuild.dependencies'

    controller_with_parser.new_document('rbbuild.toml')
    assert controller_with_parser._table == 'dependencies'


def test_save_file_round_trips_multi_section_structure(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        "[[dependencies]]\n"
        "deps = ['pkga-1.0.0']\n"
        'namespace = "ns_a"\n'
        "\n"
        "[[dependencies]]\n"
        "deps = ['pkgb-2.0.0']\n"
        'restrict_platform = "linux"\n')

    controller_with_parser.open_file(toml_path)
    controller_with_parser.save_file()

    text = toml_path.read_text()
    assert 'namespace = "ns_a"' in text
    assert 'restrict_platform = "linux"' in text

    controller_with_parser.open_file(toml_path)
    by_name = {pkg.name: pkg for pkg in controller_with_parser.active_deps}
    assert by_name['pkga'].namespace == 'ns_a'
    assert by_name['pkgb'].name == 'pkgb'


def test_save_file_persists_edited_sbom_fields(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text("[dependencies]\ndeps = ['pkg1-1.0.0']\n")

    controller_with_parser.open_file(toml_path)
    controller_with_parser.select(0)
    controller_with_parser.apply_sbom(
        'cpe:2.3:a:Example:pkg1:1.0.0:*:*:*:*:*:*:*', '', '', '', '', '', '', '')
    controller_with_parser.save_file()

    controller_with_parser.open_file(toml_path)
    pkg = controller_with_parser.active_deps[0]
    assert pkg.cpe == 'cpe:2.3:a:Example:pkg1:1.0.0:*:*:*:*:*:*:*'


def test_save_file_appends_packages_added_after_open(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text("[dependencies]\ndeps = ['pkg1-1.0.0']\n")

    controller_with_parser.open_file(toml_path)
    controller_with_parser.active_deps.append(Package('newpkg', '9.9.9'))
    controller_with_parser.save_file()

    controller_with_parser.open_file(toml_path)
    names = sorted(pkg.name for pkg in controller_with_parser.active_deps)
    assert names == ['newpkg', 'pkg1']


def test_save_file_without_path_or_loaded_path_raises(controller_with_parser):
    with pytest.raises(ValueError):
        controller_with_parser.save_file()


def test_save_file_to_new_path_updates_loaded_path(controller_with_parser, tmp_path):
    path_a = tmp_path / 'a.toml'
    path_a.write_text("[dependencies]\ndeps = ['pkg1-1.0.0']\n")
    path_b = tmp_path / 'b.toml'
    path_b.write_text("[dependencies]\ndeps = []\n")

    controller_with_parser.open_file(path_a)
    controller_with_parser.save_file(path_b)

    assert controller_with_parser.loaded_path == path_b
    assert 'pkg1' in path_b.read_text()


# pyproject.toml stores rbbuild's dependencies nested under
# [tool.rbbuild.dependencies], not a bare [dependencies] table.
def test_open_file_reads_pyproject_toml_nested_table(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'pyproject.toml'
    toml_path.write_text(
        "[project]\nname = 'myproject'\n\n"
        "[tool.rbbuild.dependencies]\n"
        "deps = ['pkg1-1.0.0']\n")

    controller_with_parser.open_file(toml_path)

    names = [pkg.name for pkg in controller_with_parser.active_deps]
    assert names == ['pkg1']


def test_save_file_writes_pyproject_toml_nested_table(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'pyproject.toml'
    toml_path.write_text(
        "[project]\nname = 'myproject'\n\n"
        "[tool.rbbuild.dependencies]\n"
        "deps = ['pkg1-1.0.0']\n")

    controller_with_parser.open_file(toml_path)
    controller_with_parser.active_deps.append(Package('newpkg', '9.9.9'))
    controller_with_parser.save_file()

    text = toml_path.read_text()
    assert '[tool.rbbuild.dependencies]' in text
    assert '[dependencies]' not in text

    controller_with_parser.open_file(toml_path)
    names = sorted(pkg.name for pkg in controller_with_parser.active_deps)
    assert names == ['newpkg', 'pkg1']


# A freshly assembled deps list (no open_file() call) can be saved straight
# to a nonexistent path - the file is created, with the table name chosen
# from the target filename (rbbuild.toml -> [dependencies]).
def test_save_file_creates_new_file(controller_with_parser, active_deps, tmp_path):
    controller_with_parser.active_deps.extend(active_deps)
    toml_path = tmp_path / 'rbbuild.toml'
    assert not toml_path.exists()

    controller_with_parser.save_file(toml_path)

    text = toml_path.read_text()
    assert '[[dependencies]]' in text
    assert 'mypkg' in text
    assert controller_with_parser.loaded_path == toml_path


# Same as above, but targeting a new pyproject.toml - uses the dotted
# [[tool.rbbuild.dependencies]] table instead.
def test_save_file_creates_new_pyproject_toml(controller_with_parser, active_deps, tmp_path):
    controller_with_parser.active_deps.extend(active_deps)
    toml_path = tmp_path / 'pyproject.toml'
    assert not toml_path.exists()

    controller_with_parser.save_file(toml_path)

    text = toml_path.read_text()
    assert '[[tool.rbbuild.dependencies]]' in text
    assert 'mypkg' in text


# --- render_preview() ---

# Before any file is loaded, render_preview() uses target_filename to pick
# the table, without touching disk at all.
def test_render_preview_before_open_uses_target_filename(controller_with_parser, active_deps):
    controller_with_parser.active_deps.extend(active_deps)

    assert '[[dependencies]]' in controller_with_parser.render_preview('rbbuild.toml')
    assert '[[tool.rbbuild.dependencies]]' in controller_with_parser.render_preview('pyproject.toml')


def test_render_preview_before_open_defaults_to_rbbuild_toml(controller_with_parser, active_deps):
    controller_with_parser.active_deps.extend(active_deps)
    assert '[[dependencies]]' in controller_with_parser.render_preview()


# Once a file is loaded, its own table takes precedence over
# target_filename - matches save_file()'s behavior.
def test_render_preview_after_open_ignores_target_filename(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'pyproject.toml'
    toml_path.write_text(
        "[tool.rbbuild.dependencies]\ndeps = ['pkg1-1.0.0']\n")
    controller_with_parser.open_file(toml_path)

    text = controller_with_parser.render_preview('rbbuild.toml')
    assert '[[tool.rbbuild.dependencies]]' in text
    assert 'pkg1' in text


def test_render_preview_does_not_write_to_disk(controller_with_parser, active_deps, tmp_path):
    controller_with_parser.active_deps.extend(active_deps)
    toml_path = tmp_path / 'rbbuild.toml'

    controller_with_parser.render_preview('rbbuild.toml')

    assert not toml_path.exists()


# --- load_from_text() ---

# Before any file is loaded, load_from_text() picks its table from
# target_filename, same as render_preview().
def test_load_from_text_before_open_uses_target_filename(controller_with_parser):
    controller_with_parser.load_from_text(
        "[[dependencies]]\ndeps = ['pkg1-1.0.0']\n", 'rbbuild.toml')

    assert [pkg.name for pkg in controller_with_parser.active_deps] == ['pkg1']
    assert controller_with_parser.loaded_path is None


# Once a file is loaded, its own table takes precedence - matches
# render_preview()/save_file()'s behavior - and loaded_path is untouched,
# so a subsequent Save still writes back to the original file.
def test_load_from_text_after_open_ignores_target_filename_and_keeps_loaded_path(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'pyproject.toml'
    toml_path.write_text(
        "[tool.rbbuild.dependencies]\ndeps = ['pkg1-1.0.0']\n")
    controller_with_parser.open_file(toml_path)

    controller_with_parser.load_from_text(
        "[tool.rbbuild.dependencies]\ndeps = ['pkg2-2.0.0']\n", 'rbbuild.toml')

    assert [pkg.name for pkg in controller_with_parser.active_deps] == ['pkg2']
    assert controller_with_parser.loaded_path == toml_path


def test_load_from_text_replaces_active_deps_in_place(deps_parser):
    active_deps = [Package('stale', '0.0.1')]
    controller = DepsEditorController(active_deps, deps_parser)

    controller.load_from_text("[[dependencies]]\ndeps = ['pkg1-1.0.0']\n")

    assert controller.active_deps is active_deps
    assert [pkg.name for pkg in active_deps] == ['pkg1']


# --- patch_into_text() ---

def test_patch_into_text_preserves_other_sections(controller_with_parser, active_deps):
    controller_with_parser.active_deps.extend(active_deps)
    base_text = '[project]\nname = "myproject"\n'

    result = controller_with_parser.patch_into_text(base_text, 'rbbuild.toml')

    assert 'name = "myproject"' in result
    assert '[[dependencies]]' in result
    assert 'mypkg' in result


def test_patch_into_text_does_not_write_to_disk(controller_with_parser, active_deps, tmp_path):
    controller_with_parser.active_deps.extend(active_deps)
    toml_path = tmp_path / 'rbbuild.toml'

    controller_with_parser.patch_into_text('', 'rbbuild.toml')

    assert not toml_path.exists()


# --- section settings ---

def test_current_section_index_defaults_to_zero_creating_empty_section(controller_with_parser):
    assert controller_with_parser.current_section_index() == 0
    assert controller_with_parser._section_attrs == [{}]


def test_current_section_index_follows_selected_entry(deps_parser, tmp_path):
    controller = DepsEditorController([], deps_parser)
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        "[[dependencies]]\n"
        "deps = ['pkga-1.0.0']\n"
        "\n"
        "[[dependencies]]\n"
        "deps = ['pkgb-2.0.0']\n"
        "namespace = 'ns_b'\n")
    controller.open_file(toml_path)

    controller.select(1)
    assert controller.current_section_index() == 1
    assert controller.get_section_attrs() == {'namespace': 'ns_b'}

    controller.select(0)
    assert controller.current_section_index() == 0
    assert controller.get_section_attrs() == {}


def test_apply_section_attrs_sets_and_clears_fields(controller_with_parser):
    controller_with_parser.apply_section_attrs(
        namespace='ns1', restrict_platform='linux',
        components=['prod'], build_only=True, traverse=True,
        package_install_action='copy')

    assert controller_with_parser.get_section_attrs() == {
        'namespace': 'ns1', 'restrict_platform': 'linux',
        'components': ['prod'], 'build_only': True,
        'package_install_action': 'copy',
    }

    controller_with_parser.apply_section_attrs(namespace='', build_only=False)
    assert controller_with_parser.get_section_attrs() == {}


def test_apply_section_attrs_traverse_false_is_stored(controller_with_parser):
    controller_with_parser.apply_section_attrs(traverse=False)
    assert controller_with_parser.get_section_attrs() == {'traverse': False}

    controller_with_parser.apply_section_attrs(traverse=True)
    assert controller_with_parser.get_section_attrs() == {}


def test_apply_section_attrs_drops_legacy_no_traverse(controller_with_parser):
    controller_with_parser._section_attrs = [{'no_traverse': True}]
    controller_with_parser.apply_section_attrs(traverse=False)
    assert controller_with_parser.get_section_attrs() == {'traverse': False}


def test_apply_section_attrs_round_trips_through_save(
        controller_with_parser, active_deps, tmp_path):
    controller_with_parser.active_deps.extend(active_deps)
    controller_with_parser.apply_section_attrs(namespace='ns1', build_only=True)
    toml_path = tmp_path / 'rbbuild.toml'

    controller_with_parser.save_file(toml_path)

    text = toml_path.read_text()
    assert 'namespace = "ns1"' in text
    assert 'build_only = true' in text


# --- comment preservation / editing ---

def test_open_file_captures_leading_and_inline_comments(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        '[dependencies]\n'
        'deps = [\n'
        '    # pinned for CVE-1234\n'
        '    "pkg1-1.0.0", # do not upgrade\n'
        '    "pkg2-1.0.0",\n'
        ']\n')

    controller_with_parser.open_file(toml_path)

    by_name = {pkg.name: pkg for pkg in controller_with_parser.active_deps}
    assert controller_with_parser.get_comment(by_name['pkg1']) == 'pinned for CVE-1234'
    assert controller_with_parser.get_comment(by_name['pkg2']) == ''


def test_save_file_round_trips_comments(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        '[dependencies]\n'
        'deps = [\n'
        '    # pinned for CVE-1234\n'
        '    "pkg1-1.0.0", # do not upgrade\n'
        ']\n')

    controller_with_parser.open_file(toml_path)
    controller_with_parser.save_file()

    text = toml_path.read_text()
    assert '# pinned for CVE-1234' in text
    assert '"pkg1-1.0.0", # do not upgrade' in text


def test_apply_comment_sets_leading_comment_for_selected_package(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text('[dependencies]\ndeps = ["pkg1-1.0.0"]\n')
    controller_with_parser.open_file(toml_path)
    controller_with_parser.select(0)

    controller_with_parser.apply_comment('a new note')

    pkg = controller_with_parser.active_deps[0]
    assert controller_with_parser.get_comment(pkg) == 'a new note'


def test_apply_comment_clears_comment_when_blank(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        '[dependencies]\n'
        'deps = [\n'
        '    # pinned for CVE-1234\n'
        '    "pkg1-1.0.0",\n'
        ']\n')
    controller_with_parser.open_file(toml_path)
    controller_with_parser.select(0)

    controller_with_parser.apply_comment('')

    pkg = controller_with_parser.active_deps[0]
    assert controller_with_parser.get_comment(pkg) == ''


def test_apply_comment_preserves_inline_comment(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        '[dependencies]\ndeps = ["pkg1-1.0.0", # do not upgrade\n]\n')
    controller_with_parser.open_file(toml_path)
    controller_with_parser.select(0)

    controller_with_parser.apply_comment('a leading note')
    controller_with_parser.save_file()

    text = toml_path.read_text()
    assert '# a leading note' in text
    assert '# do not upgrade' in text


def test_apply_comment_noop_when_nothing_selected(controller_with_parser):
    controller_with_parser.apply_comment('some text')
    assert controller_with_parser._entry_comments == {}


def test_remove_selected_discards_its_comment(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        '[dependencies]\n'
        'deps = [\n'
        '    # pinned for CVE-1234\n'
        '    "pkg1-1.0.0",\n'
        ']\n')
    controller_with_parser.open_file(toml_path)
    controller_with_parser.select(0)

    controller_with_parser.remove_selected()

    assert controller_with_parser._entry_comments == {}


# A section whose deps array is empty except for a fully commented-out
# example line (e.g. rbbuild's own pyproject.toml 'sonar' sections) must
# not lose that comment on open/save - it has no package to attach to, so
# it's tracked per-section rather than per-entry.
def test_open_file_and_save_file_preserve_trailing_comment_in_empty_section(controller_with_parser, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        '[[dependencies]]\n'
        "namespace = 'sonar'\n"
        'deps = [\n'
        "#    'sample-sources:sonar_build_wrapper-6.7-linux-x86',\n"
        ']\n'
        "restrict_platform = 'linux'\n")

    controller_with_parser.open_file(toml_path)
    assert controller_with_parser._section_trailing_comments == {
        0: ["'sample-sources:sonar_build_wrapper-6.7-linux-x86',"],
    }

    controller_with_parser.save_file()

    text = toml_path.read_text()
    assert "# 'sample-sources:sonar_build_wrapper-6.7-linux-x86'," in text
    assert 'deps = []' not in text

