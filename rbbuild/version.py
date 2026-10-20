# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import os
import tomllib

from packaging.version import Version
from pathlib import Path

from rbbuild.package.metadata import Metadata


class RBBuildVersion(Metadata):
    def __init__(self):
        pyproject_toml_path = self.root_path / 'pyproject.toml'
        if (pyproject_toml_path).exists():
            with open(pyproject_toml_path, 'rb') as fd:
                data = tomllib.load(fd)

            v = data['project']['version']
        else:
            from importlib.metadata import version
            v = Version(version("rbbuild"))

        config = {
            'version': str(v),
        }
        if 'BUILD_NUMBER' in os.environ:
            config['version_build'] = os.environ['BUILD_NUMBER']
        elif 'GITHUB_RUN_NUMBER' in os.environ:
            config['version_build'] = os.environ['GITHUB_RUN_NUMBER']

        super().__init__(
            config,
            paths=None,     # NOTE: with this, self.environ must not be called!
            source_path=self.root_path,
        )


    @property
    def root_path(self) -> Path:
        return Path(__file__).resolve().parent.parent


__version__ = str(RBBuildVersion().version)
