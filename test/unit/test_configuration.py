# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from pathlib import Path

from rbbuild.container.configuration import RBBuildConfiguration
from rbbuild.core.toolchain import default_tcid, selected_tcid, target_tcid

# Unit tests for RBBuildConfiguration.load_project_configuration.
#
# Both pyproject.toml and rbbuild.toml are loaded by load_project_configuration.
# In pyproject.toml, rbbuild-specific sections are nested under [tool.rbbuild.*].
# In rbbuild.toml, the same sections appear at the top level ([rbbuild], [cmake], …).
#
# The internal DI key layout after loading is:
#   pyproject.toml [project]                       -> cfg.project.*
#   pyproject.toml [tool.rbbuild.version]          -> cfg.project.version_major / _minor / …
#   pyproject.toml [tool.rbbuild]                  -> cfg.rbbuild.*
#   pyproject.toml [tool.rbbuild.cmake]            -> cfg.cmake.*
#   pyproject.toml [tool.rbbuild.oss]              -> cfg.oss.*
#   pyproject.toml [tool.rbbuild.packaging.*]      -> cfg.packaging.*
#   pyproject.toml [tool.rbbuild.pandoc.*]         -> cfg.pandoc.*
#   pyproject.toml [tool.rbbuild.sphinx.*]         -> cfg.sphinx.*
#   pyproject.toml [tool.rbbuild.dependencies]     -> cfg.dependencies()
#   rbbuild.toml [dependencies] / [[dependencies]] -> cfg.dependencies()


# Write config files to tmp_path and call load_project_configuration.
def _load_cfg(tmp_path, pyproject_text=None, rbbuild_text=None):
    if pyproject_text:
        (tmp_path / 'pyproject.toml').write_text(pyproject_text)
    if rbbuild_text:
        (tmp_path / 'rbbuild.toml').write_text(rbbuild_text)
    cfg = RBBuildConfiguration()
    cfg.load_project_configuration(tmp_path)
    return cfg


# ---------------------------------------------------------------------------
# [project] — package identity
# ---------------------------------------------------------------------------

def test_project_name(tmp_path):
    cfg = _load_cfg(tmp_path, '[project]\nname = "mypkg"\n')
    assert cfg.project.name() == 'mypkg'


def test_project_version(tmp_path):
    cfg = _load_cfg(tmp_path, '[project]\nname = "mypkg"\nversion = "1.2"\n')
    assert cfg.project.version() == '1.2'


def test_project_authors(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        'authors = [{name = "Alice", email = "alice@example.com"}]\n',
    )
    assert cfg.project.authors() == [{'name': 'Alice', 'email': 'alice@example.com'}]


def test_project_license(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        'license = {text = "MIT"}\n',
    )
    assert cfg.project.license() == {'text': 'MIT'}


# ---------------------------------------------------------------------------
# [tool.rbbuild.version] — version fields
# ---------------------------------------------------------------------------

def test_version_major_minor(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.version]\nmajor = 3\nminor = 7\n',
    )
    assert cfg.project.version_major() == 3
    assert cfg.project.version_minor() == 7


def test_version_revision_build(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.version]\nrevision = 99\nbuild = 42\n',
    )
    assert cfg.project.version_revision() == 99
    assert cfg.project.version_build() == 42


def test_version_branch(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.version]\nbranch = "main"\n',
    )
    assert cfg.project.branch() == 'main'


def test_version_string_override(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.version]\nversion = "5.6"\n',
    )
    assert cfg.project.version() == '5.6'


# ---------------------------------------------------------------------------
# [tool.rbbuild] / [rbbuild] — build configuration
# ---------------------------------------------------------------------------

def test_rbbuild_build_tools(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild]\nbuild_tools = ["cmake", "rbbuild"]\n',
    )
    assert cfg.rbbuild.build_tools() == ['cmake', 'rbbuild']


def test_rbbuild_build_tools_hyphen(tmp_path):
    # 'build-tools' (hyphen) must be treated as equivalent to 'build_tools'
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild]\nbuild-tools = ["cmake", "rbbuild"]\n',
    )
    assert cfg.rbbuild.build_tools() == ['cmake', 'rbbuild']


