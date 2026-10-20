# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Set


@dataclass
class OperationMode:
    debug: bool
    verbose: bool
    force: bool
    ignore_errors: bool
    dry_run: bool
    offline: bool
    manifest_only: bool
    transitive: bool


# result of compare_packages()
class CompareState(Enum):
    SAME    = 0   # no change
    CHANGED = 1   # same package, but different version
    NEW     = 2   # newly added
    DELETED = 3   # only in previous
    MOVED   = 4   # same package, but different namespace


class DiffMode(IntEnum):
    BASIC       = 0
    COMMITS     = 1
    JIRADETAILS = 2
    GITDETAILS  = 3


@dataclass
class RuntimeSettings:
    profile_name: str
    profile_version: str
    channel: str
    platform: str
    toolchain: str
    op_mode: OperationMode
    filtered_components: Set
    skipped_components: Set


    # Loads and returns profile/component_registry/<pkgman>_components.json
    # The variable "pkgman" is a string that is defined as package URL type, i.e., pkg:<pkgman>/<package>
    #def component_registry(self, pkgman: str) -> dict:
    #    if pkgman not in self._component_registry:
    #        registry_json = self.profile_path / f'component_registry/{pkgman}_components.json'
    #
    #        #if not registry_json.exists():
    #        #    if self.inherited_profile_path:
    #        #        registry_json = self.inherited_profile_path / f'component_registry/{pkgman}_components.json'
    #
    #        if not registry_json.exists():
    #            raise LookupError(f'Component registry file {str(registry_json)} not found')
    #
    #        with open(registry_json, 'r') as jfd:
    #            self._component_registry[pkgman] = json.load(jfd)
    #
    #    return self._component_registry[pkgman]

