# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import os
import re
import sys
import tomllib

from dependency_injector import providers
from pathlib import Path
from typing import List

from rbbuild.container.config_roots import load_config_roots
from rbbuild.core.runtime_settings import OperationMode, CompareState, DiffMode
from rbbuild.core.cache import CacheMode
from rbbuild.deps.converter import deps_json_to_config, load_deps_json

from rbbuild.sourcedir.jenkinsfile import Jenkinsfile


# Build tools that need a toolchain, with the file that activates each of them
_TOOLCHAIN_BUILD_TOOLS = {
    'cmake': 'CMakeLists.txt',
}


# Normalize sub-section keys so that 'build-tools', 'build_tools', and
# 'build.tools' are all treated as the same key.  The canonical storage
# form uses underscores so the DI layer can access them as attributes.
def _normalize_config(cfg: dict) -> dict:
    def normalize(k): return re.sub(r'[-.]+', '_', k).lower()

    cfg_out = {}

    for k, v in cfg.items():
        if type(v) is dict:
            cfg_out[normalize(k)] = _normalize_config(v)
        else:
            cfg_out[normalize(k)] = v
    return cfg_out


class RBBuildConfiguration(providers.Configuration):
    # Fallback for $RBB_CONFIG_PATH in config files if the env variable is unset
    _rbbuild_config_path: Path = None

    # Source folder of the loaded project configuration, if any
    _project_source_path: Path = None

    # toolchain-<platform> settings of the user config; they override the profile
    _user_toolchain_defaults: dict = None

    def load_configuration(
        self,
        rbbuild_root_path: Path,
        rbbuild_config_path: Path,
    ):
        self._rbbuild_config_path = rbbuild_config_path
        self.paths.rbbuild_root.from_value(str(rbbuild_root_path))
        # Load rbbuild config (defaults)
        rbbuild_config = rbbuild_config_path / 'rbbuild.toml'
        self.paths.rbbuild_config.from_value(rbbuild_config)
        self._load_toml_file(rbbuild_config, profile=False)

        # Load user config
        user_config_path = Path(self.paths.user_config())
        self.paths.user_config.from_value(user_config_path)  # Convert type to Path
        user_config = user_config_path / 'rbbuild.toml'
        if user_config.exists():
            self._load_toml_file(user_config, profile=False)
            self._user_toolchain_defaults = {
                key: value for key, value in (self.settings() or {}).items()
                if key.startswith('toolchain-')
            }

            # Load user credentials from environment variable (RBB_CREDENTIALS)
            self._load_credentials()


    # Loads configuration elements from rbbuild.toml or other project
    # configuration files (e.g., pyproject.toml).
    #
    # Project configuration is only relevant for rbbuild and rbfoss (i.e.,
    # where these tools work with actual source code repositories).
    # Hence, this method is loaded explicitly by those tools rather than
    # called by default with load_configuration().
    def load_project_configuration(self, source_path: Path):
        cfg = {}
        pyproject_toml = source_path / 'pyproject.toml'
        if pyproject_toml.exists():
            cfg = self._load_pyproject_toml(pyproject_toml)
            cfg = _normalize_config(cfg)

        rbbuild_toml = source_path / 'rbbuild.toml'
        if rbbuild_toml.exists():
            with open(rbbuild_toml, 'rb') as fd:
                rbbuild_toml_cfg = tomllib.load(fd)
                rbbuild_toml_cfg = _normalize_config(rbbuild_toml_cfg)

            # Need to merge config files recursively. Example:
            #
            # pyproject.toml:
            #   [project]
            #   name = ...
            #   license = ...
            #   authors = ...
            #   maintainers = ...
            #
            # rbbuild.toml:
            #   [project]
            #   name = ...
            #   version = ...
            #
            # If we simply did cfg.update(rbbuild_toml_cfg) then only
            # "name" and "version" are taken over.
            # The other fields (license, authors, maintainers) would vanish.

            def _merge_config(cfg, updated_cfg):
                for k, v in updated_cfg.items():
                    if type(v) is dict:
                        cfg[k] = _merge_config(cfg.get(k, {}), v)
                    else:
                        cfg[k] = v
                return cfg

            _merge_config(cfg, rbbuild_toml_cfg)

        # Normalize [dependencies] (dict) and [[dependencies]] (list) to always be a list
        if 'dependencies' in cfg and isinstance(cfg['dependencies'], dict):
            cfg['dependencies'] = [cfg['dependencies']]


        deps_from_file = None
        deps_json = source_path / 'deps.json'
        if deps_json.exists():
            deps_from_file = load_deps_json(deps_json)
        else:
            # Legacy deps files (deps, deps.linux, deps.win32, …).
            legacy_files = sorted(
                f for f in source_path.iterdir()
                if f.is_file()
                and (f.name == 'deps' or f.name.startswith('deps.'))
                and not f.suffix.startswith('.json')
            )
            if legacy_files:
                deps_data = {'/' : {}}
                for df in legacy_files:
                    with open(df) as fd:
                        deps_data['/'][df.name] = [line.strip() for line in fd]
                deps_from_file = deps_json_to_config(deps_data)

        if deps_from_file:
            # If no [dependencies] was configured, detect and eagerly load file-based sources.
            if 'dependencies' not in cfg:
                cfg['dependencies'] = deps_from_file
            else:
                raise RuntimeError('Dependencies already defined rbbuild.toml/pyproject.toml. Remove conflicting deps file and retry!')

        self.from_dict(cfg)
        self._project_source_path = source_path

        # Environment variables override
        if 'RBB_PACKAGE_NAME' in os.environ:
            self.project.name.from_env('RBB_PACKAGE_NAME')
        if 'BRANCH_NAME' in os.environ:
            self.project.branch.from_env('BRANCH_NAME')
        if 'BUILD_NUMBER' in os.environ:
            self.project.version_build.from_env('BUILD_NUMBER')
        elif 'GITHUB_RUN_NUMBER' in os.environ:
            self.project.version_build.from_env('GITHUB_RUN_NUMBER')
        if 'RBB_PACKAGE_VERSION' in os.environ:
            self.project.version.from_env('RBB_PACKAGE_VERSION')


    def _load_pyproject_toml(self, pyproject_toml: Path):
        with open(pyproject_toml, 'rb') as fd:
            data = tomllib.load(fd)

        cfg = {}

        # [project]
        project = data.get('project')
        if project:
            cfg['project'] = project

        # [tool.rbbuild]
        rbbuild = data.get('tool', {}).get('rbbuild')
        if rbbuild:
            cfg['rbbuild'] = {}
            for key in rbbuild.keys():
                # Map items from pyproject_toml[tool.rbbuild.<k>] -> cfg[<k>]
                if key in ['dependencies', 'packaging', 'oss', 'pandoc', 'sphinx', 'cmake']:
                    cfg[key] = rbbuild[key]

                # [tool.rbbuild.version]
                elif 'version' in rbbuild:
                    if 'major' in rbbuild['version']:
                        cfg['project']['version_major']    = rbbuild['version']['major']
                    if 'minor' in rbbuild['version']:
                        cfg['project']['version_minor']    = rbbuild['version']['minor']
                    if 'revision' in rbbuild['version']:
                        cfg['project']['version_revision'] = rbbuild['version']['revision']
                    if 'build' in rbbuild['version']:
                        cfg['project']['version_build']    = rbbuild['version']['build']
                    if 'branch' in rbbuild['version']:
                        cfg['project']['branch']           = rbbuild['version']['branch']
                    if 'version' in rbbuild['version']:
                        cfg['project']['version']          = rbbuild['version']['version']

                # Map all other items from pyproject_toml[tool.rbbuild.<k>] -> cfg['rbbuild'][<k>]
                else:
                    cfg['rbbuild'][key] = rbbuild[key]

        return cfg


    def load_jenkinsfile(self, source_path: Path):
        # Jenkinsfile.rbbuild and Jenkinsfile are supported.
        # If both exist, Jenkinsfile.rbbuild will be used.
        # Repository-specific profile from Jenkinsfile overrides the
        # user-selected default.
        #
        # The selected profile and toolchain can be defined in the
        # Jenkinsfile configuration as repository specific setting.
        jenkinsfile = {}
        for jf in [source_path / 'Jenkinsfile.rbbuild', source_path / 'Jenkinsfile']:
            if jf.exists():
                jenkinsfile = Jenkinsfile(jf)
                break

        # Extract profile_name from the following sources (in this order):
        # - as command-line argument (-P)
        # - Jenkinsfile[.rbbuild]
        # - ~/.config/rbbuild.ini [settings] section
        # - otherwise, the default profile is "standalone"
        # [settings.profile]
        if 'profile' in jenkinsfile:
            self.settings.profile.from_value(jenkinsfile['profile'])


    # We need to do this before loading files from source path (Jenkinsfile, pyproject.toml)
    def load_cli_source_path(self, **kwargs):
        if kwargs.get('source_path'):
            self.paths.source.from_value(kwargs['source_path'])

    def load_cli_profile(self, **kwargs):
        if kwargs.get('profile'):
            self.settings.profile.from_value(kwargs['profile'])


    # A toolchain is only needed if an active build tool needs one. The tools
    # are taken from [rbbuild] build_tools or, by default, from the files of
    # the project. Without project configuration, the profile default applies.
    def _requires_toolchain(self) -> bool:
        if self._project_source_path is None:
            return True

        build_tools = self.rbbuild.build_tools() or self.tool.rbbuild.build_tools() or list(_TOOLCHAIN_BUILD_TOOLS)
        source = Path(self.paths.source() or self._project_source_path)
        return any(
            tool in build_tools and (source / marker).exists()
            for tool, marker in _TOOLCHAIN_BUILD_TOOLS.items()
        )


    def load_cli(self, **kwargs):
        platform = kwargs.get('platform') or sys.platform
        self.settings.platform.from_value(platform)

        # settings.channel and settings.toolchain hold only the explicit selection
        if kwargs.get('channel'):
            self.settings.channel.from_value(kwargs['channel'])
        elif os.environ.get('RBB_CHANNEL'):
            self.settings.channel.from_value(os.environ['RBB_CHANNEL'])

        if kwargs.get('tcid'):
            self.settings.toolchain.from_value(kwargs['tcid'])
        elif os.environ.get('RBB_TOOLCHAIN_ID'):
            self.settings.toolchain.from_value(os.environ['RBB_TOOLCHAIN_ID'])

        self.settings.toolchain_required.from_value(self._requires_toolchain())

        if kwargs.get('install_prefix'):
            self.paths.install_prefix.from_value(kwargs['install_prefix'])

        if kwargs.get('deps_line'):
            self.rbbuild.rbbuild.deps_line.from_value(kwargs['deps_line'])

        if kwargs.get('depsfile'):
            self.rbbuild.rbbuild.depsfile.from_value(Path(kwargs['depsfile']))

        if kwargs.get('cmake_define'):
            self.cmake.cmake_defines.from_value(kwargs['cmake_define'])

        # Application operation mode
        op_mode = OperationMode(
            debug=kwargs.get('debug', False),
            verbose=kwargs.get('verbose', False),
            force=kwargs.get('force', False),
            ignore_errors=kwargs.get('ignore_errors', False),
            dry_run=kwargs.get('dry_run', False),
            offline=kwargs.get('offline', False),
            manifest_only=kwargs.get('manifest_only', False),
            transitive=not kwargs.get('no_traverse', False),
        )
        self.op_mode.from_value(op_mode)

        # Cache mode
        # This variable controls the behavior of caching and downloading (e.g., rbbuild -F):
        # * normal:        synchronize online and only download if the file is not cached
        # * cache_only:    Never check online
        # * force:         Never use the cache
        # * manifest_only: Only synchronize manifest file
        if op_mode.force is True:
            cache_mode = CacheMode.force
        elif op_mode.offline is True:
            cache_mode = CacheMode.cache_only
        elif op_mode.manifest_only is True:
            cache_mode = CacheMode.manifest_only
        else:
            cache_mode = CacheMode.normal

        # Disable synchronizing with remote if -F was not specified
        #if 'fetch' not in self.rbbuild.actions() and not kwargs.get('publish'):
        #    if cache_mode == CacheMode.normal:
        #        cache_mode = CacheMode.cache_only

        self.cache_mode.from_value(cache_mode)

        # --components
        # Handle skipping of components via command line parameter. Example:
        #     rbbuild -FI --components=prod will accept only prod packages
        #     rbbuild -FI --components=~licenses,dev will skip licenses and dev packages
        filtered_components = set()
        skipped_components  = set()
        if kwargs.get('components'):
            for comp in kwargs['components'].split(','):
                skipped = comp.startswith('~')
                if skipped:
                    skipped_components.add(comp)
                else:
                    filtered_components.add(comp)
        self.filtered_components.from_value(filtered_components)
        self.skipped_components.from_value(skipped_components)

        self.load_cli_source_path(**kwargs)
        self.load_cli_profile(**kwargs)

        # pkq specific?
        if kwargs.get('diffmode'):
            dmode = kwargs['diffmode']
            if dmode == 'basic':
                diffmode = DiffMode.BASIC
            elif dmode == 'commits':
                diffmode = DiffMode.COMMITS
            elif dmode == 'jira':
                diffmode = DiffMode.JIRADETAILS
            elif dmode == 'git':
                diffmode = DiffMode.GITDETAILS
            else:
                raise SyntaxError('Valid arguments for --diff-mode: basic, commits, git, or jira')
            self.diffmode.from_value(diffmode)

        if kwargs.get('filter_changes'):
            filter_changes = kwargs['filter_changes']
            allowed_filter = []
            if filter_changes == 'all':
                filter_changes = 'same,changed,new,deleted,moved'
            for f in filter_changes.split(','):
                f = f.strip()
                if f == 'same':
                    allowed_filter.append(CompareState.SAME)
                elif f == 'changed':
                    allowed_filter.append(CompareState.CHANGED)
                elif f == 'new':
                    allowed_filter.append(CompareState.NEW)
                elif f == 'deleted':
                    allowed_filter.append(CompareState.DELETED)
                elif f == 'moved':
                    allowed_filter.append(CompareState.MOVED)
                else:
                    raise SyntaxError(f'Invalid filter changes parameter "{filter_changes}"')
            self.filter_changes.from_value(allowed_filter)


    # Load profile data. Profiles of the same name are overridden in the order
    # system, config roots (plugins), user. Remote services of the config roots
    # are shared by all profiles and may be overridden by the profile itself.
    def load_profile(
        self,
        profile_name: str,
        rbbuild_config_path: Path,
        user_config_path: Path,
        config_roots: List[Path] = None,
    ):
        if config_roots is None:
            config_roots = load_config_roots()

        self._rbbuild_config_path = rbbuild_config_path

        # Identify all profiles
        profiles = {}
        profile_dirs = [
            rbbuild_config_path / 'profiles',
            *(root / 'profiles' for root in config_roots),
            user_config_path / 'profiles',
        ]
        for profile_dir in profile_dirs:
            if not profile_dir.exists():
                continue
            for profile_path in profile_dir.iterdir():
                profile_toml = profile_path / f'{profile_path.name}.toml'
                if profile_toml.exists():
                    profiles[profile_path.name] = profile_toml

        if not profile_name:
            return

        self.profiles.from_dict(profiles)

        if profile_name not in profiles:
            raise LookupError(f'Could not find profile {profile_name}')

        # Load profile configuration: imported profiles first, so that the
        # importing profile overrides them
        chain = self._profile_chain(profile_name, profiles)
        for name in chain:
            self._load_toml_file(profiles[name], profile=True)
        profile_paths = [profiles[name].parent for name in chain]
        if self._user_toolchain_defaults:
            self.from_dict({'settings': self._user_toolchain_defaults})

        # ruff.toml is passed to ruff as a file, so only its path is stored
        ruff_configs = [path / 'ruff.toml' for path in profile_paths if (path / 'ruff.toml').is_file()]
        if ruff_configs:
            self.from_dict({'profile': {'ruff_config': str(ruff_configs[-1])}})

        # Remote services
        service_dirs = [
            *(root / 'remote-services' for root in config_roots),
            *(path / 'remote-services' for path in profile_paths),
        ]
        for service_dir in service_dirs:
            for service_toml in sorted(service_dir.glob('*.toml')):
                self._load_toml_file(service_toml, profile=False)

        self.profile.services.url.from_dict({
            'type': 'url',
            'auth-method': 'none',
        })

        # Toolchains
        toolchains = {}
        for path in profile_paths:
            toolchains.update(self._load_toolchains(path))
        self.from_dict({'profile': {'toolchains': toolchains}})

        # Channels - handler for URL (not configurable)
        self.profile.channels.url.from_dict({
            'type': 'url',
            'remote_service': 'url',
            'repository': 'downloads',
        })


    # Returns the profile preceded by the profiles it imports with
    # [profile] import, imported profiles first.
    def _profile_chain(self, profile_name: str, profiles: dict) -> List[str]:
        chain = []
        while profile_name:
            if profile_name in chain:
                raise RuntimeError(f'Profile {profile_name}: circular [profile] import')
            if profile_name not in profiles:
                raise LookupError(f'Could not find profile {profile_name}')
            chain.insert(0, profile_name)
            with open(profiles[profile_name], 'rb') as fd:
                profile_name = tomllib.load(fd).get('profile', {}).get('import')
        return chain


    # A toolchain is defined by toolchains/<platform>-<tcid>.toml. Tool-specific
    # sections (the keys are in the Toolchain class):
    #   [toolchain]  native
    #   [cmake]      file     CMake toolchain file, relative to toolchains/.
    #                         Default: cmake/<platform>-<tcid>.cmake. It is not
    #                         checked here but passed to CMake as-is.
    #   [python]     executable    Name (looked up in PATH) or absolute path
    #   [python.environment]       Variables for processes using the executable
    #   [python]     import        Toolchain whose [python] section is taken
    #                              over; own keys override
    #   [wheel]      platform-tag
    def _load_toolchains(self, profile_path: Path) -> dict:
        toolchains_dir = profile_path / 'toolchains'
        toolchains = {}
        python_sections = {}
        for toolchain_toml in sorted(toolchains_dir.glob('*.toml')):
            name = toolchain_toml.stem
            platform, tcid = name.split('-', maxsplit=1)

            with open(toolchain_toml, 'rb') as fd:
                data = tomllib.load(fd)

            cmake_file = toolchains_dir / data.get('cmake', {}).get('file', f'cmake/{name}.cmake')

            toolchains[name] = {
                'platform': platform,
                'tcid': tcid,
                'cmake_file': cmake_file,
                'native': data.get('toolchain', {}).get('native', False),
            }
            python_sections[name] = data.get('python', {})
            platform_tag = data.get('wheel', {}).get('platform-tag')
            if platform_tag:
                toolchains[name]['wheel_platform_tag'] = platform_tag

        for name in toolchains:
            python = self._resolve_python_section(name, python_sections)
            if python.get('executable'):
                toolchains[name]['python_executable'] = python['executable']
            if python.get('environment'):
                toolchains[name]['python_environment'] = python['environment']

        return toolchains


    # Applies [python] import: the section of the imported toolchain is the
    # base, keys of the importing toolchain override it.
    def _resolve_python_section(self, name: str, sections: dict, stack: tuple = ()) -> dict:
        section = sections[name]
        imported = section.get('import')
        if not imported:
            return section

        if imported == name or imported in stack:
            raise RuntimeError(f'Toolchain {name}: circular [python] import of {imported}')
        if imported not in sections:
            raise LookupError(f'Toolchain {name}: [python] import of unknown toolchain {imported}')

        base = self._resolve_python_section(imported, sections, (*stack, name))
        return {
            **base,
            **{key: value for key, value in section.items() if key not in ('import', 'environment')},
            'environment': {**base.get('environment', {}), **section.get('environment', {})},
        }


    # Checked Python environs library. Issues:
    # * cannot assign environment variables but must use a file (.env)
    # * does not support env variables in default values
    def _expand_vars(self, cfg: dict):
        def _walk_config(config: dict, parent: dict=None):
            for key, value in config.items():
                if type(value) is dict:
                    yield from _walk_config(value, value)
                else:
                    yield key, value, parent

        for key, value, parent in _walk_config(cfg):
            # Note: only strings are replaced, but not list or dict
            if type(value) is str and value.count('$') > 0:
                # Replace 'var = $HOME/somepath' with 'var = /home/user/somepath'
                for i in range(value.count('$')):
                    default = ''
                    # Support environment variable patterns: '${VAR}' and '$VAR'
                    pattern =  r'\$(\w+)'
                    if '${' in value:
                        # Allow default values: ${MYVALUE:defaultvalue}
                        if mm := re.match(r'\${(\w+):(.+)}', value):
                            value = '$' + mm.group(1)
                            default = mm.group(2)
                        else:
                            pattern =  r'\${(\w+)}'
                    value = re.sub(pattern, lambda m: self._lookup_var(m.group(1), default), value)
                parent[key] = value


    def _lookup_var(self, name: str, default: str) -> str:
        if name in os.environ:
            return os.environ[name]
        if name == 'RBB_CONFIG_PATH' and self._rbbuild_config_path:
            return str(self._rbbuild_config_path)
        return default


    def _load_toml_file(self, toml: Path, profile: bool):
        try:
            with open(toml, 'rb') as fd:
                cfg = tomllib.load(fd)
        except tomllib.TOMLDecodeError as ex:
            from rbbuild.librbb.term import term
            term.error(str(toml), 'Failed to parse TOML file')
            raise ex
        except Exception:
            raise

        self._expand_vars(cfg)
        # The explicit toolchain only comes from -t or RBB_TOOLCHAIN_ID; rbbuild 5 keys are ignored
        for legacy_key in ('toolchain', 'toolchains'):
            cfg.get('settings', {}).pop(legacy_key, None)
        if 'rbbuild' in cfg.get('tool', {}):
            cfg['tool']['rbbuild'] = _normalize_config(cfg['tool']['rbbuild'])
        # The channel of a profile is only the default of the profile
        if profile and 'channel' in cfg.get('settings', {}):
            cfg['settings']['default_channel'] = cfg['settings'].pop('channel')
        self.from_dict(cfg)


    def _load_credentials(self):
        from rbbuild.librbb.term import term
        # Overwrite credentials if they are passed via environment variable
        if 'RBB_CREDENTIALS' in os.environ:
            for value in os.environ['RBB_CREDENTIALS'].split(';'):
                ncolon = value.count(':')
                user = None
                if ncolon == 1:
                    repo,cred = value.split(':', maxsplit=1)
                elif ncolon == 2:
                    repo,cred,user = value.split(':', maxsplit=2)
                else:
                    raise SyntaxError(f'Invalid credentials. Expected format: {term.bright_white("<repo>:<credentials>[:<user>]")}')

                # if f'service:{repo}' not in self.config():
                if not self.service[repo]():
                    raise RuntimeError(f'Invalid repository {repo} - not configured!')

                # Update/overwrite config
                if cred:
                    self.service[repo].credentials.from_value(cred)
                if user:
                    self.service[repo].user.from_value(user)

