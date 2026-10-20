# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from importlib.metadata import entry_points
from typing import Dict, Type

from rbbuild.librbb.term import term

from .repository import Repository


ENTRY_POINT_GROUP = 'rbbuild.repository'


# Loads Repository classes registered by installed packages under the
# "rbbuild.repository" entry-point group. The
# entry-point name is the service type used in profile remote-services.
def load_repository_plugins() -> Dict[str, Type[Repository]]:
    plugins = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            cls = ep.load()
        except Exception as e:
            term.warning(f'[{ENTRY_POINT_GROUP}]', f'Cannot load {ep.name} ({ep.value}): {e}')
            continue
        if not (isinstance(cls, type) and issubclass(cls, Repository)):
            term.warning(f'[{ENTRY_POINT_GROUP}]', f'{ep.name} ({ep.value}) is not a Repository subclass')
            continue
        plugins[ep.name] = cls
    return plugins
