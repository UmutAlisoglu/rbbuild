# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .cmake import CMake, MakeTool
from .ctest import CTest
from .deps_file import DepsFile
from .npm import NPM
from .packaging import Packaging
from .pypa import PyPA
from .pytest import PyTest
from .rbbuild_class import RBBuild
from .ruff import Ruff


class BuildSystemContainer(containers.DeclarativeContainer):
    config     = providers.Configuration()
    core       = providers.DependenciesContainer()
    deps       = providers.DependenciesContainer()
    package    = providers.DependenciesContainer()
    repository = providers.DependenciesContainer()
    resolver   = providers.DependenciesContainer()

    deps_file = providers.Singleton(
        DepsFile,
        deps_parser = deps.parser,
        resolver    = resolver.resolver,
    )

    packaging = providers.Singleton(
        Packaging,
        packaging_config = config.packaging,
        paths            = core.paths,
    )

    rbbuild = providers.Singleton(
        RBBuild,
        settings            = core.settings,
        paths               = core.paths,
        deps_file           = deps_file,
        resolver            = resolver.resolver,
        rbbuild_config      = config.rbbuild,
        packaging           = packaging,
        dependencies_config = config.dependencies,
        manifest            = package.manifest,
        repoman             = repository.repoman,
        metadata            = package.metadata,
        profile_supplier    = config.profile.supplier,
    )

    maketool = providers.Singleton(
        MakeTool,
        settings        = core.settings,
        paths           = core.paths,
        cmake_generator = 'Ninja',
        toolchain       = core.toolchain,
    )

    cmake = providers.Singleton(
        CMake,
        settings      = core.settings,
        paths         = core.paths,
        maketool      = maketool,
        cmake_config  = config.cmake,
        metadata      = package.metadata,
    )

    ctest = providers.Singleton(
        CTest,
        settings = core.settings,
        paths    = core.paths,
        maketool = maketool,
        metadata = package.metadata,
    )

    pytest = providers.Singleton(
        PyTest,
        paths     = core.paths,
        toolchain = core.toolchain,
        op_mode   = config.op_mode,
    )

    ruff = providers.Singleton(
        Ruff,
        paths               = core.paths,
        profile_ruff_config = config.profile.ruff_config,
    )

    pypa = providers.Singleton(
        PyPA,
        paths                  = core.paths,
        remote_services_config = config.profile.services,
        user_config            = config.service,
        uv_config              = config.profile.uv,
        packaging              = packaging,
        metadata               = package.metadata,
        toolchain              = core.toolchain,
    )

    npm = providers.Singleton(
        NPM,
        paths=core.paths,
    )