def test_rbbuild_documentation_tools(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild]\ndocumentation_tools = ["pandoc", "sphinx"]\n',
    )
    assert cfg.rbbuild.documentation_tools() == ['pandoc', 'sphinx']


def test_rbbuild_documentation_tools_hyphen(tmp_path):
    # 'documentation-tools' (hyphen) must be treated as equivalent to 'documentation_tools'
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild]\ndocumentation-tools = ["pandoc", "sphinx"]\n',
    )
    assert cfg.rbbuild.documentation_tools() == ['pandoc', 'sphinx']


def test_rbbuild_actions(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild]\nactions = ["setup", "build"]\n',
    )
    assert cfg.rbbuild.actions() == ['setup', 'build']


def test_rbbuild_test_tools_and_sca_tools(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild]\ntest-tools = ["ctest", "pytest"]\nsca-tools = ["ruff"]\n',
    )
    assert cfg.rbbuild.test_tools() == ['ctest', 'pytest']
    assert cfg.rbbuild.sca_tools() == ['ruff']


# The default configuration (rbbuild.toml) accepts the canonical hyphen keys too
def test_default_config_tool_keys_are_normalized(tmp_path):
    (tmp_path / 'rbbuild.toml').write_text(
        f'[paths]\nuser_config = "{(tmp_path / "user").as_posix()}"\n'
        '[tool.rbbuild]\nbuild-tools = ["cmake"]\nsca-tools = ["ruff"]\n')
    cfg = RBBuildConfiguration()
    cfg.load_configuration(tmp_path, tmp_path)
    assert cfg.tool.rbbuild.build_tools() == ['cmake']
    assert cfg.tool.rbbuild.sca_tools() == ['ruff']


def test_shipped_default_config_tools():
    cfg = RBBuildConfiguration()
    cfg.load_configuration(Path('rbbuild'), Path('share/rbbuild/config'))
    assert cfg.tool.rbbuild.build_tools() == ['rbbuild', 'cmake', 'pypa', 'npm']
    assert cfg.tool.rbbuild.sca_tools() == ['ruff']
    assert cfg.tool.rbbuild.test_tools() is None


# ---------------------------------------------------------------------------
# [tool.rbbuild.cmake] / [cmake] — CMake parameters
# ---------------------------------------------------------------------------

def test_cmake_defines(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.cmake]\ncmake_defines = ["BUILD_TESTS=ON", "ARCH=x64"]\n',
    )
    assert cfg.cmake.cmake_defines() == ['BUILD_TESTS=ON', 'ARCH=x64']


# ---------------------------------------------------------------------------
# [tool.rbbuild.oss] / [oss] — OSS scan settings
# ---------------------------------------------------------------------------

def test_oss_users(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.oss]\nusers = ["jdoe", "xyz123"]\n',
    )
    assert cfg.oss.users() == ['jdoe', 'xyz123']


def test_oss_ignore_fields(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.oss]\n'
        'ignore_files = [".gitignore"]\n'
        'ignore_folders = ["unit_test"]\n'
        'ignore_extensions = ["ism"]\n'
        'exclude_dependencies = ["sign_supplicant"]\n',
    )
    assert cfg.oss.ignore_files() == ['.gitignore']
    assert cfg.oss.ignore_folders() == ['unit_test']
    assert cfg.oss.ignore_extensions() == ['ism']
    assert cfg.oss.exclude_dependencies() == ['sign_supplicant']


# ---------------------------------------------------------------------------
# [tool.rbbuild.packaging.*] / [packaging.*] — packaging components
# ---------------------------------------------------------------------------

def test_packaging_component(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.packaging.runtime]\n'
        'files = ["$STAGING/bin/myapp"]\n'
        'suffix = "tar.xz"\n',
    )
    assert cfg.packaging.runtime.files() == ['$STAGING/bin/myapp']
    assert cfg.packaging.runtime.suffix() == 'tar.xz'


# ---------------------------------------------------------------------------
# [tool.rbbuild.pandoc.*] / [pandoc.*] — Pandoc documents
# ---------------------------------------------------------------------------

def test_pandoc_document(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.pandoc.user_manual]\n'
        'files = ["docs/*.md"]\n',
    )
    assert cfg.pandoc.user_manual.files() == ['docs/*.md']


