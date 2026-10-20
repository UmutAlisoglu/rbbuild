# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import subprocess

from pathlib import Path
from typing import Iterator

from rbbuild.core.paths import Paths
from rbbuild.package.package import Package


class Pandoc:
    def __init__(
        self,
        pandoc_config: dict,
        project_config: dict,
        paths: Paths,
    ):
        self.source_path = paths.source
        self.documentation_path = paths.documentation
        self.pandoc_config = pandoc_config if pandoc_config else {}


    def generate_from_deps(self, deps_map: dict) -> Path:
        deps_md = self.documentation_path / 'deps_diagram.md'

        if 'rbbuild' not in deps_map:
            return None

        if not deps_md.parent.exists():
            deps_md.parent.mkdir(parents=True)

        with open(deps_md, 'w') as fd:
            fd.write( '# Dependencies Package Diagram\n'
                      '```plantuml\n')
            for name, pkg in deps_map['rbbuild'].items():
                fd.write(f'package "{repr(pkg)}" << {pkg.version} >> #lightblue ' + '{\n}\n')
                for dname, dpkg in pkg.dependencies.items():
                    fd.write(f'"{dname}" ..> "{repr(pkg)}" : "<color:green> dynamic"\n')

            fd.write('```\n')

        return deps_md


    def generate_from_manifest(self, mypkg: Package):
        if not mypkg.dependencies:
            return None
        manifest_md = self.documentation_path / 'manifest_diagram.md'
        if not manifest_md.parent.exists():
            manifest_md.parent.mkdir(parents=True)

        with open(manifest_md, 'w') as fd:
            fd.write( '# Manifest Package Diagram\n'
                      '```plantuml\n')
            for child, pkg in mypkg.dependencies.items():
                fd.write(f'package "{repr(pkg)}" << {pkg.version} >> #lightblue ' + '{\n}\n')
                fd.write(f'"{repr(mypkg)}" ..> "{repr(pkg)}" : "<color:green> dynamic"\n')

            fd.write('```\n')

        return manifest_md


    def build_documentation(self, deps_map: dict, mypkg: Package) -> Iterator[Path]:
        self.documentation_path.mkdir(parents=True, exist_ok=True)

        for docname, config in self.pandoc_config.items():
            outfile = self.documentation_path / f'{docname}.pdf'

            argv = ['pandoc',
                    '-o', str(outfile),
                    '--filter', 'pandoc-plantuml']

            for md in config['files']:
                if md == '$GENERATED_DEPS_DIAGRAM':
                    deps_md = self.generate_from_deps(deps_map)
                    if deps_md and deps_md.exists():
                        argv.append(str(deps_md))
                elif md == '$GENERATED_MANIFEST_DIAGRAM':
                    manifest_md = self.generate_from_manifest(mypkg)
                    if manifest_md and manifest_md.exists():
                        argv.append(str(manifest_md))
                else:
                    for p in sorted(self.source_path.glob(md)):
                        argv.append(str(p))

            proc = subprocess.run(argv)
            if proc.returncode != 0:
                raise RuntimeError(f'Command failed: {" ".join(argv)}:\n{proc.stderr}')

            yield outfile
