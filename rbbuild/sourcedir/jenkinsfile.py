# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import ast

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ParseState(Enum):
    INIT                 = 1
    RBBUILD_PLUGIN_FOUND = 2   # rbbuild
    BLOCK_ENTERED        = 3   # inside block { ... }
    DONE                 = 4   # left block


@dataclass
class Jenkinsfile:
    path: Path          # path to Jenkinsfile
    _data: dict = None


    @property
    def data(self) -> dict:
        if self._data is None:
            self._data = self._parse(self.path) if self.path.exists() else {}

        return self._data


    def __getitem__(self, key: str) -> dict:
        return self.data[key]


    def __contains__(self, key: str) -> bool:
        return key in self.data


    def get(self, key, default_value=None) -> dict:
        return self.data.get(key, default_value)


    # This is a very simplistic "parser" for our Jenkinsfiles.
    # In essence, we merely want to link configurations in rbbuild.
    def _parse(self, jenkinsfile: Path) -> dict:
        data = {}
        with open(jenkinsfile) as fd:
            lines = list(fd)
            parse_state = ParseState.INIT
            for line in lines:
                if '//' in line:
                    line = line[:line.find('//')]

                # remove whitespaces
                line = line.strip()

                # only consider rbbuild block (gvciPlugin is a legacy alias)
                if line.startswith('rbbuild') or line.startswith('gvciPlugin'):
                    parse_state = ParseState.RBBUILD_PLUGIN_FOUND

                if '{' in line:
                    if parse_state == ParseState.RBBUILD_PLUGIN_FOUND:
                        parse_state = ParseState.BLOCK_ENTERED
                    elif parse_state != ParseState.INIT:
                        raise Exception('parse error')

                    line = line.split('{')[1].strip()

                if parse_state == ParseState.BLOCK_ENTERED:
                    if '}' in line:
                        line, _ = line.split('}')
                        line = line.strip()
                        parse_state = ParseState.DONE

                    # These are the entries we are interested in
                    if '=' in line:
                        key,value = line.split('=', maxsplit=1)
                        key = key.strip()
                        value = ast.literal_eval(value.strip())
                        data[key] = value

        return data

