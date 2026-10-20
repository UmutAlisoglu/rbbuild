# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .channel import Channel
from .paths import Paths
from .runtime_settings import RuntimeSettings
from .temp_folder import TempFolder
from .toolchain import Toolchain, default_tcid, selected_tcid, target_tcid


class Core(containers.DeclarativeContainer):
    config = providers.Configuration()

    platform = config.settings.platform
    default_toolchain_id = providers.Callable(default_tcid, config.settings, platform)
    toolchain = providers.Factory(
        Toolchain,
        tcid              = providers.Callable(
            selected_tcid, config.settings.toolchain, default_toolchain_id, config.settings.toolchain_required),
        toolchains_config = config.profile.toolchains,
    )
    toolchain_factory = toolchain.provider
    target_toolchain = providers.Factory(
        Toolchain,
        tcid              = providers.Callable(target_tcid, config.settings.toolchain, default_toolchain_id),
        toolchains_config = config.profile.toolchains,
    )
    channel = providers.Factory(
        Channel,
        name            = config.settings.channel,
        default_channel = config.settings.default_channel,
        channels_config = config.profile.channels,
        source_path     = config.paths.source,
    )
    channel_factory = channel.provider

    paths = providers.Singleton(
        Paths,
        rbbuild_root   = config.paths.rbbuild_root,
        source         = config.paths.source,
        staging_root   = config.paths.staging_root,
        build_root     = config.paths.build_root,
        documentation_root = config.paths.documentation_root,
        dist           = config.paths.dist,
        install_prefix = config.paths.install_prefix,
        toolchain      = toolchain,
    )

    temp_folder = providers.Singleton(
        TempFolder,
        path = config.paths.temp,
    )

    settings = providers.Singleton(
        RuntimeSettings,
        profile_name        = config.settings.profile,
        profile_version     = config.settings.profile_version,
        channel             = channel,
        platform            = platform,
        toolchain           = toolchain,
        op_mode             = config.op_mode,
        skipped_components  = config.skipped_components,
        filtered_components = config.filtered_components,
    )

