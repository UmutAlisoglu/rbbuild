# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from importlib.metadata import entry_points
from importlib.util import find_spec
from pathlib import Path
from typing import List

from rbbuild.librbb.term import term


ENTRY_POINT_GROUP = 'rbbuild.config'


# Returns the directories of packages registered under the "rbbuild.config"
# entry-point group (by installed profile packages). Each directory may contain
# 'profiles/' and 'remote-services/' folders. The order is by entry-point name,
# so that later roots deterministically win over earlier ones.
def load_config_roots() -> List[Path]:
    roots = []
    for ep in sorted(entry_points(group=ENTRY_POINT_GROUP), key=lambda e: e.name):
        try:
            spec = find_spec(ep.module)
        except (ImportError, ValueError) as e:
            term.warning(f'[{ENTRY_POINT_GROUP}]', f'Cannot locate {ep.name} ({ep.value}): {e}')
            continue
        locations = spec.submodule_search_locations if spec else None
        if not locations:
            term.warning(f'[{ENTRY_POINT_GROUP}]', f'{ep.name} ({ep.value}) is not a package')
            continue
        root = Path(list(locations)[0])
        if root not in roots:
            roots.append(root)
    return roots
