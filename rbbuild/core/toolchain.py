# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import os
import re
import shutil
import sysconfig

from pathlib import Path
from typing import Optional

# Variables with a list of paths: values of the toolchain are prepended
_PATH_VARIABLES = ('PATH', 'PYTHONPATH')


# Toolchain ID that the profile defines as default for the platform
def default_tcid(settings: dict, platform: str) -> Optional[str]:
    return (settings or {}).get(f'toolchain-{platform}')


# Translates a default toolchain setting of rbbconf into its canonical form
# settings.toolchain-<platform> = <platform>-<tcid>. Accepted are
# toolchain=<platform>-<tcid>, toolchain=<tcid> (for the current platform) and
# toolchain-<platform>=<tcid or platform-tcid>. Other keys are returned as-is.
def default_toolchain_setting(key: str, value: str, platform: str, toolchains_config: dict):
    match = re.fullmatch(r'(?:settings\.)?toolchain(?:-(\w+))?', key)
    if not match:
        return key, value

    platforms = {'linux', 'win32', 'darwin', *(tc['platform'] for tc in toolchains_config.values())}
    value_platform = value.split('-', maxsplit=1)[0] if '-' in value else None
    if value_platform not in platforms:
        value_platform = None

    key_platform = match.group(1)
    if key_platform and value_platform and value_platform != key_platform:
        raise SyntaxError(f'Toolchain {value} does not match platform {key_platform} of {key}')

    target_platform = key_platform or value_platform or platform
    if value_platform != target_platform:
        value = f'{target_platform}-{value}'
    return f'settings.toolchain-{target_platform}', value


# A project that needs no toolchain selects none-any, unless a toolchain is selected explicitly
def selected_tcid(explicit: Optional[str], default: Optional[str], required: bool) -> Optional[str]:
    return explicit or (default if required else 'none-any')


# Toolchain of packages without toolchain: the explicit selection or else the profile default
def target_tcid(explicit: Optional[str], default: Optional[str]) -> Optional[str]:
    return explicit or default


class Toolchain:
    def __init__(
        self,
        tcid: str,
        toolchains_config: dict,
    ):
        if not tcid or tcid == 'none-any':
            self.platform='none'
            self.name='any'
            self.cmake_file=None
            self.native=False
            self.wheel_platform_tag=None
            self.python_executable=None
            self.python_environment={}
            return

        cfg = toolchains_config.get(tcid)
        if cfg:
            cfg = toolchains_config[tcid]
        else:
            for name, toolchain in toolchains_config.items():
                if toolchain['tcid'] == tcid:
                    cfg = toolchain
                    break
            if not cfg:
                raise LookupError(f'Toolchain {tcid} not found')

        self.platform = cfg['platform']
        self.name = cfg['tcid']
        self.cmake_file = cfg['cmake_file']
        self.native = cfg.get('native', False)
        self.python_executable = cfg.get('python_executable')
        self.python_environment = cfg.get('python_environment', {})

        # Native toolchains use the platform of the running interpreter
        self.wheel_platform_tag = cfg.get('wheel_platform_tag')
        if not self.wheel_platform_tag and self.native:
            self.wheel_platform_tag = re.sub(r'[-.]', '_', sysconfig.get_platform())


    def __repr__(self) -> str:
        return f'Toolchain(platform={self.platform}, name={self.name}, cmake_file={self.cmake_file!s})'


    # none-any: no toolchain is needed
    @property
    def is_any(self) -> bool:
        return self.platform == 'none'


    # The Python executable of the toolchain: an absolute path, or a name that
    # is looked up in PATH. It is never provisioned by rbbuild.
    @property
    def python_path(self) -> Optional[Path]:
        if not self.python_executable:
            return None

        found = shutil.which(self.python_executable)
        if not found:
            raise FileNotFoundError(f'Python executable "{self.python_executable}" of toolchain {self} not found')
        return Path(found)


    # Returns a copy of environ with the Python environment of the toolchain:
    # path variables are prepended, other variables are set if not defined yet.
    def apply_python_environment(self, environ: dict) -> dict:
        result = dict(environ)
        for name, value in self.python_environment.items():
            existing = next((key for key in result if key.upper() == name.upper()), None)
            if name.upper() in _PATH_VARIABLES:
                if existing and result[existing]:
                    value = value + os.pathsep + result[existing]
                result[existing or name] = value
            elif not existing:
                result[name] = value
        return result


    # The identifier of the toolchain. This attribute is really
    # unique for the platform, however, it may appear for multiple
    # platforms. Examples:
    # - linux-yocto-armhf-2.4
    # - win32-visualstudio-2017
    # - linux-native
    # - win32-native
    def __str__(self) -> str:
        return f'{self.platform}-{self.name}'

