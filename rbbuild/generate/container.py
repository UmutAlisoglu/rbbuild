# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .project_file_generator import ProjectFileGenerator


class Generate(containers.DeclarativeContainer):
    core = providers.DependenciesContainer()

    project_file_generator = providers.Factory(
        ProjectFileGenerator,
        paths     = core.paths,
        toolchain = core.toolchain,
        settings  = core.settings,
    )
