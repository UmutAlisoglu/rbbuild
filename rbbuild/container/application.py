# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from rbbuild.buildsystem.container import BuildSystemContainer
from rbbuild.core.container import Core
from rbbuild.deps.container import Deps
from rbbuild.docsystem.container import DocumentationContainer
from rbbuild.generate.container import Generate
from rbbuild.package.container import PackageContainer
from rbbuild.query.container import QueryContainer
from rbbuild.resolver.container import ResolverContainer
from rbbuild.service.container import ServiceContainer
from rbbuild.sourcedir.container import SourceDir


# Container setup is inspired by:
# https://python-dependency-injector.ets-labs.org/examples/application-multiple-containers.html

class Application(containers.DeclarativeContainer):
    config = providers.Configuration()

    core = providers.Container(
        Core,
        config=config,
    )

    generate = providers.Container(
        Generate,
        core = core,
    )

    package = providers.Container(
        PackageContainer,
        config = config,
        core = core,
    )

    deps = providers.Container(
        Deps,
        core       = core,
    )

    service = providers.Container(
        ServiceContainer,
        config  = config,
        core    = core,
        package = package,
        deps    = deps,
    )

    resolver = providers.Container(
        ResolverContainer,
        config     = config,
        repository = service.repository,
    )

    query = providers.Container(
        QueryContainer,
        config     = config,
        repository = service.repository,
        resolver   = resolver,
        deps       = deps,
        package    = package,
    )

    sourcedir = providers.Container(
        SourceDir,
        core       = core,
        package    = package,
        repository = service.repository,
    )

    buildsystem = providers.Container(
        BuildSystemContainer,
        config     = config,
        core       = core,
        deps       = deps,
        package    = package,
        repository = service.repository,
        resolver   = resolver,
    )

    docsystem = providers.Container(
        DocumentationContainer,
        config       = config,
        core         = core,
        issuetracker = service.issuetracker,
    )

