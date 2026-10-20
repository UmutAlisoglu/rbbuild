# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .parser import DepsParser


class Deps(containers.DeclarativeContainer):
    core       = providers.DependenciesContainer()

    parser = providers.Singleton(
        DepsParser,
        platform          = core.platform,
        channel_factory   = core.channel_factory,
        toolchain_factory = core.toolchain_factory,
    )

