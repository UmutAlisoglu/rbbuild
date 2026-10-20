# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock

from rbbuild.__main__ import RBBuildMain
from rbbuild.buildsystem.cmake import CMake
from rbbuild.buildsystem.pypa import PyPA

# Unit tests for the selection of build, test and SCA tools in RBBuildMain.


def _tool(available=True):
    tool = MagicMock()
    tool.available = available
    return tool


def _build_tools(build_tools_config, **available):
    tools = {name: _tool(available.get(name, True)) for name in ('cmake', 'pypa', 'npm')}
    rbbuild = MagicMock()
    result = RBBuildMain().build_tools(
        build_tools_config=build_tools_config, rbbuild=rbbuild, **tools)
    return result, tools, rbbuild


def test_build_tools_in_configured_order():
    result, tools, rbbuild = _build_tools(['pypa', 'rbbuild', 'cmake'])
    assert result == [tools['pypa'], rbbuild, tools['cmake']]


def test_build_tools_skip_unavailable_tools():
    result, tools, _ = _build_tools(['cmake', 'npm'], cmake=False)
    assert result == [tools['npm']]


def test_build_tools_ignore_test_and_sca_tools():
    result, _, _ = _build_tools(['pytest', 'ruff'])
    assert result == []


def test_tool_list_prefers_project_config():
    main = RBBuildMain()
    value = main.tool_list(
        'sca_tools', project_config={'sca_tools': ['a']}, default_config={'sca_tools': ['b']})
    assert value == ['a']


def test_tool_list_empty_project_list_disables_tools():
    main = RBBuildMain()
    value = main.tool_list(
        'sca_tools', project_config={'sca_tools': []}, default_config={'sca_tools': ['b']})
    assert value == []


def test_tool_list_falls_back_to_default_config():
    main = RBBuildMain()
    assert main.tool_list('sca_tools', project_config=None, default_config={'sca_tools': ['b']}) == ['b']
    assert main.tool_list('sca_tools', project_config={}, default_config={}) is None


def _test_tools(config, build_tools=(), ctest_available=True):
    main = RBBuildMain()
    main.build_tools = lambda: list(build_tools)
    main.tool_list = lambda key: None
    ctest = _tool(ctest_available)
    pytest = MagicMock()
    return main.test_tools(config, ctest=ctest, pytest=pytest), ctest, pytest


def test_test_tools_default_to_the_tests_of_the_build_tools():
    result, ctest, pytest = _test_tools(None, [MagicMock(spec=CMake), MagicMock(spec=PyPA)])
    assert result == [ctest, pytest]


def test_test_tools_default_is_empty_without_build_tools():
    assert _test_tools(None)[0] == []


def test_test_tools_default_cmake_project_does_not_run_pytest():
    result, ctest, _ = _test_tools(None, [MagicMock(spec=CMake)])
    assert result == [ctest]


def test_test_tools_configured_pytest_runs_without_pypa():
    result, _, pytest = _test_tools(['pytest'])
    assert result == [pytest]


def test_test_tools_configured_ctest_needs_cmake_project():
    assert _test_tools(['ctest'], ctest_available=False)[0] == []


def test_test_tools_empty_list_runs_nothing():
    assert _test_tools([], [MagicMock(spec=CMake)])[0] == []


def _sca_tools(config, ruff_available=True):
    main = RBBuildMain()
    main.tool_list = lambda key: ['ruff']
    ruff = _tool(ruff_available)
    return main.sca_tools(config, ruff=ruff), ruff


def test_sca_tools_default_to_ruff():
    result, ruff = _sca_tools(None)
    assert result == [ruff]


def test_sca_tools_skip_unavailable_ruff():
    assert _sca_tools(['ruff'], ruff_available=False)[0] == []


def test_sca_tools_empty_list_runs_nothing():
    assert _sca_tools([])[0] == []


def test_static_code_analysis_calls_tools():
    main = RBBuildMain()
    tool = MagicMock()
    main.sca_tools = lambda: [tool]

    main.static_code_analysis()

    tool.static_code_analysis.assert_called_once_with()


def test_static_code_analysis_without_tool_warns(monkeypatch):
    main = RBBuildMain()
    main.sca_tools = lambda: []
    warnings = []
    monkeypatch.setattr('rbbuild.__main__.term.warning', lambda *args, **kwargs: warnings.append(args))

    main.static_code_analysis()

    assert len(warnings) == 1


def test_run_tests_calls_tools():
    main = RBBuildMain()
    tool = MagicMock()
    main.test_tools = lambda: [tool]

    main.run_tests()

    tool.run_tests.assert_called_once_with()
