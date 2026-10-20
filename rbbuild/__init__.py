# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import sys
from pathlib import Path


# Returns the path to the rbbuild shared data directory.
# Installed wheel: {sys.prefix}/share/rbbuild/
# Editable / development install: share/rbbuild/ next to the project root
#
# The editable case is detected by location (package_dir outside sys.prefix),
# not by checking whether {sys.prefix}/share/rbbuild happens to exist - a
# stale copy can be left behind under sys.prefix from an earlier, unrelated
# non-editable install of rbbuild in the same environment, and must never be
# preferred over the live source tree in that case.
def data_path() -> Path:
    package_dir = Path(__file__).resolve().parent
    source_data = package_dir.parent / 'share' / 'rbbuild'

    if not package_dir.is_relative_to(Path(sys.prefix).resolve()):
        return source_data

    installed = Path(sys.prefix) / 'share' / 'rbbuild'
    return installed if installed.is_dir() else source_data
