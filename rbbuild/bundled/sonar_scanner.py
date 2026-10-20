# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import sys
import subprocess

from pathlib import Path

from rbbuild.bundled.base import BundledBase
from rbbuild.librbb.term import term
from rbbuild.package.metadata import Metadata


#@dataclass
#class Sonar:
#    host_url: str
#    project_key: str      # project key per component:  com.bosch.rbbuild.<component>
#    project_prefix: str   # project name per component: PROJECT-<component>
#    login: str = None
#    build_wrapper_enable: bool = False


class SonarScanner(BundledBase):
    def __init__(
        self,
        settings,
        source_path: Path,
        metadata: Metadata,
    ):
        self.source_path = source_path
        if (source_path / '.git').exists():
            search_path = Path('staging/*/sonar/sonar-scanner-*/bin')
        else:
            search_path = None

        self.metadata = metadata

        super().__init__(settings, search_path)


    @property
    def sonar_executable(self):
        if sys.platform == 'win32':
            return self.executable('sonar-scanner.bat')
        else:
            return self.executable('sonar-scanner')


    def run(self, version, sources, tcid, njobs, build_path):
        # Example: {PROJECT}-{linuxvars}
        project_name = f'{self.settings.profile.sonar.project_prefix}-{self.metadata.name}'

        # Example: {com.bosch.rbbuild}.{linuxvars}
        project_key = f'{self.settings.sonar.project_key}.{self.metadata.name}'

        # Example: 3.0.123.4-mybranch-yocto-armhf-2.4
        project_version = f'{str(self.metadata.version)}-{self.metadata.branch}-{tcid}'

        # Example: {linuxvars-3.0.123.4-mybranch-yocto-armhf-2.4
        build_string = f'{self.metadata.name}-{project_version}'

        argv = [
            self.sonar_executable,
            f'-Dsonar.host.url={self.settings.profile.sonar_host_url}',
            f'-Dsonar.login={self.settings.profile.sonar_login}',
             '-Dsonar.cfamily.build-wrapper-output=sonar',
            f'-Dsonar.sources={",".join(sources)}',
            f'-Dsonar.projectName={project_name}',
            f'-Dsonar.projectVersion={project_version}',
            f'-Dsonar.projectBaseDir={self.source_path}',
            f'-Dsonar.projectKey={project_key}',
            f'-Dsonar.buildString={build_string}',
             '-Dsonar.cfamily.cache.enabled=false',
            f'-Dsonar.cfamily.threads={njobs}',
        ]
        if self.metadata.git_branch:
            argv.append(f'-Dsonar.branch.name={self.metadata.git_branch}')

        py_coverage_file = self.settings.build_path / 'Testing/pytest/Coverage.xml'
        if py_coverage_file.exists():
            argv.append(f'-Dsonar.python.coverage.reportPaths={str(py_coverage_file)}')

        if self.verbose:
            term.info(argv)
        proc = subprocess.run(argv, cwd=build_path)

        if proc.returncode != 0:
            raise RuntimeError(f'Command failed with error code {proc.returncode}:\n  {" ".join(argv)}')

