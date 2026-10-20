# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import tempfile

from functools import cached_property
from pathlib import Path

class TempFolder:
    def __init__(self, path: Path):
        self._path = path


    @cached_property
    def path(self) -> Path:
        if not self._path:
            return Path(tempfile.mkdtemp(prefix='rbbuild-'))
        else:
            self._path.mkdir(exist_ok=True)
            return self._path


    def __del__(self):
        if self._path:
            if list(self._path.iterdir()):
                raise ResourceWarning(f'Temporary folder "{self._path}" is not empty!')
            self._path.rmdir()

