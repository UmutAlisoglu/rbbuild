# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import email.parser
import functools
import getpass
import os
import re
import shutil
import subprocess
import sys
import tomllib

from pathlib import Path
from typing import List

from packaging.requirements import Requirement

from rbbuild.core.paths import Paths
from rbbuild.core.toolchain import Toolchain
from rbbuild.package.metadata import Metadata
from rbbuild.package.component import Component
from rbbuild.package.license import License
from rbbuild.package.package import Package
from rbbuild.librbb.crypto import compute_sha1sum
from rbbuild.librbb.term import term

from rbbuild.sourcedir.staging_folder import StagingFolder

from rbbuild.buildsystem.build import build_sdist, build_wheel

from ._license_map import PYTHON_CLASSIFIER_LICENSE_MAP as _python_classifier_license_map
from .packaging import Packaging


class PyPA:
    def __init__(
        self,
        paths: Paths,
        remote_services_config: dict,
        uv_config: dict,
        user_config: dict,
        packaging: Packaging,
        metadata: Metadata,
        toolchain: Toolchain,
    ):
        self.paths = paths
        self.remote_services_config = remote_services_config
        self.uv_config = uv_config
        self.user_config = user_config
        self.packaging = packaging
        self.metadata = metadata
        self.toolchain = toolchain


    @functools.cached_property
    def pyproject_toml(self) -> dict:
        pyproject_toml = {}
        pyproject_toml_path = self.paths.source / 'pyproject.toml'
        if pyproject_toml_path.exists():
            with open(pyproject_toml_path, 'rb') as fd:
                pyproject_toml = tomllib.load(fd)

        return pyproject_toml


    @property
    def venv_path(self) -> Path:
        return self.paths.staging / '.venv'


    def _execute(
        self,
        argv,
        input=None,
        environ=None,
    ):

        term.info(f'Executing command: {term.cyan(" ".join(argv))}')
        if environ:
            term.info('Environment variables:')
            for uv_var in ['UV_DEFAULT_INDEX', 'UV_INDEX', 'UV_PYTHON_INSTALL_MIRROR']:
                if uv_var in environ:
                    term.info(f'  {uv_var}={environ[uv_var]}')
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            input=input,
            env=environ)
        if proc.returncode != 0:
            raise RuntimeError(f'Command failed ({term.red(str(proc.returncode))})')

        return proc


    # uv executable resolved once; raises if uv is not installed.
    @functools.cached_property
    def _uv_executable(self) -> str:
        uv = shutil.which('uv')
        if not uv:
            raise RuntimeError('uv not found on PATH')

        return uv


    def _uv_auth_login(self, service: str, service_config: dict, service_name: str):
        uv_cred_store = self.uv_data_path / 'credentials/credentials.toml'
        term.debug('uv credentials', str(uv_cred_store))
        # Check whether the credentials for the service are already registered
        if uv_cred_store.exists():
            with open(uv_cred_store, 'rb') as fd:
                data = tomllib.load(fd)
            for item in data.get('credential', []):
                if 'service' in item and service.startswith(item['service']):
                    # Only skip uv auth if password remains the same
                    if item.get('password') == service_config.get('credentials'):
                        return
        if 'user' in service_config:
            argv = [
                self._uv_executable,
                'auth',
                'login',
                service,
                '--username', service_config['user'],
                '--password', '-'
            ]
        elif 'credentials' in service_config:
            raise RuntimeError(
                'uv auth currently does not support Bearer token authentication.'
                'To fix this, add your user name, e.g:\n'
                f'\trbbconf -s service.{service_name}.user={getpass.getuser()}')
            # uv auth login <service> --token <token> also doesn't work
            # last tested with uv-0.11.19
        else:
            raise RuntimeError(f'Invalid configuration for {service} - no credentials!')

        term.info(f'Updating uv credentials:\n  {term.cyan(" ".join(argv))}')
        self._execute(argv, input=service_config['credentials'].encode('utf-8'))


    # Creates the staging venv if it does not yet exist. uv only creates the
    # venv: the Python executable of the toolchain (if any) must be available.
    def _ensure_venv(self):
        if not self.venv_path.exists():
            argv = [self._uv_executable, 'venv', str(self.venv_path)]
            python = self.toolchain.python_path
            if python:
                argv += ['--python', str(python), '--no-python-downloads']
            self._execute(argv, environ=self.toolchain.apply_python_environment(os.environ.copy()))


    @functools.cached_property
    def _uv_cli_defaults(self):
        argv = []
        environ = self.toolchain.apply_python_environment(os.environ.copy())

        # default index
        if self.uv_config and 'default_index' in self.uv_config:
            remote_uv_default_index_name = self.uv_config['default_index']['remote_service']
            url = self.remote_services_config[remote_uv_default_index_name]['url']
            uv_default_index = f'{url}{self.uv_config["default_index"]["repository"]}/{self.uv_config["default_index"]["root_path"]}'
            environ['UV_DEFAULT_INDEX'] = uv_default_index
            service_config = self.user_config[remote_uv_default_index_name]
            self._uv_auth_login(
                service=uv_default_index,
                service_config=service_config,
                service_name=remote_uv_default_index_name,
            )

        # python install mirror
        if self.uv_config and 'python_install_mirror' in self.uv_config:
            remote_uv_mirror_name = self.uv_config['python_install_mirror']['remote_service']
            url = self.remote_services_config[remote_uv_mirror_name]['url']
            uv_mirror = f'{url}{self.uv_config["python_install_mirror"]["repository"]}/{self.uv_config["python_install_mirror"]["root_path"]}'
            environ['UV_PYTHON_INSTALL_MIRROR'] = uv_mirror
            service_config = self.user_config[remote_uv_mirror_name]
            self._uv_auth_login(
                service=uv_mirror,
                service_config=service_config,
                service_name=remote_uv_mirror_name,
            )

        # extra indexes (UV_INDEX = space-separated name=url pairs)
        if self.uv_config and 'extra_indexes' in self.uv_config:
            index_entries = []
            for idx_name, idx_cfg in self.uv_config['extra_indexes'].items():
                remote = idx_cfg['remote_service']
                url = self.remote_services_config[remote]['url']
                index_url = f'{url}{idx_cfg["repository"]}/{idx_cfg["root_path"]}'
                index_entries.append(f'{idx_name}={index_url}')
                self._uv_auth_login(
                    service=index_url,
                    service_config=self.user_config[remote],
                    service_name=remote,
                )
            environ['UV_INDEX'] = ' '.join(index_entries)

        self._ensure_venv()

        argv = [
            self._uv_executable,
        ]

        environ['VIRTUAL_ENV'] = str(self.venv_path)

        return argv, environ


    def uv(self, *args):
        argv, environ = self._uv_cli_defaults
        return self._execute(argv + list(args), environ=environ)


    def _normalize_pkg_name(self, name: str) -> str:
        return re.sub(r'[-_.]+', '-', name.strip()).lower()


    def _make_package(self, item: dict) -> Package:
        name = self._normalize_pkg_name(item['name'])

        pkg = Package(name=name, version=item['version'])
        pkg.purl = f'pkg:pypi/{pkg.name}@{pkg.version}'

        homepage = (item.get('home_page') or '').strip()
        if homepage and homepage.upper() != 'UNKNOWN':
            pkg.url = homepage

        # 1. Prefer classifiers that resolve to a known SPDX ID (non-None entries).
        spdx_licenses = []
        unknown_classifier_licenses = []
        for classifier in item.get('classifiers', []):
            if classifier in _python_classifier_license_map:
                lic_id = _python_classifier_license_map[classifier]
                if lic_id:
                    spdx_licenses.append(License(id=lic_id))
                else:
                    unknown_classifier_licenses.append(License(name=classifier))

        if spdx_licenses:
            pkg.licenses = list(set(spdx_licenses))
        else:
            # 2. Fall back to explicit SPDX expression string (e.g. "BSD-2-Clause").
            license_expression = (item.get('license_expression') or '').strip()
            if license_expression:
                pkg.licenses = license_expression
            elif unknown_classifier_licenses:
                # 3. Classifiers present but no SPDX ID — use raw classifier names.
                pkg.licenses = list(set(unknown_classifier_licenses))
            else:
                # 4. Last resort: raw License field.
                license_name = (item.get('license') or '').strip()
                if license_name and license_name.upper() != 'UNKNOWN':
                    pkg.licenses = license_name

        contacts = []
        for label, field in [
            ('Author', 'author'),
            ('Author-email', 'author_email'),
            ('Maintainer', 'maintainer'),
            ('Maintainer-email', 'maintainer_email'),
        ]:
            value = (item.get(field) or '').strip()
            if value:
                contacts.append(f'{label}: {value}')

        if contacts:
            pkg.copyright = '; '.join(contacts)

        pkg.components = [
            Component(name='wheel', suffix='whl', filename=f'{pkg.name}-{pkg.version}-py3-none-any.whl'),
        ]

        for rs in self.build_requirements:
            req = Requirement(rs)
            if req.name == name:
                pkg.build_only = True
                break

        return pkg


    def _installed_from_venv(self) -> dict:
        if not self.venv_path.exists():
            return {}

        # Locate site-packages inside the venv (path layout is platform-dependent).
        if sys.platform == 'win32':
            sp_dirs = [self.venv_path / 'Lib' / 'site-packages']
        else:
            sp_dirs = list((self.venv_path / 'lib').glob('python*/site-packages'))

        installed_packages = {}
        for sp in sp_dirs:
            for dist_info in sp.glob('*.dist-info'):
                metadata_path = dist_info / 'METADATA'
                if not metadata_path.exists():
                    continue
                with open(metadata_path, 'rb') as fd:
                    msg = email.parser.BytesParser().parse(fd)
                # msg.get() can return a Header object rather than a plain str
                # (e.g. for encoded-word values).  str() decodes it uniformly.
                def _h(key):
                    return str(msg.get(key) or '').strip()

                name = _h('Name')
                if not name:
                    continue
                item = {
                    'name':               name,
                    'version':            _h('Version'),
                    'home_page':          _h('Home-page'),
                    'classifiers':        [str(c) for c in (msg.get_all('Classifier') or [])],
                    'license_expression': _h('License-Expression'),
                    'license':            _h('License'),
                    'author':             _h('Author'),
                    'author_email':       _h('Author-email'),
                    'maintainer':         _h('Maintainer'),
                    'maintainer_email':   _h('Maintainer-email'),
                }
                installed_packages[self._normalize_pkg_name(name)] = item

        return installed_packages


    # https://docs.astral.sh/uv/reference/storage/#persistent-data-directory
    # rbbuild ignores $XDG_DATA_HOME/uv on Linux systems due to the (likely)
    # lack of write permissions.
    @functools.cached_property
    def uv_data_path(self) -> Path:
        if 'UV_CREDENTIALS_DIR' in os.environ:
            return Path(os.environ.get('UV_CREDENTIALS_DIR'))

        if sys.platform == 'win32':
            return Path(os.environ.get('APPDATA', '')) / 'uv/data'

        return Path.home() / '.local/share/uv'


    def fetch(self, mypkg: Package, fi_hint: bool):
        if fi_hint is False:
            term.warning('skipped', 'uv does not support downloading alone. Use rbbuild -FI instead.')


    def install_deps(
        self,
        mypkg: Package,
        staging_folder: StagingFolder,
        install_prefix: Path,
        fi_hint: bool,
    ):
        if not self.requirements and not self.build_requirements:
            term.warning('No packages found. Dependency file (pyproject.toml) does not exist?')
            return

        installed = self._installed_from_venv()
        added_packages = []
        for rs in [*self.requirements, *self.build_requirements]:
            req = Requirement(rs)
            norm_name = self._normalize_pkg_name(req.name)
            if norm_name not in installed or installed[norm_name]['version'] not in req.specifier:
                added_packages.append(rs)

        if added_packages:
            # self.paths.build.mkdir(parents=True, exist_ok=True)
            # In case rbbuild -I is called (without -F), ensure to use uv --offline
            args = []
            if fi_hint is False:
                args.append('--offline')
            args.extend(added_packages)
            self.uv('pip', 'install', *args)

        installed = self._installed_from_venv()
        for item in installed.values():
            pkg = self._make_package(item)
            mypkg.dependencies[repr(pkg)] = pkg
            staging_folder.index_db.data[repr(pkg)] = pkg
        staging_folder.index_db.store()


    def build(self, target=None, njobs=None):
        # No-op placeholder so that 'rbbuild -sb' does not skip PyPA entirely.
        # The actual build (sdist + wheel) happens in package().
        pass


    def package(self, mypkg: Package):
        term.info(f'Packaging {mypkg}', end='')

        # Non-rbbuild projects: delegate entirely to uv build.
        if self.pyproject_toml and self.pyproject_toml.get('build-system', {}).get('build-backend') != 'rbbuild.buildsystem.build':
            if not self.venv_path.exists():
                term.warning(str(self.venv_path), 'venv is not set-up. Try rbbuild -FI first.')
                return
            self._uv_build(mypkg)
            return

        # Native rbbuild path: build_sdist/build_wheel work without a venv, but
        # runtime deps can only be captured in the manifest when the venv exists.
        if self.requirements and not self.venv_path.exists():
            term.warning(str(self.venv_path), 'venv is not set-up; runtime deps will be missing from manifest. Try rbbuild -FI first.')

        # rbbuild support the creation of multiple wheel files. If more than one
        # "python" packaging item is defined, the wheel name is extended by the
        # component name, e.g., [tool.rbbuild.packaging.mycomponent] will append
        # "_mycomponent" to the package name.
        wheels_list = []
        for cname, comp in self.packaging.items():
            if comp.get('type') == 'python':
                wheels_list.append(cname)
        if len(wheels_list) > 1:
            multi_wheel = True
            term.redraw_last_line(f' ({", ".join(wheels_list)})')
        else:
            multi_wheel = False
            term.info('')

        for cname, comp in self.packaging.items():
            if comp.get('type') != 'python':
                continue
            config_settings = {
                'rbbuild_python_backend': self,
                'package_name': cname,
                'packaging_entry': comp,
                'multi_wheel': multi_wheel,
                'toolchain': self.toolchain,
            }
            sdist_filename = build_sdist(sdist_directory=self.paths.build, config_settings=config_settings)
            fpath = self.paths.build / sdist_filename
            mypkg.components.append(Component(
                name      = f'{cname}_sdist',
                suffix    = 'tar.gz',
                filename  = sdist_filename,
                checksum  = compute_sha1sum(fpath),
                localpath = str(fpath.parent.relative_to(self.paths.source)),
            ))
            whl_filename = build_wheel(wheel_directory=self.paths.build, config_settings=config_settings)
            fpath = self.paths.build / whl_filename
            mypkg.components.append(Component(
                name      = cname,
                suffix    = 'whl',
                filename  = whl_filename,
                checksum  = compute_sha1sum(fpath),
                localpath = str(fpath.parent.relative_to(self.paths.source)),
            ))

        # Load runtime dependencies from the installed venv into the manifest.
        self._register_venv_deps(mypkg)


    def _uv_build(self, mypkg: Package):
        # Build a non-rbbuild Python project using uv and glob for the output
        # files rather than predicting filenames from the version string.
        term.info('Running uv build ... ', end='')
        try:
            self.uv(
                'build',
                '--no-build-isolation',
                '--out-dir', str(self.paths.build),
                str(self.paths.source),
            )
        except RuntimeError:
            term.redraw_last_line(f'{term.red("failed")}')
            raise
        term.redraw_last_line(f'{term.green("success")}')

        wheels = sorted(self.paths.build.glob('*.whl'))
        sdists = sorted(self.paths.build.glob('*.tar.gz'))
        if not wheels or not sdists:
            raise RuntimeError(f'uv build produced no output in {self.paths.build}')

        for fpath, comp_name, suffix in [
            (wheels[-1], 'wheel', 'whl'),
            (sdists[-1], 'sdist', 'tar.gz'),
        ]:
            mypkg.components.append(Component(
                name      = comp_name,
                suffix    = suffix,
                filename  = fpath.name,
                checksum  = compute_sha1sum(fpath),
                localpath = str(fpath.parent.relative_to(self.paths.source)),
            ))
            term.info(f'[{term.green("*")}]', term.cyan(fpath.name))

        self._register_venv_deps(mypkg)


    def _register_venv_deps(self, mypkg: Package):
        # Adds all packages installed in the venv to mypkg.dependencies
        # using pkg:pypi PURL strings as keys.
        installed = self._installed_from_venv()
        for item in installed.values():
            dep_pkg = self._make_package(item)
            mypkg.dependencies[str(dep_pkg.purl)] = dep_pkg


    def clean(self, remove_staging=False):
        for egg_info in self.paths.source.glob('**/*.egg-info'):
            shutil.rmtree(egg_info, ignore_errors=True)
        for pycache in self.paths.source.glob('**/__pycache__'):
            shutil.rmtree(pycache)


    # To avoid ambiguities, the term "requirements" is used to indicate
    # Python input dependencies. Later, after calling pip download and freeze,
    # these inputs will be converted into proper rbbuild Package objects
    # with pkg:pypi prefixed PURLs.
    @property
    def requirements(self) -> List[str]:
        return self.pyproject_toml.get('project', {}).get('dependencies', [])


    # [project.optional-dependencies] extras, e.g. {'ui': ['PySide6>=6.11']}.
    @property
    def optional_requirements(self) -> dict:
        return self.pyproject_toml.get('project', {}).get('optional-dependencies', {})


    # Packages declared under [dependency-groups.build-only] in pyproject.toml
    # are installed into the venv and tracked in the SBOM as build_only.
    # PEP 735 group entries may also be {include-group: ...} dicts; those are
    # silently ignored here because they do not carry a version specifier.
    @property
    def build_requirements(self) -> List[str]:
        groups = self.pyproject_toml.get('dependency-groups', {})
        # Per PEP 735, group names must be normalized before comparison:
        # e.g. 'build_only' and 'Build-Only' are the same group as 'build-only'.
        normalized = {self._normalize_pkg_name(k): v for k, v in groups.items()}
        group = normalized.get('build-only', [])
        return [item for item in group if isinstance(item, str)]


    @functools.cached_property
    def _build_only_names(self) -> set:
        req_names = {self._normalize_pkg_name(Requirement(r).name) for r in self.requirements}
        build_req_names = {self._normalize_pkg_name(Requirement(r).name) for r in self.build_requirements}
        return build_req_names - req_names


    @property
    def available(self) -> bool:
        if self.pyproject_toml:
            return True
        # Also active when rbbuild.toml declares packaging entries with type='python'
        return any(comp.get('type') == 'python' for _, comp in self.packaging.items())