# ---------------------------------------------------------------------------
# [tool.rbbuild.sphinx.*] / [sphinx.*] — Sphinx documents
# ---------------------------------------------------------------------------

def test_sphinx_document(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.sphinx.dev_guide]\n'
        'sourcedir = "docs/source"\n'
        'title = "Developer Guide"\n',
    )
    assert cfg.sphinx.dev_guide.sourcedir() == 'docs/source'
    assert cfg.sphinx.dev_guide.title() == 'Developer Guide'


# ---------------------------------------------------------------------------
# [tool.rbbuild.dependencies] / [dependencies] — dependency list
# ---------------------------------------------------------------------------

# Canonical pyproject.toml form: [tool.rbbuild.dependencies] with deps = [...]
def test_dependencies_list(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.dependencies]\ndeps = ["pkga", "pkgb"]\n',
    )
    assert cfg.dependencies() == [{'deps': ['pkga', 'pkgb']}]


# Section-level attributes (build_only, traverse, …) are preserved as-is.
def test_dependencies_with_section_attrs(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        '[project]\nname = "mypkg"\n'
        '[tool.rbbuild.dependencies]\n'
        'deps = ["pkga"]\n'
        'build_only = 1\n',
    )
    assert cfg.dependencies() == [{'deps': ['pkga'], 'build_only': 1}]


# ---------------------------------------------------------------------------
# Environment variable overrides
# ---------------------------------------------------------------------------

def test_env_package_name_override(tmp_path, monkeypatch):
    monkeypatch.setenv('RBB_PACKAGE_NAME', 'env_name')
    cfg = _load_cfg(tmp_path, '[project]\nname = "original"\n')
    assert cfg.project.name() == 'env_name'


def test_env_branch_name(tmp_path, monkeypatch):
    monkeypatch.setenv('BRANCH_NAME', 'feature-xyz')
    cfg = _load_cfg(tmp_path, '[project]\nname = "mypkg"\n')
    assert cfg.project.branch() == 'feature-xyz'


def test_env_build_number(tmp_path, monkeypatch):
    monkeypatch.setenv('BUILD_NUMBER', '77')
    cfg = _load_cfg(tmp_path, '[project]\nname = "mypkg"\n')
    assert cfg.project.version_build() == '77'


# GITHUB_RUN_NUMBER is used as a fallback when BUILD_NUMBER (Jenkins) is
# not set.
def test_env_github_run_number(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_RUN_NUMBER', '88')
    cfg = _load_cfg(tmp_path, '[project]\nname = "mypkg"\n')
    assert cfg.project.version_build() == '88'


# BUILD_NUMBER (Jenkins) takes precedence over GITHUB_RUN_NUMBER.
def test_env_build_number_takes_precedence_over_github_run_number(tmp_path, monkeypatch):
    monkeypatch.setenv('BUILD_NUMBER', '77')
    monkeypatch.setenv('GITHUB_RUN_NUMBER', '88')
    cfg = _load_cfg(tmp_path, '[project]\nname = "mypkg"\n')
    assert cfg.project.version_build() == '77'


def test_env_package_version(tmp_path, monkeypatch):
    monkeypatch.setenv('RBB_PACKAGE_VERSION', '3.4.5.6')
    cfg = _load_cfg(tmp_path, '[project]\nname = "mypkg"\n')
    assert cfg.project.version() == '3.4.5.6'


# ---------------------------------------------------------------------------
# rbbuild.toml only (non-Python project — no pyproject.toml)
# In rbbuild.toml the sections are at the top level: [project], [rbbuild],
# [cmake], [oss], [packaging.*], [pandoc.*], [sphinx.*], [dependencies].
# ---------------------------------------------------------------------------

def test_rbbuild_toml_project(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text='[project]\nname = "mylib"\nversion = "2.0"\nbranch = "develop"\n',
    )
    assert cfg.project.name() == 'mylib'
    assert cfg.project.version() == '2.0'
    assert cfg.project.branch() == 'develop'


def test_rbbuild_toml_version_fields(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text=(
            '[project]\n'
            'name = "mylib"\n'
            'version_major = 3\n'
            'version_minor = 7\n'
            'version_revision = 50\n'
            'version_build = 9\n'
        ),
    )
    assert cfg.project.version_major() == 3
    assert cfg.project.version_minor() == 7
    assert cfg.project.version_revision() == 50
    assert cfg.project.version_build() == 9


def test_rbbuild_toml_rbbuild_section(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text=(
            '[project]\nname = "mylib"\n'
            '[rbbuild]\n'
            'build_tools = ["cmake"]\n'
            'documentation_tools = ["pandoc"]\n'
            'actions = ["setup", "build", "package"]\n'
        ),
    )
    assert cfg.rbbuild.build_tools() == ['cmake']
    assert cfg.rbbuild.documentation_tools() == ['pandoc']
    assert cfg.rbbuild.actions() == ['setup', 'build', 'package']


def test_rbbuild_toml_rbbuild_section_hyphen_keys(tmp_path):
    # Hyphen-notation keys in rbbuild.toml [rbbuild] must resolve to the same DI keys
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text=(
            '[project]\nname = "mylib"\n'
            '[rbbuild]\n'
            'build-tools = ["cmake"]\n'
            'documentation-tools = ["pandoc"]\n'
        ),
    )
    assert cfg.rbbuild.build_tools() == ['cmake']
    assert cfg.rbbuild.documentation_tools() == ['pandoc']


