# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from rbbuild.docsystem.pandoc import Pandoc
from rbbuild.docsystem.sphinx import Sphinx

from .documentation_runner import DocumentationRunner


class DocumentationContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    core = providers.DependenciesContainer()
    issuetracker = providers.DependenciesContainer()

    pandoc = providers.Singleton(
        Pandoc,
        pandoc_config=config.pandoc,
        project_config=config.project,
        paths=core.paths,
    )

    sphinx = providers.Singleton(
        Sphinx,
        sphinx_config=config.sphinx,
        project_config=config.project,
        paths=core.paths,
        issueman=issuetracker.issueman,
    )

    documentation_runner = providers.Singleton(
        DocumentationRunner,
        rbbuild_config=config.rbbuild,
        pandoc=pandoc,
        sphinx=sphinx,
    )
