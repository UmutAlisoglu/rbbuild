# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .staging_folder import StagingFolder
from .staging_index_db import StagingIndexDB


class SourceDir(containers.DeclarativeContainer):
    core       = providers.DependenciesContainer()
    package    = providers.DependenciesContainer()
    repository = providers.DependenciesContainer()

    staging_index_db = providers.Singleton(
        StagingIndexDB,
        paths    = core.paths,
        manifest = package.manifest,
    )
    staging_folder = providers.Singleton(
        StagingFolder,
        toolchain = core.toolchain,
        index_db  = staging_index_db,
        paths     = core.paths,
        repoman   = repository.repoman,
    )

