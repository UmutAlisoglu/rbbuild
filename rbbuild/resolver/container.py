# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .resolver import Resolver


class ResolverContainer(containers.DeclarativeContainer):
    config     = providers.Configuration()
    repository = providers.DependenciesContainer()

    resolver = providers.Singleton(
        Resolver,
        repoman = repository.repoman,
        op_mode = config.op_mode,
    )

