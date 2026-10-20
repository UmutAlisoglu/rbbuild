# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .manager import CIManager
from .jenkins import Jenkins


class CIContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    jenkins = providers.Factory(Jenkins)

    # https://refactoring.guru/design-patterns/facade
    ciman = providers.Singleton(
        CIManager,
        profile_config=config.profile,
        user_config=config.service,   # user overrides and credentials
        # **providers
        jenkins=jenkins.provider,
    )