def test_rbbuild_toml_cmake_section(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text='[project]\nname = "mylib"\n[cmake]\ncmake_defines = ["X=1", "Y=2"]\n',
    )
    assert cfg.cmake.cmake_defines() == ['X=1', 'Y=2']


def test_rbbuild_toml_oss_section(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text=(
            '[project]\nname = "mylib"\n'
            '[oss]\n'
            'users = ["jdoe"]\n'
            'ignore_folders = ["unit_test", ".git"]\n'
            'ignore_extensions = ["ism"]\n'
        ),
    )
    assert cfg.oss.users() == ['jdoe']
    assert cfg.oss.ignore_folders() == ['unit_test', '.git']
    assert cfg.oss.ignore_extensions() == ['ism']


def test_rbbuild_toml_packaging_section(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text=(
            '[project]\nname = "mylib"\n'
            '[packaging.runtime]\n'
            'files = ["$OBJ/bin/mylib.so"]\n'
            'suffix = "tar.xz"\n'
        ),
    )
    assert cfg.packaging.runtime.files() == ['$OBJ/bin/mylib.so']
    assert cfg.packaging.runtime.suffix() == 'tar.xz'


def test_rbbuild_toml_pandoc_section(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text=(
            '[project]\nname = "mylib"\n'
            '[pandoc.user_manual]\n'
            'files = ["docs/*.md"]\n'
        ),
    )
    assert cfg.pandoc.user_manual.files() == ['docs/*.md']


def test_rbbuild_toml_sphinx_section(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text=(
            '[project]\nname = "mylib"\n'
            '[sphinx.api_docs]\n'
            'sourcedir = "source/rst"\n'
            'title = "API Reference"\n'
        ),
    )
    assert cfg.sphinx.api_docs.sourcedir() == 'source/rst'
    assert cfg.sphinx.api_docs.title() == 'API Reference'


def test_rbbuild_toml_dependencies_section(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text=(
            '[project]\nname = "mylib"\n'
            '[dependencies]\n'
            'deps = ["pkga", "pkgb>1.0"]\n'
        ),
    )
    assert cfg.dependencies() == [{'deps': ['pkga', 'pkgb>1.0']}]


# [[dependencies]] (double-bracket) produces a list of section dicts.
def test_rbbuild_toml_dependencies_double_bracket(tmp_path):
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text=(
            '[project]\nname = "mylib"\n'
            '[[dependencies]]\n'
            'deps = ["pkga"]\n'
            'restrict_platform = "linux"\n'
            '[[dependencies]]\n'
            'deps = ["pkgb"]\n'
            'restrict_platform = "win32"\n'
        ),
    )
    result = cfg.dependencies()
    assert len(result) == 2
    assert result[0] == {'deps': ['pkga'], 'restrict_platform': 'linux'}
    assert result[1] == {'deps': ['pkgb'], 'restrict_platform': 'win32'}


# ---------------------------------------------------------------------------
# Interaction: rbbuild.toml and pyproject.toml together
# rbbuild.toml values take precedence over pyproject.toml for the same key.
# Keys present in only one file are preserved unchanged.
# ---------------------------------------------------------------------------

