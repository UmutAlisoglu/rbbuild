# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from types import SimpleNamespace

from rbbuild.docsystem.documentation_runner import DocumentationRunner


def _make_runner(doctools):
    pandoc = SimpleNamespace()
    pandoc.calls = 0

    def pandoc_build_documentation(deps_map, mypkg):
        pandoc.calls += 1
        yield 'pandoc-output'

    pandoc.build_documentation = pandoc_build_documentation

    sphinx = SimpleNamespace()
    sphinx.calls = 0

    def sphinx_build_documentation(deps_map, mypkg):
        sphinx.calls += 1
        yield 'sphinx-output'

    sphinx.build_documentation = sphinx_build_documentation

    runner = DocumentationRunner(
        rbbuild_config={'documentation_tools': doctools},
        pandoc=pandoc,
        sphinx=sphinx,
    )
    return runner, pandoc, sphinx


def test_runner_skips_all_backends_when_no_tools_configured():
    runner, pandoc, sphinx = _make_runner([])

    runner.build_documentation(SimpleNamespace())

    assert pandoc.calls == 0
    assert sphinx.calls == 0


def test_runner_calls_only_configured_pandoc_backend():
    runner, pandoc, sphinx = _make_runner(['pandoc'])

    runner.build_documentation(SimpleNamespace())

    assert pandoc.calls == 1
    assert sphinx.calls == 0


def test_runner_calls_both_configured_backends():
    runner, pandoc, sphinx = _make_runner(['pandoc', 'sphinx'])

    runner.build_documentation(SimpleNamespace())

    assert pandoc.calls == 1
    assert sphinx.calls == 1
