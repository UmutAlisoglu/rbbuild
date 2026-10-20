# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import functools
import json
import os
import shutil
import subprocess

from copy import copy
from pathlib import Path
from typing import Dict

from rbbuild.core.paths import Paths
from rbbuild.package.package import Package
from rbbuild.librbb.term import term
from rbbuild.sourcedir.staging_folder import StagingFolder


class NPM:
    def __init__(self, paths: Paths):
        self.paths: Paths = paths


    @property
    def npm_dist_path(self) -> Path:
        return self.paths.dist / 'npm'


    @property
    def package_json(self) -> Path:
        return self.paths.source / 'package.json'


    @property
    def package_lock_json(self) -> Path:
        return self.paths.source / 'package-lock.json'


    def execute_npm(self, npmcmd, *args, capture_output=False):
        environ = copy(os.environ)
        environ.update({ 'npm_config_cache': str(self.npm_dist_path),
                         'save-exact': 'true',   # exact versions in package-lock.json
                         })

        argv = ['npm', npmcmd, *args]
        proc = subprocess.run(argv, env=environ, capture_output=capture_output)
        if proc.returncode != 0:
            raise RuntimeError('Command failed: ', ' '.join(argv))
        return proc


    def setup(self, install_prefix: Path):
        pass


    def fetch(self, mypkg: Package, fi_hint: bool) -> Dict[str, Package]:
        packages = {}
        self.execute_npm('install')
        packages = self.dependencies

        return packages


    def install_deps(
        self,
        mypkg: Package,
        staging_folder: StagingFolder,
        install_prefix: Path,
        fi_hint: bool,
    ):
        if not self.dependencies:
            term.warning('No packages found. Dependency file does not exist?')
            return

        self.execute_npm('install')

        return self.dependencies


    def build(self, target: str=None, njobs=None):
        with open(self.package_json, 'r') as jfd:
            data = json.load(jfd)
            if not data.get('scripts', {}).get('build'):
                term.info('npm: no build script defined in package.json')
                return
        self.execute_npm('run', 'build')


    def package(self, mypkg: Package):
        self.execute_npm('run', 'pack')
        # TODO: update mypkg.components, ...


    def clean(self, remove_staging: bool):
        self.package_lock_json.unlink(missing_ok=True)
        if remove_staging:
            shutil.rmtree(self.paths.source / 'node_modules', ignore_errors=True)


    @functools.cached_property
    def dependencies(self) -> dict:
        dependencies = {}
        if self.package_lock_json.exists():
            # TODO!!!
            pass

        return dependencies


    @property
    def available(self) -> bool:
        return self.package_json.exists()

