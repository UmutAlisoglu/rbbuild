# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from rbbuild.docsystem.pandoc import Pandoc
from rbbuild.docsystem.sphinx import Sphinx
from rbbuild.package.package import Package


class DocumentationRunner:
    def __init__(self, rbbuild_config: dict, pandoc: Pandoc, sphinx: Sphinx):
        self.rbbuild_config = rbbuild_config if rbbuild_config else {}
        self.pandoc = pandoc
        self.sphinx = sphinx


    def build_documentation(self, mypkg: Package):
        deps_map = {}  # TODO
        doctools = set(self.rbbuild_config.get('documentation_tools', []))

        if 'pandoc' in doctools:
            for _outfile in self.pandoc.build_documentation(deps_map, mypkg):
                pass

        if 'sphinx' in doctools:
            for _outfile in self.sphinx.build_documentation(deps_map, mypkg):
                pass
