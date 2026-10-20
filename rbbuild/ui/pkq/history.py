# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pickle
import shutil

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List, Optional


_MAX_ENTRIES = 20
_FILE_NAME = 'gui_state.pickle'


# Persists pkq GUI state (recent queries + last download directory) across
# sessions, as a single pickle file under the user config directory - same
# user trust boundary as rbbuild.librbb.user_config_file.UserConfigFile.
class PkqHistory:

    def __init__(self, user_config_path: Path):
        self._path = Path(user_config_path) / _FILE_NAME
        self._history: List[dict] = []
        self._last_download_dir: Optional[str] = None
        self._load()


    def _load(self):
        try:
            with open(self._path, 'rb') as f:
                state = pickle.load(f)
        except (FileNotFoundError, EOFError, pickle.UnpicklingError):
            return

        self._history = state.get('history', [])
        self._last_download_dir = state.get('last_download_dir')


    def _save(self):
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        state = {'history': self._history, 'last_download_dir': self._last_download_dir}

        with NamedTemporaryFile('wb', delete=False, dir=self._path.parent) as tmpfd:
            pickle.dump(state, tmpfd, protocol=pickle.HIGHEST_PROTOCOL)
            tmpfname = tmpfd.name

        Path(tmpfname).chmod(0o600)
        shutil.move(tmpfname, self._path)


    @property
    def entries(self) -> List[str]:
        return [entry['package'] for entry in self._history]


    def last(self) -> Optional[dict]:
        return self._history[0] if self._history else None


    def find(self, package: str) -> Optional[dict]:
        return next((e for e in self._history if e['package'] == package), None)


    def add(self, package: str, channel: Optional[str], toolchain: Optional[str]):
        if not package:
            return

        entry = {'package': package, 'channel': channel, 'toolchain': toolchain}
        self._history = [entry] + [e for e in self._history if e['package'] != package]
        self._history = self._history[:_MAX_ENTRIES]
        self._save()


    @property
    def last_download_dir(self) -> Optional[str]:
        return self._last_download_dir


    @last_download_dir.setter
    def last_download_dir(self, path: str):
        self._last_download_dir = path
        self._save()