def test_rbbuild_toml_name_overrides_pyproject(tmp_path):
    # rbbuild.toml wins for overlapping [project].name
    cfg = _load_cfg(
        tmp_path,
        pyproject_text='[project]\nname = "py_name"\nversion = "1.0"\n',
        rbbuild_text='[project]\nname = "rbb_name"\n',
    )
    assert cfg.project.name() == 'rbb_name'


def test_pyproject_keys_preserved_when_rbbuild_toml_omits_them(tmp_path):
    # pyproject.toml keys not present in rbbuild.toml survive the merge
    cfg = _load_cfg(
        tmp_path,
        pyproject_text='[project]\nname = "mypkg"\nversion = "1.0"\n',
        rbbuild_text='[project]\nname = "rbb_name"\n',
    )
    assert cfg.project.version() == '1.0'   # from pyproject.toml
    assert cfg.project.name() == 'rbb_name'  # overridden by rbbuild.toml


def test_rbbuild_toml_cmake_alongside_pyproject_project(tmp_path):
    # rbbuild.toml contributes [cmake] while pyproject.toml provides [project]
    cfg = _load_cfg(
        tmp_path,
        pyproject_text='[project]\nname = "mypkg"\nversion = "1.0"\n',
        rbbuild_text='[cmake]\ncmake_defines = ["PLATFORM=linux"]\n',
    )
    assert cfg.project.name() == 'mypkg'
    assert cfg.cmake.cmake_defines() == ['PLATFORM=linux']


def test_rbbuild_section_merged_from_both_files(tmp_path):
    # [tool.rbbuild] in pyproject.toml and [rbbuild] in rbbuild.toml are merged;
    # rbbuild.toml values win for overlapping keys
    cfg = _load_cfg(
        tmp_path,
        pyproject_text=(
            '[project]\nname = "mypkg"\n'
            '[tool.rbbuild]\n'
            'build_tools = ["cmake"]\n'
            'actions = ["setup", "build"]\n'
        ),
        rbbuild_text=(
            '[rbbuild]\n'
            'documentation_tools = ["pandoc"]\n'
            'actions = ["setup", "build", "package"]\n'
        ),
    )
    assert cfg.rbbuild.build_tools() == ['cmake']                      # from pyproject.toml
    assert cfg.rbbuild.documentation_tools() == ['pandoc']             # from rbbuild.toml
    assert cfg.rbbuild.actions() == ['setup', 'build', 'package']     # rbbuild.toml wins


# ---------------------------------------------------------------------------
# Absent config files and missing fields
#
# When a field is not set in any config file, load_project_configuration
# leaves the DI value as None.  The caller (Metadata) is then responsible
# for deriving the value automatically — e.g. name and branch from the git
# remote, revision from the current date, and version defaulting to "0.0".
# ---------------------------------------------------------------------------

def test_no_config_files_does_not_raise(tmp_path):
    # Neither pyproject.toml nor rbbuild.toml — must not raise.
    cfg = _load_cfg(tmp_path)
    assert cfg.project.name() is None
    assert cfg.project.version() is None
    assert cfg.project.branch() is None


def test_missing_name_is_none(tmp_path):
    # [project] section present but without 'name' — Metadata will derive it from git.
    cfg = _load_cfg(tmp_path, rbbuild_text='[project]\nversion = "1.0"\n')
    assert cfg.project.name() is None


def test_missing_version_is_none(tmp_path):
    # No 'version' field — Metadata will default to "0.0" and compute revision/build.
    cfg = _load_cfg(tmp_path, rbbuild_text='[project]\nname = "mylib"\n')
    assert cfg.project.version() is None


def test_missing_branch_is_none(tmp_path):
    # No 'branch' field — Metadata will read it from the git HEAD (or use "local").
    cfg = _load_cfg(tmp_path, rbbuild_text='[project]\nname = "mylib"\n')
    assert cfg.project.branch() is None


def test_missing_version_digits_are_none(tmp_path):
    # Individual version components absent — Metadata computes them from 'version' or time.
    cfg = _load_cfg(tmp_path, rbbuild_text='[project]\nname = "mylib"\nversion = "1.2"\n')
    assert cfg.project.version_major() is None
    assert cfg.project.version_minor() is None
    assert cfg.project.version_revision() is None
    assert cfg.project.version_build() is None


