# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .bitbucket import Bitbucket
from .github import GitHub
from .manager import SCMManager


class SCMContainer(containers.DeclarativeContainer):
    config  = providers.Configuration()
    core    = providers.DependenciesContainer()

    bitbucket = providers.Factory(Bitbucket)

    github = providers.Factory(GitHub)

    # https://refactoring.guru/design-patterns/facade
    scmman = providers.Singleton(
        SCMManager,
        services_config   = config.profile.services,
        user_config       = config.service,  # user overrides and credentials
        # **providers (GitRepository factories)
        bitbucket         = bitbucket.provider,
        github            = github.provider,
    )

