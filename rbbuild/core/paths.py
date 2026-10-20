# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from pathlib import Path

from rbbuild import data_path
from rbbuild.core.toolchain import Toolchain


class Paths:
    def __init__(
        self,
        rbbuild_root: str,
        source: str,
        staging_root: str,
        build_root: str,
        documentation_root: str,
        dist: str,
        install_prefix: str,
        toolchain: Toolchain,
    ):
        self.rbbuild_root: Path      = Path(rbbuild_root)
        self.source: Path            = Path(source).resolve()
        self.staging_root: Path      = self._safe_path(Path(staging_root))
        self.staging: Path           = Path(self.staging_root) / str(toolchain)
        self.build_root: Path        = self._safe_path(Path(build_root))
        self.build: Path             = Path(self.build_root) / str(toolchain)
        self.documentation_root: Path = self._safe_path(Path(documentation_root))
        self.documentation: Path     = Path(self.documentation_root) / 'documentation'
        self.dist: Path              = Path(dist)
        # Install Prefix is by default staging/<tcid> and overwritten with rbbuild -S <install_prefix>
        self.install_prefix: Path    = Path(install_prefix) if install_prefix else self.staging
        self.templates: Path         = data_path() / 'templates'


    def _safe_path(self, path: Path) -> Path:
        def _protected_paths():
            # Prohibited paths for staging (avoid unwanted deleting)
            protected_paths = [
                # Linux
                '/',
                '/bin',
                '/sbin',
                '/usr',
                '/usr/bin',
                '/usr/sbin',
                '/var',
                '/tmp',
                '/var',
                '/lib',
                '/lib32',
                '/lib64',
                '/usr/lib',
                '/mnt',
                # Windows
                'c:\\windows',
                'c:\\windows\\system32',
                'c:\\program files',
            ]
            return map(Path, protected_paths)

        if path == Path('.') or '..' in path.parts:
            raise RuntimeError(f'Invalid path {path}: must not contain \'..\' parts')
        if path.is_absolute():
            raise RuntimeError(f'Invalid path {path}: must be a relative path')

        out_path = path.expanduser().absolute()

        # Prohibit protected paths to be selected as staging_root
        if path.absolute() in _protected_paths():
            raise RuntimeError(f'Invalid path {out_path}: matches a protected system path')

        return out_path