def test_pyproject_without_rbbuild_section(tmp_path):
    # Python project with only [project] — rbbuild/cmake/oss sections are all absent.
    cfg = _load_cfg(tmp_path, '[project]\nname = "pypkg"\nversion = "0.1"\n')
    assert cfg.project.name() == 'pypkg'
    assert cfg.rbbuild.build_tools() is None
    assert cfg.cmake.cmake_defines() is None
    assert cfg.oss.users() is None


def test_rbbuild_toml_without_project_section(tmp_path):
    # rbbuild.toml that only configures build tools — project fields are all absent.
    cfg = _load_cfg(
        tmp_path,
        rbbuild_text='[rbbuild]\nbuild_tools = ["cmake"]\n',
    )
    assert cfg.rbbuild.build_tools() == ['cmake']
    assert cfg.project.name() is None
    assert cfg.project.version() is None


# ---------------------------------------------------------------------------
# $RBB_CONFIG_PATH in config files
# ---------------------------------------------------------------------------

def _write_service_toml(path):
    path.write_text('[profile.services.svc]\nurl = "file:$RBB_CONFIG_PATH/data"\n')
    return path


def test_rbb_config_path_falls_back_to_loaded_config_path(tmp_path, monkeypatch):
    monkeypatch.delenv('RBB_CONFIG_PATH', raising=False)
    cfg = RBBuildConfiguration()
    cfg._rbbuild_config_path = tmp_path
    cfg._load_toml_file(_write_service_toml(tmp_path / 'svc.toml'), profile=False)
    assert cfg.profile.services.svc.url() == f'file:{tmp_path}/data'


def test_rbb_config_path_env_variable_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv('RBB_CONFIG_PATH', '/from/env')
    cfg = RBBuildConfiguration()
    cfg._rbbuild_config_path = tmp_path
    cfg._load_toml_file(_write_service_toml(tmp_path / 'svc.toml'), profile=False)
    assert cfg.profile.services.svc.url() == 'file:/from/env/data'


# ---------------------------------------------------------------------------
# Default toolchain: only build tools that need a toolchain (CMake) select one
# ---------------------------------------------------------------------------

def _default_toolchain(tmp_path, rbbuild_text='[project]\nname = "x"\n', files=(), load_project=True, **cli):
    for name in files:
        (tmp_path / name).write_text('')
    if load_project:
        cfg = _load_cfg(tmp_path, rbbuild_text=rbbuild_text)
    else:
        cfg = RBBuildConfiguration()
    cfg.paths.source.from_value(str(tmp_path))
    cfg.from_dict({'settings': {'toolchain-linux': 'linux-native'}})
    cfg.load_cli(platform='linux', **cli)
    return selected_tcid(
        cfg.settings.toolchain(), default_tcid(cfg.settings(), 'linux'), cfg.settings.toolchain_required())


def test_default_toolchain_is_none_any_without_toolchain_build_tool(tmp_path):
    assert _default_toolchain(tmp_path) == 'none-any'


def test_default_toolchain_with_cmake(tmp_path):
    assert _default_toolchain(tmp_path, files=['CMakeLists.txt']) == 'linux-native'


# The selection does not depend on the type of the project otherwise.
def test_default_toolchain_ignores_packaging_and_dependencies(tmp_path):
    text = (
        '[packaging.wheel]\ntype = "python"\nplatform-specific = true\nfiles = ["x"]\n'
        '\n[dependencies]\ndeps = ["libfoo-1.0"]\n'
    )
    assert _default_toolchain(tmp_path, text, files=['rbbuild-build.sh']) == 'none-any'


def test_default_toolchain_cli_option_wins(tmp_path):
    assert _default_toolchain(tmp_path, tcid='linux-ubuntu-armhf') == 'linux-ubuntu-armhf'


def test_default_toolchain_env_overrides_default(tmp_path, monkeypatch):
    monkeypatch.setenv('RBB_TOOLCHAIN_ID', 'linux-ubuntu-armhf')
    assert _default_toolchain(tmp_path, files=['CMakeLists.txt']) == 'linux-ubuntu-armhf'
    assert _default_toolchain(tmp_path) == 'linux-ubuntu-armhf'


