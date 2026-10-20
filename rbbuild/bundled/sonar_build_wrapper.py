# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import sys
from pathlib import Path

from rbbuild.bundled.base import BundledBase


class SonarBuildWrapper(BundledBase):
    def __init__(self, settings):
        search_path = None

        if (settings.rbbuild_root_path / '.git').exists():
            search_path = Path('staging/*/sonar/build-wrapper-*')

        super().__init__(settings, search_path)
        self.build_path = self.settings.build_path / 'sonar'
        if sys.platform == 'win32':
            self.build_wrapper_exe = self.executable('build-wrapper-win-x86-64.exe')
        else: # Linux
            self.build_wrapper_exe = self.executable('build-wrapper-linux-x86-64')


    def cmdline(self):
        # must be /, also on Windows
        build_path = str(self.build_path).replace('\\', '/')
        return [ str(self.build_wrapper_exe),
                 '--out-dir',
                 build_path ]


    def meta_files_exist(self):
        return (self.build_path / 'build-wrapper-dump.json').exists()

