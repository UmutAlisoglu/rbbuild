# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .query import Query


class QueryContainer(containers.DeclarativeContainer):
    config     = providers.Configuration()
    repository = providers.DependenciesContainer()
    resolver   = providers.DependenciesContainer()
    deps       = providers.DependenciesContainer()
    package    = providers.DependenciesContainer()

    query = providers.Singleton(
        Query,
        repoman      = repository.repoman,
        resolver     = resolver.resolver,
        deps_parser  = deps.parser,
        package_diff = package.diff,
        op_mode      = config.op_mode,
    )
