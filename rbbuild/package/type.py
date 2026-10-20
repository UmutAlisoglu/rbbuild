# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from enum import Enum, auto


# Definitions from CycloneDX 1.6: https://cyclonedx.org/docs/1.6/json/#components_items_type
# In CycloneDX, a "package" is also a component. This doesn't really match with the rbbuild
# model, however, we also do not apply a type to a Component.
class PackageType(Enum):
    APPLICATION            = 0        # default, if not defined otherwise
    FRAMEWORK              = auto()
    LIBRARY                = auto()
    CONTAINER              = auto()
    PLATFORM               = auto()
    OPERATING_SYSTEM       = auto()
    DEVICE                 = auto()
    DEVICE_DRIVER          = auto()
    FIRMWARE               = auto()
    FILE                   = auto()
    MACHINE_LEARNING_MODEL = auto()
    DATA                   = auto()
    CRYPTOGRAPHIC_ASSET    = auto()

    # Returns CycloneDX 1.6 strings of a component.type object
    def __str__(self) -> str:
        if self.value == PackageType.OPERATING_SYSTEM:
            return 'operating-system'
        if self.value == PackageType.DEVICE_DRIVER:
            return 'device-driver'
        if self.value == PackageType.MACHINE_LEARNING_MODEL:
            return 'machine-learning-model'
        if self.value == PackageType.CRYPTOGRAPHIC_ASSET:
            return 'cryptographic-asset'
        return self.name.lower()


    @classmethod
    def from_string(cls, value: str) -> 'PackageType':
        if value == 'operating-system':
            return PackageType.OPERATING_SYSTEM
        if value == 'device-driver':
            return PackageType.DEVICE_DRIVER
        if value == 'machine-learning-model':
            return PackageType.MACHINE_LEARNING_MODEL
        if value == 'cryptographic-asset':
            return PackageType.CRYPTOGRAPHIC_ASSET
        return getattr(cls, value.upper())

