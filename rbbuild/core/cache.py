#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from enum import Enum

class CacheMode(Enum):
    normal = 0          # synchronize online and only download if the file is not cached
    cache_only = 1      # Never check online
    force = 2           # Never use the cache
    manifest_only = 3   # Only synchronize manifest file

