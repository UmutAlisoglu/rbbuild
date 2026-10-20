# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

from rbbuild.ui.config.project_control import ProjectController


@pytest.fixture
def controller():
    return ProjectController()


# --- construction / new_document() ---

def test_construction_has_empty_defaults(controller):
    assert controller.name is None
    assert controller.branch is None
    assert controller.version is None
    assert controller.authors == []
    assert controller.maintainers == []
    assert controller.license == {}
    assert controller.scripts == {}
    assert controller.gui_scripts == {}
    assert controller.loaded_path is None


def test_new_document_resets_fields_populated_by_open_file(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        '[project]\n'
        'name = "myproject"\n'
        'authors = [{name = "A", email = "a@example.org"}]\n')
    controller.open_file(toml_path)

    controller.new_document()

    assert controller.name is None
    assert controller.authors == []
    assert controller.loaded_path is None


# --- open_file() / load_from_text() ---

def test_open_file_loads_simple_fields(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        '[project]\n'
        'name = "myproject"\n'
        'branch = "main"\n'
        'version = "1.2"\n')

    controller.open_file(toml_path)

    assert controller.name == 'myproject'
    assert controller.branch == 'main'
    assert controller.version == '1.2'
    assert controller.loaded_path == toml_path


def test_open_file_loads_authors_maintainers_license_scripts(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text(
        '[project]\n'
        'authors = [{name = "A", email = "a@example.org"}]\n'
        'maintainers = [{name = "M", email = "m@example.org"}]\n'
        'license = {text = "MIT"}\n'
        'scripts = {rbbuild = "rbbuild.__main__:run"}\n'
        '"gui-scripts" = {myapp-ui = "myapp.gui:main"}\n')

    controller.open_file(toml_path)

    assert controller.authors == [{'name': 'A', 'email': 'a@example.org'}]
    assert controller.maintainers == [{'name': 'M', 'email': 'm@example.org'}]
    assert controller.license == {'text': 'MIT'}
    assert controller.scripts == {'rbbuild': 'rbbuild.__main__:run'}
    assert controller.gui_scripts == {'myapp-ui': 'myapp.gui:main'}


def test_open_file_with_no_project_table_leaves_defaults(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text("[dependencies]\ndeps = ['pkg1-1.0.0']\n")

    controller.open_file(toml_path)

    assert controller.name is None
    assert controller.loaded_path == toml_path


def test_load_from_text_does_not_touch_loaded_path(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text('[project]\nname = "myproject"\n')
    controller.open_file(toml_path)

    controller.load_from_text('[project]\nname = "renamed"\n')

    assert controller.name == 'renamed'
    assert controller.loaded_path == toml_path


# --- patch_into_text() ---

def test_patch_into_text_preserves_other_sections(controller):
    controller.name = 'myproject'
    base_text = "[dependencies]\ndeps = ['pkg1-1.0.0']\n"

    result = controller.patch_into_text(base_text)

    assert '[dependencies]' in result
    assert 'pkg1-1.0.0' in result
    assert 'name = "myproject"' in result


def test_patch_into_text_preserves_unmodeled_project_keys(controller):
    base_text = '[project]\nname = "myproject"\ncustom_key = "keep-me"\n'
    controller.load_from_text(base_text)
    controller.name = 'renamed'

    result = controller.patch_into_text(base_text)

    assert 'name = "renamed"' in result
    assert 'custom_key = "keep-me"' in result


def test_patch_into_text_removes_cleared_fields(controller):
    base_text = '[project]\nname = "myproject"\nbranch = "main"\n'
    controller.load_from_text(base_text)
    controller.branch = None

    result = controller.patch_into_text(base_text)

    assert 'name = "myproject"' in result
    assert 'branch' not in result


def test_patch_into_text_drops_empty_project_table(controller):
    base_text = '[project]\nname = "myproject"\n'
    controller.load_from_text(base_text)
    controller.name = None

    result = controller.patch_into_text(base_text)

    assert '[project]' not in result


def test_patch_into_text_does_not_write_to_disk(controller, tmp_path):
    controller.name = 'myproject'
    toml_path = tmp_path / 'rbbuild.toml'

    controller.patch_into_text('')

    assert not toml_path.exists()


# --- render_preview() ---

def test_render_preview_shows_current_fields(controller):
    controller.name = 'myproject'
    controller.authors = [{'name': 'A', 'email': 'a@example.org'}]

    text = controller.render_preview()

    assert '[project]' in text
    assert 'name = "myproject"' in text
    assert 'authors' in text


def test_render_preview_empty_by_default(controller):
    assert controller.render_preview() == ''


# --- save_file() ---

def test_save_file_writes_project_table(controller, tmp_path):
    controller.name = 'myproject'
    controller.version = '1.2'
    toml_path = tmp_path / 'rbbuild.toml'

    controller.save_file(toml_path)

    text = toml_path.read_text()
    assert 'name = "myproject"' in text
    assert 'version = "1.2"' in text
    assert controller.loaded_path == toml_path


def test_save_file_preserves_other_sections(controller, tmp_path):
    toml_path = tmp_path / 'rbbuild.toml'
    toml_path.write_text("[dependencies]\ndeps = ['pkg1-1.0.0']\n")
    controller.open_file(toml_path)
    controller.name = 'myproject'

    controller.save_file()

    text = toml_path.read_text()
    assert '[dependencies]' in text
    assert 'pkg1-1.0.0' in text
    assert 'name = "myproject"' in text


def test_save_file_without_path_or_loaded_path_raises(controller):
    with pytest.raises(ValueError):
        controller.save_file()
