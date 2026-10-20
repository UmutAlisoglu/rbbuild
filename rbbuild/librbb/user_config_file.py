# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import shutil
import tomllib

from collections import UserDict
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from rbbuild.librbb.term import term


class UserConfigFile(UserDict):
    def __init__(self, user_conf_path: Path):
        super().__init__()
        self.user_conf_path = user_conf_path


    def __enter__(self):
        user_config_file = self.user_conf_path / 'rbbuild.toml'
        if user_config_file.exists():
            with open(user_config_file, 'rb') as fd:
                self.data = tomllib.load(fd)
        return self


    def __exit__(self, exc_type, _exc_val, _exc_tb):
        if exc_type is None:
            self.write()


    # "dict" set interface
    def __setitem__(self, key, value):
        if not key:
            raise SyntaxError('Key must not be None!')

        if '.' not in key:
            sections = ['settings', key]

        else:
            sections = key.split('.')

        # Sections of sections (section.subsection) are orgnized
        # as nested dicts.
        data = self.data
        for sec in sections[:-1]:
            if sec not in data:
                data[sec] = {}
            data = data[sec]

        # The last dict element contains the actual value
        data[sections[-1]] = value


    # Updates or sets an item in the user configuration file
    # (default: $HOME/.config/rbbuild.toml)
    def write(self):
        user_config_file = self.user_conf_path / 'rbbuild.toml'
        if user_config_file.exists():
            # try-except not needed here, already done during program init
            with open(user_config_file, 'rb') as fd:
                config_out = tomllib.load(fd)
        else:
            # Ensure that the .config folder exists (especially on Windows, this may be an issue)
            self.user_conf_path.mkdir(mode=0o700, parents=True, exist_ok=True)
            config_out = {}

        def _update_config(in_item=self.data, out_item=config_out):
            for key, value in in_item.items():
                if type(value) is dict:
                    if key not in out_item:
                        out_item[key] = {}
                    _update_config(in_item[key], out_item[key])
                else:
                    out_item[key] = value

        # We cannot simply call config_out.update(self.data). Otherwise, fields will get lost.
        _update_config(self.data, config_out)

        def _walk_config(config: dict, section):
            for key, value in config.items():
                if type(value) is dict:
                    snew = key if not section else f'{section}.{key}'
                    yield from _walk_config(value, snew)
                else:
                    yield section, key, value


        with NamedTemporaryFile('w', delete=False) as tmpfd:
            text = f'# This file was generated with rbbconf {datetime.now().isoformat()}\n'

            prev_section = None
            for section, key, value in _walk_config(config_out, None):
                if section != prev_section:
                    text += f'\n[{section}]\n'
                    prev_section = section
                if isinstance(value, list):
                    items = ', '.join(repr(v) for v in value)
                    text += f'{key} = [{items}]\n'
                else:
                    text += f'{key} = {value!r}\n'

            text += '\n'
            tmpfd.write(text)
            tmpfname = tmpfd.name  # workaround on Windows

        # Before overwriting the old config file, we try to read the just written content.
        try:
            with open(tmpfname, 'rb') as fd:
                _ = tomllib.load(fd)
        except tomllib.TOMLDecodeError as ex:
            term.error(str(self.user_conf_path), f'Parse error of updated configuration: {tmpfname}')
            raise ex
        except Exception:
            raise

        # Since security sensitive information (user credentials) are stored
        # here, we need to be cautious about permissions.
        # We are relying on the fact that NamedTemporaryFile will have the
        # mode 0o600. See, e.g:
        # https://github.com/python/cpython/blob/main/Lib/tempfile.py#L623
        shutil.move(tmpfname, user_config_file)