def test_default_toolchain_cli_option_wins_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv('RBB_TOOLCHAIN_ID', 'linux-ubuntu-armhf')
    assert _default_toolchain(tmp_path, tcid='linux-native') == 'linux-native'


# An explicit selection also wins for a project without toolchain.
def test_explicit_none_any_is_selected_for_cmake_project(tmp_path):
    assert _default_toolchain(tmp_path, files=['CMakeLists.txt'], tcid='none-any') == 'none-any'


def test_target_toolchain_is_profile_default_without_explicit_selection():
    assert target_tcid(None, 'linux-native') == 'linux-native'


def test_target_toolchain_is_explicit_selection():
    assert target_tcid('none-any', 'linux-native') == 'none-any'


def _channel_settings(tmp_path, **cli):
    cfg = _load_cfg(tmp_path)
    cfg.load_cli(platform='linux', **cli)
    return cfg.settings.channel()


def test_channel_is_not_selected_without_explicit_selection(tmp_path):
    assert _channel_settings(tmp_path) is None


def test_channel_cli_option_wins_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv('RBB_CHANNEL', 'from-env')
    assert _channel_settings(tmp_path, channel='from-cli') == 'from-cli'


def test_channel_env_selects_channel(tmp_path, monkeypatch):
    monkeypatch.setenv('RBB_CHANNEL', 'from-env')
    assert _channel_settings(tmp_path) == 'from-env'


# ---------------------------------------------------------------------------
# Default toolchain: user config and profile
# ---------------------------------------------------------------------------

def _load_with_user_config(tmp_path, user_settings, profile_settings=''):
    system = tmp_path / 'system'
    user = tmp_path / 'user'
    (system / 'profiles' / 'p').mkdir(parents=True)
    user.mkdir()
    (system / 'rbbuild.toml').write_text(f'[paths]\nuser_config = "{user.as_posix()}"\n')
    (system / 'profiles' / 'p' / 'p.toml').write_text(f'[settings]\n{profile_settings}')
    (user / 'rbbuild.toml').write_text(f'[settings]\n{user_settings}')
    cfg = RBBuildConfiguration()
    cfg.load_configuration(tmp_path, system)
    cfg.load_profile('p', system, user, config_roots=[])
    return cfg


def test_profile_default_toolchain_without_user_default(tmp_path):
    cfg = _load_with_user_config(tmp_path, '', 'toolchain-linux = "linux-a"\n')
    assert cfg.settings()['toolchain-linux'] == 'linux-a'


def test_user_default_toolchain_overrides_profile(tmp_path):
    cfg = _load_with_user_config(
        tmp_path,
        'toolchain-linux = "linux-b"\n',
        'toolchain-linux = "linux-a"\ntoolchain-win32 = "win32-a"\n')
    assert cfg.settings()['toolchain-linux'] == 'linux-b'
    assert cfg.settings()['toolchain-win32'] == 'win32-a'


# rbbuild 5 entries must not select a toolchain explicitly
def test_legacy_toolchain_settings_are_ignored(tmp_path):
    cfg = _load_with_user_config(
        tmp_path, 'toolchain = "linux-native"\ntoolchains = "linux-native"\n', 'toolchain-linux = "linux-a"\n')
    assert cfg.settings.toolchain() is None
    assert 'toolchains' not in cfg.settings()
    assert cfg.settings()['toolchain-linux'] == 'linux-a'


# The build tools of the project configuration decide which files matter.
def test_default_toolchain_cmake_not_in_build_tools(tmp_path):
    text = '[rbbuild]\nbuild_tools = ["pypa"]\n'
    assert _default_toolchain(tmp_path, text, files=['CMakeLists.txt']) == 'none-any'


def test_default_toolchain_cmake_in_build_tools(tmp_path):
    text = '[rbbuild]\nbuild_tools = ["pypa", "cmake"]\n'
    assert _default_toolchain(tmp_path, text, files=['CMakeLists.txt']) == 'linux-native'


# Tools that do not load a project configuration (e.g., promote) keep the
# profile default.
def test_default_toolchain_without_project_configuration(tmp_path):
    assert _default_toolchain(tmp_path, load_project=False) == 'linux-native'
