# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dependency_injector import containers, providers

from .repository.container import RepositoryContainer
from .ci.container import CIContainer
from .issuetracker.container import IssueTrackerContainer
from .scm.container import SCMContainer
from .oss.container import OSSContainer

from .licensedb import LicenseDB


# This container defines all available service factories.
class ServiceContainer(containers.DeclarativeContainer):
    config  = providers.Configuration()
    core    = providers.DependenciesContainer()
    package = providers.DependenciesContainer()
    deps    = providers.DependenciesContainer()

    repository = providers.Container(
        RepositoryContainer,
        config  = config,
        core    = core,
        package = package,
        deps    = deps,
    )

    ci = providers.Container(
        CIContainer,
        config = config,
    )

    issuetracker = providers.Container(
        IssueTrackerContainer,
        config = config,
    )

    scm = providers.Container(
        SCMContainer,
        config = config,
        core   = core,
    )

    oss = providers.Container(
        OSSContainer,
        config = config,
    )

    #licensedb_svc_name = profile_config.get('licensedb', {}).get('remote_service', '')
    #licensedb_svc_cfg  = profile_config.get('services', {}).get(licensedb_svc_name, {})
    licensedb = providers.Factory(
        LicenseDB,
        licensedb_config=config.profile.licensedb,
        remote_services_config=config.profile.services,
        profile_name=config.settings.profile,
    )

