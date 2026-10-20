# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .fossid import FossID
from .oss_manager import OSSManager


class OSSContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    fossid = providers.Factory(
        FossID,
        op_mode = config.op_mode,
    )

    # https://refactoring.guru/design-patterns/facade
    ossman = providers.Singleton(
        OSSManager,
        profile_config = config.profile,
        user_config    = config.service,  # user overrides and credentials
        oss_config     = config.oss,      # configuration override from rbbuild.toml
        # **providers (OSS service factories, keyed by type name)
        fossid         = fossid.provider,
    )
