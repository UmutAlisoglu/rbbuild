# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# 'no_traverse' is the legacy spelling of 'traverse=0'.
def resolve_traverse(traverse: Optional[bool], no_traverse: Optional[bool]) -> bool:
    if traverse is not None and no_traverse is not None and bool(traverse) == bool(no_traverse):
        raise SyntaxError('"traverse" contradicts the legacy attribute "no_traverse"')
    if traverse is not None:
        return bool(traverse)
    if no_traverse is not None:
        return not no_traverse
    return True


@dataclass
class Component:
    name: str
    suffix: str
    filename: str = field(default=None, repr=False, compare=False, hash=False)
    checksum: str = field(default=None, repr=False, compare=False, hash=False)
    localpath: Path = field(default=None, repr=False, compare=False, hash=False)
    build_only: bool = field(default=False, repr=False, compare=False, hash=False)
    traverse: bool = field(default=True, repr=False, compare=False, hash=False)


    def __hash__(self) -> int:
        return hash((self.name, self.suffix))

