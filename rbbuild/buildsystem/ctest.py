# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import functools
import shutil
import subprocess
import sys

from pathlib import Path

from rbbuild.buildsystem.cmake import MakeTool
from rbbuild.core.paths import Paths
from rbbuild.core.runtime_settings import RuntimeSettings
from rbbuild.librbb.term import term
from rbbuild.package.metadata import Metadata


class CTest:
    def __init__(
        self,
        settings: RuntimeSettings,
        paths: Paths,
        maketool: MakeTool,
        metadata: Metadata,
    ):
        self.settings = settings
        self.paths: Paths = paths
        self.maketool = maketool
        self.metadata = metadata


    @functools.cached_property
    def ctest_executable(self):
        found = shutil.which('ctest')
        if found is None:
            found = shutil.which('ctest', path=str(Path(sys.executable).parent))
        return found


    @property
    def available(self) -> bool:
        return (self.paths.source / 'CMakeLists.txt').exists()


    def run_tests(self):
        cmakefiles = self.paths.build / 'CMakeFiles'
        if not cmakefiles.exists():
            raise FileNotFoundError(f'{cmakefiles} not found. Run setup first.')

        argv = [ self.ctest_executable,
                 '-T', 'test',
                 '--no-compress-output',
                 str(self.paths.build) ]

        # Generators for IDEs, such as Visual Studio, support multiple build
        # configurations. For switching between Debug and Release, we need to
        # pass --config Release|Debug.
        if self.maketool.build_config_switch:
            argv = argv + ['--build-config', self.maketool.build_config_switch]

        # -v
        if self.settings.op_mode.verbose:
            argv.append('-V')
            term.info('Build path: %s' % str(self.paths.build))
            term.info('Build commands: ', argv)

        proc = subprocess.run(
            argv,
            bufsize=0,
            env=self.metadata.environ,
            cwd=self.paths.build,
        )
        if proc.returncode != 0:
            raise RuntimeError(f'Command failed with error code {proc.returncode}:\n  {" ".join(argv)}')
