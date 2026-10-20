# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .issuetracker_manager import IssueTrackerManager
from .jira import Jira


class IssueTrackerContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    jira = providers.Factory(Jira)

    # https://refactoring.guru/design-patterns/facade
    issueman = providers.Singleton(
        IssueTrackerManager,
        profile_config = config.profile,
        user_config = config.service,  # user overrides and credentials
        # **providers
        jira = jira.provider,
    )



