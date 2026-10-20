# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import tarfile
import zipfile

from pathlib import Path
from typing import List, Tuple

from rbbuild.core.paths import Paths
from rbbuild.package.component import Component, resolve_traverse
from rbbuild.package.package import Package
from rbbuild.librbb.crypto import compute_sha1sum
from rbbuild.librbb.term import term


class Packaging:
    def __init__(self, packaging_config: dict, paths: Paths):
        self._config = packaging_config if packaging_config else {}
        self.paths = paths


    def __bool__(self) -> bool:
        return bool(self._config)


    def items(self):
        return self._config.items()


    # Resolves the set of excluded Paths for a packaging entry.
    # Handles type='python' automatic __pycache__ exclusion.
    def resolve_excluded(self, comp: dict) -> set:
        exclude_patterns = list(comp.get('exclude', []))
        if comp.get('type') == 'python':
            exclude_patterns += ['**/__pycache__', '**/__pycache__/**']
        excluded = set()
        for excl in exclude_patterns:
            excl = self._substitute_file_vars(excl)
            # On Python 3.12+/Windows trailing '**' does not match files; append '/*'
            if excl.endswith('**'):
                excl += '/*'
            excluded.update(Path().glob(excl))
        return excluded


    # Resolves file patterns for a packaging entry into (path, strip, dest) triplets.
    # Each entry in 'files' is either a string or a dict with keys:
    #   src  (mandatory): file path or glob pattern
    #   strip (optional): prefix stripped from each matched path in the archive
    #   dest  (optional): prefix prepended to each archive entry path
    # Patterns matched by 'exclude' are removed from the result.
    # For type='python' entries, __pycache__ directories are automatically excluded.
    def resolve_files(self, cname: str, comp: dict) -> List[Tuple[Path, str, str]]:
        file_patterns = comp.get('files')
        if not file_patterns:
            raise SyntaxError(f'[packaging.{cname}]: missing or empty "files" key')

        excluded = self.resolve_excluded(comp)

        files = []    # list of triplets: file-path, strip, dest
        for entry in file_patterns:
            if isinstance(entry, dict):
                fpattern = entry.get('src')
                if not fpattern:
                    raise SyntaxError(f'[packaging.{cname}]: dict entry missing "src" key')
                strip = entry.get('strip')
                if strip:
                    strip = self._substitute_file_vars(strip)
                dest  = entry.get('dest', '')
            else:
                fpattern = entry
                strip = None
                dest  = ''

            f = self._substitute_file_vars(fpattern)
            # On Python 3.12+/Windows trailing '**' does not match files; append '/*'
            if f.endswith('**'):
                f += '/*'

            globbed_list = [g for g in Path().glob(f) if g not in excluded]
            if not globbed_list:
                term.warning(f'[packaging.{cname}]', f'File pattern not found: {term.bright_white(f)}')
                continue

            for g in globbed_list:
                files.append((g, strip, dest))

        return files


    # Resolves shared-data patterns for a packaging entry into (path, strip, dest) triplets.
    # Each entry in 'shared-data' is either a string or a dict with keys:
    #   src  (mandatory): file path or glob pattern
    #   strip (optional): prefix stripped from each matched path in the archive
    #   dest  (optional): path prepended to each entry inside the wheel's .data/data/ section
    # Returns an empty list when 'shared-data' is absent.
    def resolve_shared_data(self, cname: str, comp: dict) -> List[Tuple[Path, str, str]]:
        patterns = comp.get('shared_data')
        if not patterns:
            return []

        files = []
        for entry in patterns:
            if isinstance(entry, dict):
                fpattern = entry.get('src')
                if not fpattern:
                    raise SyntaxError(f'[packaging.{cname}]: shared-data dict entry missing "src" key')
                strip = entry.get('strip')
                dest  = entry.get('dest', '')
            else:
                fpattern = entry
                strip = None
                dest  = ''

            f = self._substitute_file_vars(fpattern)

            globbed_list = list(Path().glob(f))
            if not globbed_list:
                term.warning(f'[packaging.{cname}]', f'shared-data pattern not found: {term.bright_white(f)}')
                continue

            for g in globbed_list:
                files.append((g, strip, dest))

        return files


    # Creates a tar or zip archive at fpath from (path, relative_to, prefix) triplets.
    def make_archive(self, fpath: Path, files: List[Tuple[Path, str, str]]):
        if fpath.suffix == '.zip':
            self._make_zip_archive(fpath, files)
            return

        if fpath.suffix in ['.txz', '.xz']:
            compression = 'xz'
        elif fpath.suffix in ['.tgz', '.gz']:
            compression = 'gz'
        elif fpath.suffix in ['.tbz2', '.bz2']:
            compression = 'bz2'
        elif fpath.suffix in ['', None]:
            compression = ''
        else:
            raise SyntaxError(f'Package type for suffix not supported: {fpath.suffix}')

        with tarfile.open(fpath, f'w:{compression}') as tar:
            for fname, strip, dest in files:
                if strip:
                    arcname = Path(dest) / fname.relative_to(strip)
                elif dest:
                    arcname = Path(dest) / fname.name
                else:
                    arcname = None
                tar.add(fname, arcname=arcname)


    # zipfile has no tarfile.add()-like recursive directory helper, so
    # directories are expanded manually and paths forced to posix separators.
    def _make_zip_archive(self, fpath: Path, files: List[Tuple[Path, str, str]]):
        with zipfile.ZipFile(fpath, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fname, strip, dest in files:
                if strip:
                    base = Path(dest) / fname.relative_to(strip)
                elif dest:
                    base = Path(dest) / fname.name
                else:
                    base = fname

                if fname.is_dir():
                    for sub in fname.rglob('*'):
                        if sub.is_file():
                            zf.write(sub, (base / sub.relative_to(fname)).as_posix())
                else:
                    zf.write(fname, base.as_posix())


    # Builds Component objects for packaging entries
    def build_components(self, mypkg: Package) -> List[Component]:
        components = []
        for cname, comp in self._config.items():
            packaging_type = comp.get('type', 'auto')
            if packaging_type == 'python':
                # handled by the pypa build backend
                continue
            if packaging_type not in ('auto', 'plain', 'archive'):
                raise SyntaxError(f'[packaging.{cname}]: unknown type "{packaging_type}"')
            if 'depends_on' in comp:
                raise SyntaxError(f'[packaging.{cname}]: "depends-on" is only supported for type "python"')
            for key in ('platform_specific', 'wheel_tag'):
                if key in comp:
                    raise SyntaxError(f'[packaging.{cname}]: "{key.replace("_", "-")}" is only supported for type "python"')

            files = self.resolve_files(cname, comp)

            if not files:
                continue

            fpath = self.paths.source / files[0][0]
            is_single_file = len(files) == 1 and fpath.is_file()

            if packaging_type == 'plain' and not is_single_file:
                raise SyntaxError(f'[packaging.{cname}]: type="plain" requires exactly one matched file')

            use_plain = is_single_file if packaging_type == 'auto' else packaging_type == 'plain'

            if use_plain:
                if 'suffix' in comp:
                    raise SyntaxError(f'[packaging.{cname}]: "suffix" must not be used with a plain component')
                suffix = ''
                if '.' in fpath.name:
                    _, suffix = fpath.name.rsplit('.', maxsplit=1)
            else:
                suffix = comp.get('suffix', 'tar.xz')
                tcstr = f'-{mypkg.toolchain}' if mypkg.toolchain else ''
                fpath = self.paths.build / f'{mypkg.name}-{mypkg.version}{tcstr}-{cname}.{suffix}'
                self.make_archive(fpath, files)

            checksum = compute_sha1sum(fpath)
            build_only = bool(comp.get('build_only', False))
            traverse = resolve_traverse(
                comp.get('traverse'), comp.get('no_traverse'))

            component = Component(
                name        = cname,
                suffix      = suffix,
                filename    = fpath.name,
                checksum    = checksum,
                localpath   = str(fpath.parent.relative_to(self.paths.source)),
                build_only  = build_only,
                traverse    = traverse,
            )

            term.info(f'rbbuild component {term.bright_white(cname)}:\n  {term.cyan(str(fpath))}')

            components.append(component)

        return components


    def _substitute_file_vars(self, f: str) -> str:
        if Path(f).anchor:
            raise SyntaxError('[packaging]: provided files must be relative')
        elif f.startswith('$OBJ/'):
            dest_path = self.paths.build / f[5:]
        elif f.startswith('$STAGING/'):
            dest_path = self.paths.staging / f[9:]
        elif f.startswith('$DOCUMENTATION/'):
            dest_path = self.paths.documentation / f[15:]
        else:
            return f

        return str(dest_path.relative_to(self.paths.source))
