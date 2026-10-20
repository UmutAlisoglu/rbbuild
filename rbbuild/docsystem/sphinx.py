# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import subprocess

from pathlib import Path
from string import Template
from typing import Iterator

from rbbuild.core.paths import Paths
from rbbuild.librbb.term import term
from rbbuild.package.package import Package
from rbbuild.service.issuetracker.issuetracker_manager import IssueTrackerManager


class Sphinx:
    def __init__(
        self,
        sphinx_config: dict,
        project_config: dict,
        paths: Paths,
        issueman: IssueTrackerManager,
    ):
        self.source_path = paths.source
        self.documentation_path = paths.documentation
        self.templates_path = paths.templates
        self.project_config = project_config or {}
        self.issueman = issueman

        self.documents = {}
        if sphinx_config:
            for doc, config in sphinx_config.items():
                self.documents[doc] = config


    def _setup(self, mypkg: Package):
        for docname, config in self.documents.items():
            conf_py = self.documentation_path / 'sphinx' / docname / 'conf.py'
            if not conf_py.exists():
                conf_py.parent.mkdir(parents=True, exist_ok=True)
                in_file = self.templates_path / 'sphinx-conf.py.in'
                with open(in_file, 'r') as fd:
                    conf_py_template_content = fd.read()

                authors = self.project_config.get('authors', {})
                author_names = [author['name'] for author in authors]
                template = Template(conf_py_template_content)
                conf_py_content = template.safe_substitute(
                    _RBB_PROJECT_NAME=mypkg.name,
                    _RBB_AUTHOR_NAMES=', '.join(author_names),
                    _RBB_RINOH_AUTHOR_NAMES=r'\n'.join(author_names),
                    _RBB_DOCUMENT_TITLE=config.get('title', mypkg.name),
                    _RBB_VERSION=mypkg.version,
                )

                logo_line = '# logo = logo.png'
                if 'logo' in config:
                    logo_line = f'logo = \'{str(self.source_path / config["logo"])}\''

                conf_py_content = Template(conf_py_content).safe_substitute(
                    _RBB_LOGO_LINE=logo_line,
                )

                with open(conf_py, 'w') as fd:
                    fd.write(conf_py_content)


    def _do_generate_changelog(self, changelog_jira, outfile: Path):
        jira_project_id, jira_release_version = changelog_jira.split(':', maxsplit=1)
        jira_service = self.issueman.service(jira_project_id)
        jira_url = jira_service.url

        with open(outfile, 'w') as fd:
            fd.write(
               f'.. table:: {jira_release_version}\n'
               f'\n'
               f'    {"="*80} {"="*100}\n'
               f'    {"**Ticket ID**":80.80} {"Summary":100.100}\n'
               f'    {"="*80} {"="*100}\n'
            )
            jql = f'project={jira_project_id} AND fixVersion={jira_release_version} ORDER BY key ASC'
            for issue in jira_service.search(query=jql):
                ticket_url = f'`{issue.key} <{jira_url}/browse/{issue.key}>`_'
                fd.write(
                    f'    {ticket_url:80.80} {issue.summary:100.100}\n'
                )

            fd.write(
               f'    {"="*80} {"="*100}\n'
                '\n'
            )

    def _generate_changelog(self):
        self.documentation_path.mkdir(parents=True, exist_ok=True)
        for docname, config in self.documents.items():
            outpath = self.documentation_path / 'sphinx' / docname
            if 'generate_changelog' in config:
                for i, changelog_jira in enumerate(config['generate_changelog']):
                    outfile = outpath / f'changelog_{i}.rst'
                    term.debug('Generating changelog', f'{str(outfile)}: {term.magenta(changelog_jira)}')
                    self._do_generate_changelog(changelog_jira, outfile)


    def build_documentation(self, deps_map: dict, mypkg: Package) -> Iterator[Path]:
        self._setup(mypkg)
        self._generate_changelog()
        self.documentation_path.mkdir(parents=True, exist_ok=True)
        for docname, config in self.documents.items():
            outpath = self.documentation_path / 'sphinx' / docname
            filename = f'{docname}.pdf'

            argv = ['sphinx-build',
                    '-c', str(outpath),
                    config['sourcedir'],
                    str(outpath),
                    '-b', 'rinoh']

            proc = subprocess.run(argv)
            if proc.returncode != 0:
                raise RuntimeError(f'Command failed: {" ".join(argv)}:\n{proc.stderr}')

            yield outpath / filename
