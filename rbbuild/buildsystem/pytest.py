# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import functools
import os
import subprocess
import shutil

from pathlib import Path

from rbbuild.core.runtime_settings import OperationMode
from rbbuild.core.paths import Paths
from rbbuild.core.toolchain import Toolchain
from rbbuild.librbb.term import term


class PyTest:
    def __init__(
        self,
        paths: Paths,
        toolchain: Toolchain,
        op_mode: OperationMode,
    ):
        self.paths    = paths
        self.op_mode  = op_mode

        # Pass information to pytest via environment variables.
        # Copy os.environ rather than aliasing it, so this doesn't leak
        # RBB_TOOLCHAIN_ID into the real process environment.
        self.environ = toolchain.apply_python_environment(os.environ.copy())
        self.environ['RBB_TOOLCHAIN_ID'] = str(toolchain)


    @functools.cached_property
    def pytest_executable(self) -> str:
        exe = shutil.which('pytest')
        if not exe:
            raise LookupError('pytest not found')
        return exe


    def run_tests(self):
        if 'RBB_DISABLE_TEST' in os.environ:
            term.info('Skipping pytest. RBB_DISABLE_TEST defined.')
            return False

        argv = [
            self.pytest_executable,
            '-x',
            '--ignore',     str(self.paths.build_root),
            '--ignore',     str(self.paths.staging_root),
            '--junit-xml',  str(self.paths.build / 'Testing/pytest/Test.xml'),
            '--cov',        str(self.paths.source),
            '--cov-report', 'term',
            '--cov-report', f'xml:{str(self.paths.build / "Testing/pytest/Coverage.xml")}',
        ]

        # See https://pytest-cov.readthedocs.io/en/latest/reporting.html
        if 'GITHUB_STEP_SUMMARY' in os.environ:
            argv.extend([
                '--cov-report', f'markdown-append:{os.environ["GITHUB_STEP_SUMMARY"]}',
            ])

        if self.op_mode.verbose:
            term.info(f'Current working directory: {str(Path.cwd())}')
            term.info(f'Environment variables: {self.environ})')
            term.info(f'Command: {" ".join(argv)}')

        proc = subprocess.run(argv, bufsize=0, env=self.environ)

        if self.op_mode.verbose:
            term.info(f'pytest return code: {proc.returncode}')

        # Execution was successful
        if proc.returncode == 0:
            return True

        # No tests found
        elif proc.returncode == 5:
            return False

        raise RuntimeError(f'Failed with error code {proc.returncode}: {" " .join(argv)})')

