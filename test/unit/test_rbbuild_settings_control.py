# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

from rbbuild.ui.config.rbbuild_control import RbbuildSettingsController


@pytest.fixture
def controller():
    return RbbuildSettingsController()


# --- construction / new_document() ---

def test_construction_has_empty_defaults(controller):
    assert controller.actions == []
    assert controller.build_tools == []
    assert controller.documentation_tools == []
    assert controller.test_tools == []
    assert controller.sca_tools == []
    assert controller.loaded_path is None


def test_new_document_resets_fields_populated_by_open_file(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text('[rbbuild]\nactions = ["setup", "build"]\n')
    controller.open_file(toml_path)

    controller.new_document()

    assert controller.actions == []
    assert controller.loaded_path is None


# --- open_file() / load_from_text() ---

def test_open_file_loads_fields_from_bare_rbbuild_toml(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        '[rbbuild]\n'
        'actions = ["setup", "build"]\n'
        'build_tools = ["cmake"]\n'
        'documentation_tools = ["sphinx"]\n')

    controller.open_file(toml_path)

    assert controller.actions == ['setup', 'build']
    assert controller.build_tools == ['cmake']
    assert controller.documentation_tools == ['sphinx']
    assert controller.loaded_path == toml_path


def test_open_file_loads_fields_from_pyproject_toml_tool_rbbuild(controller, tmp_path):
    toml_path = tmp_path / 'pyproject.toml'
    toml_path.write_text(
        '[tool.rbbuild]\n'
        'actions = ["setup"]\n'
        '\n'
        '[tool.rbbuild.dependencies]\n'
        "deps = ['pkg1-1.0.0']\n")

    controller.open_file(toml_path)

    assert controller.actions == ['setup']
    assert controller.loaded_path == toml_path


def test_open_file_with_no_rbbuild_table_leaves_defaults(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text("[dependencies]\ndeps = ['pkg1-1.0.0']\n")

    controller.open_file(toml_path)

    assert controller.actions == []
    assert controller.loaded_path == toml_path


def test_load_from_text_before_open_uses_target_filename(controller):
    controller.load_from_text('[tool.rbbuild]\nactions = ["setup"]\n', 'pyproject.toml')

    assert controller.actions == ['setup']
    assert controller.loaded_path is None


def test_load_from_text_does_not_touch_loaded_path(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text('[rbbuild]\nactions = ["setup"]\n')
    controller.open_file(toml_path)

    controller.load_from_text('[rbbuild]\nactions = ["build"]\n')

    assert controller.actions == ['build']
    assert controller.loaded_path == toml_path


# --- patch_into_text() ---

def test_patch_into_text_preserves_other_sections(controller):
    controller.actions = ['setup', 'build']
    base_text = "[dependencies]\ndeps = ['pkg1-1.0.0']\n"

    result = controller.patch_into_text(base_text, 'rbbuild.toml')

    assert '[dependencies]' in result
    assert 'pkg1-1.0.0' in result
    assert 'actions = ["setup", "build"]' in result


def test_patch_into_text_preserves_tool_rbbuild_dependencies(controller):
    base_text = (
        '[tool.rbbuild.dependencies]\n'
        "deps = ['pkg1-1.0.0']\n")
    controller.actions = ['setup']

    result = controller.patch_into_text(base_text, 'pyproject.toml')

    assert 'pkg1-1.0.0' in result
    assert 'actions = ["setup"]' in result


def test_patch_into_text_removes_cleared_fields(controller):
    base_text = '[rbbuild]\nactions = ["setup"]\nbuild_tools = ["cmake"]\n'
    controller.load_from_text(base_text)
    controller.build_tools = []

    result = controller.patch_into_text(base_text)

    assert 'actions = ["setup"]' in result
    assert 'build_tools' not in result


def test_patch_into_text_drops_empty_rbbuild_table(controller):
    base_text = '[rbbuild]\nactions = ["setup"]\n'
    controller.load_from_text(base_text)
    controller.actions = []

    result = controller.patch_into_text(base_text)

    assert '[rbbuild]' not in result


def test_patch_into_text_does_not_write_to_disk(controller, tmp_path):
    controller.actions = ['setup']
    toml_path = tmp_path / 'rbbuild.toml'

    controller.patch_into_text('')

    assert not toml_path.exists()


# --- render_preview() ---

def test_render_preview_shows_current_fields(controller):
    controller.actions = ['setup', 'build']

    text = controller.render_preview()

    assert '[rbbuild]' in text
    assert 'actions = ["setup", "build"]' in text


def test_render_preview_empty_by_default(controller):
    assert controller.render_preview() == ''


# --- save_file() ---

def test_save_file_writes_rbbuild_table(controller, tmp_path):
    controller.actions = ['setup', 'build']
    toml_path = tmp_path / 'rbbuild.toml'

    controller.save_file(toml_path)

    text = toml_path.read_text()
    assert 'actions = ["setup", "build"]' in text
    assert controller.loaded_path == toml_path


def test_save_file_preserves_other_sections(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text("[dependencies]\ndeps = ['pkg1-1.0.0']\n")
    controller.open_file(toml_path)
    controller.actions = ['setup']

    controller.save_file()

    text = toml_path.read_text()
    assert '[dependencies]' in text
    assert 'pkg1-1.0.0' in text
    assert 'actions = ["setup"]' in text


def test_save_file_without_path_or_loaded_path_raises(controller):
    with pytest.raises(ValueError):
        controller.save_file()


# --- test-tools / sca-tools and the canonical hyphen keys ---

def test_open_file_loads_test_and_sca_tools(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text('[rbbuild]\ntest-tools = ["pytest"]\nsca-tools = ["ruff"]\n')

    controller.open_file(toml_path)

    assert controller.test_tools == ['pytest']
    assert controller.sca_tools == ['ruff']


def test_patch_into_text_writes_hyphen_keys(controller):
    controller.build_tools = ['cmake']
    controller.documentation_tools = ['sphinx']
    controller.test_tools = ['pytest']
    controller.sca_tools = ['ruff']

    result = controller.patch_into_text('', 'rbbuild.toml')

    assert 'build-tools = ["cmake"]' in result
    assert 'documentation-tools = ["sphinx"]' in result
    assert 'test-tools = ["pytest"]' in result
    assert 'sca-tools = ["ruff"]' in result
    assert '_tools' not in result


def test_patch_into_text_replaces_underscore_key(controller):
    base_text = '[rbbuild]\nbuild_tools = ["cmake"]\n'
    controller.load_from_text(base_text)
    controller.build_tools = ['pypa']

    result = controller.patch_into_text(base_text)

    assert 'build-tools = ["pypa"]' in result
    assert 'build_tools' not in result
