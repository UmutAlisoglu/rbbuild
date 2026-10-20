#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import sys
import os
import argparse
import json

from dataclasses import asdict
from dependency_injector.wiring import Provide, inject
from fnmatch import fnmatch
from pathlib import Path
from typing import List

from rbbuild import data_path
from rbbuild.container.application import Application
from rbbuild.container.configuration import RBBuildConfiguration

from rbbuild.core.runtime_settings import OperationMode
from rbbuild.core.toolchain import default_toolchain_setting

from rbbuild.librbb.user_config_file import UserConfigFile
from rbbuild.librbb.term import term, LogLevel


class RBBConfMain:

    @inject
    def setconf(
        self,
        config_string: str,
        user_config_path: Path = Provide[Application.config.paths.user_config],
        platform: str = Provide[Application.config.settings.platform],
        toolchains: dict = Provide[Application.config.profile.toolchains],
    ):
        # Variable to beautify --getconf
        previous_secstr: str = None

        with UserConfigFile(user_conf_path=user_config_path) as user_data:
            for cfg in config_string.split(','):
                if '=' not in cfg:
                    raise SyntaxError(f'Invalid string "{config_string}"\nExpected "[<section>.]<key>=<value"')

                (key, value) = cfg.split('=', maxsplit=1)
                key, value = default_toolchain_setting(key, value, platform, toolchains or {})
                user_data[key] = value

                # User output
                if '.' in key:
                    (displayed_section, displayed_key) = key.rsplit('.', maxsplit=1)
                else:
                    displayed_key = key
                    displayed_section = 'settings'

                if displayed_section != previous_secstr:
                    term.info(f'[{term.bright_white(displayed_section)}]')
                term.info(f'{displayed_key} = {self._safe_value(displayed_key, value)}')
                previous_secstr = displayed_section



    # Avoid displaying sensitive information such as user credentials
    def _safe_value(self, key: str, value: str) -> str:
        if key in ['login', 'credentials', 'password']:
            return '*' * 8
        return value


    @inject
    def getconf(
        self,
        filterstr: str,
        outfile: str,
        format: str,
        config: dict = Provide[Application.config],
    ):
        # Step 1: Traverse the whole config tree and copy the selected
        # subtrees as defined in "filterstr". Example:
        # "settings.profile" --> {"settings": {"profile": "standalone"}}
        def _make_filtered_tree(data, tokens, new_data=None):
            if not new_data:
                new_data = {}

            for sec, child in data.items():
                if fnmatch(sec, tokens[0]):
                    if len(tokens) > 1 and type(child) is dict:
                        new_data[sec] = _make_filtered_tree(child, tokens[1:], new_data.get(sec))
                    elif type(child) is dict:
                        new_data[sec] = child.copy()
                    else:
                        new_data[sec] = child

            return new_data

        data = _make_filtered_tree(config, filterstr.split('.'))

        def _post_process_tree_data(data):
            for key, value in data.items():
                if type(value) is dict:
                    _post_process_tree_data(value)
                elif isinstance(value, Path):
                    data[key] = str(value)
                # dataclass objects
                elif type(value) is OperationMode:
                    data[key] = asdict(value)
                elif not outfile:
                    data[key] = self._safe_value(key, value)

        _post_process_tree_data(data)

        if format and format.lower() == 'json':
            output_text = json.dumps(data)
        elif not format or format.lower() == 'toml':
            color = not format
            output_text = ''

            def _unfold_config(config: dict, secnames: List[str]=[]):
                for key, value in config.items():
                    if type(value) is dict:
                        yield from _unfold_config(value, secnames + [key])
                    else:
                        yield '.'.join(secnames), key, value

            prev_section = None
            for section, key, value in _unfold_config(data):
                if section != prev_section:
                    if prev_section is not None:
                        output_text += '\n'
                    prev_section = section
                    if color:
                        output_text += f'[{term.bright_white(section)}]\n'
                    else:
                        output_text += f'[{section}]\n'

                if type(value) in [dict, list, set]:
                    output_text += f'{key} = {value}\n'
                elif type(value) is str:
                    output_text += f'{key} = {value!r}\n'
                elif type(value) is None:
                    output_text += f'{key} = None\n'
                else:
                    output_text += f'{key} = {str(value)!r}\n'

        if not outfile:
            term.info(output_text, end='')
        else:
            term.info(f'Writing {outfile} ...')
            with open(outfile, 'w') as fd:
                fd.write(output_text)


    def list(self, targets: str):
        if targets == '*' or targets == 'all':
            targets = 'profiles, channels, services, toolchains'

        for target in targets.split(','):
            target = target.strip()
            if target == 'profiles':
                self.list_profiles()
            elif target == 'channels':
                self.list_channels()
            elif target == 'services':
                self.list_services()
            elif target == 'toolchains':
                self.list_toolchains()
            else:
                raise SyntaxError( f'Invalid argument --list={target}' '\n'
                    'Accepted arguments for --list=<target>:\n'
                   f'- {term.bright_white("profiles")} (default)  -- available profiles' '\n'
                   f'- {term.bright_white("channels")}            -- configured channels' '\n'
                   f'- {term.bright_white("services")}            -- remote services' '\n'
                   f'- {term.bright_white("toolchains")}          -- configured toolchains' '\n' )


    @inject
    def list_profiles(
        self,
        profile: str = Provide[Application.config.settings.profile],
        profiles: dict = Provide[Application.config.profiles],
        rbbuild_config_path: Path = Provide[Application.config.paths.rbbuild_config],
        user_config_path: Path = Provide[Application.config.paths.user_config],
    ):
        term.info(term.bright_white(f'idx  {"name":<15}attributes'))
        term.print_line()
        for i, (name, profile_path) in enumerate(profiles.items()):
            if len(profiles) > 9:
                idxstr = term.bright_white(f'{i+1:>2}')
            else:
                idxstr = term.bright_white(f'{i+1}')

            if name == profile:
                defstr = term.green("*")
            else:
                defstr = ' '

            attrs = []
            toml_path = Path(profile_path)
            if toml_path.is_relative_to(user_config_path / 'profiles'):
                attrs.append(term.cyan('user'))
            elif toml_path.is_relative_to(Path(rbbuild_config_path).parent):
                attrs.append(term.cyan('builtin'))
            else:
                attrs.append(term.cyan('plugin'))

            term.info(f'[{idxstr}] {defstr}{name:<15}{", ".join(attrs)}')
        term.print_line()


    @inject
    def list_services(
        self,
        services_config: dict = Provide[Application.config.profile.services],
    ):
        term.info(term.bright_white(f'{"Service Name":<25}{"Type":<20}{"URL"}'))
        term.print_line()
        for sname, sconf in services_config.items():
            term.info(f'{sname:<25}{sconf["type"]:<20}{term.cyan(sconf.get("url", ""))}')
        term.print_line()


    @inject
    def list_channels(
        self,
        channels: dict = Provide[Application.config.profile.channels],
    ):
        term.info(term.bright_white(f'{"Channel Name":<25}{"Type":<15}{"Service":<20}{"repository":<30}root_path'))
        term.print_line()
        for chname, channel in channels.items():
            term.info(f'{chname:<25}{channel["type"]:<15}{channel.get("remote_service", ""):<20}{channel.get("repository", ""):<30}{term.cyan(channel.get("root_path", ""))}')
        term.print_line()


    @inject
    def list_toolchains(
        self,
        toolchains: dict = Provide[Application.config.profile.toolchains],
    ):
        term.info(term.bright_white(f'{"Platform":<15}{"Toolchain ID":<25}{"Toolchain File"}'))
        term.print_line()
        for toolchain in toolchains.values():
            term.info(f'{toolchain["platform"]:<15}{toolchain["tcid"]:<25}{term.cyan(str(toolchain["cmake_file"]))}')
        term.print_line()


    def main(self, args):
        # -l / --list=<target>
        if args.list:
            self.list(args.list)

        # --setconf=<OPTIONS>
        elif args.setconf:
            self.setconf(args.setconf)

        # --getconf=<FILTER>
        elif args.getconf:
            self.getconf(args.getconf, outfile=args.outfile, format=args.format)


def parse_command_line():
    parser = argparse.ArgumentParser(description='rbbconf -- Robert Bosch rbbuild configuration tool')
    parser.add_argument( '-l', '--list',            action='store',       metavar='CATEGORY', nargs='?', const='*',   help='List information per category (profiles|toolchains|channels|services|all). Default: all.' )
    parser.add_argument( '-s', '--setconf',         action='store',       metavar='OPTIONS',                          help='Set config option [<section>.]<key>=<value>[,<...>], with <section> defaulting to settings' )
    parser.add_argument( '-g', '--getconf',         action='store',       const='*', nargs='?', metavar='FILTER',                help='Print config options. If FILTER is defined: filter for <section>.<key>.')
    parser.add_argument( '-o', '--outfile',         action='store',                                                   help='Output file')
    parser.add_argument(       '--format',          action='store',                                                   help='Select output format. One of: JSON, TOML.')
    parser.add_argument( '-f', '--force',           action='store_const', const=True, default=False,                  help='Force action' )
    parser.add_argument( '-v', '--verbose',         action='store_const', const=True, default=False, help='Verbose output' )
    parser.add_argument( '-n', '--dry-run',         action='store_const', const=True, default=False, help='Do not actually publish, only dry run (--publish)' )
    parser.add_argument( '-t', '--toolchain',       action='store',       dest='tcid',                                help='Select toolchain by name or ID' )
    parser.add_argument(       '--platform',        action='store',                                                   help='Specify target platform' )
    parser.add_argument( '-P', '--profile',         action='store',                                                   help='Select profile' )
    parser.add_argument(       '--ignore-errors',   action='store_const', const=True, default=False,                  help='Ignore dependency errors' )
    parser.add_argument(       '--log-level',       action='store',       dest='log_level',                           help='Highest log level: %s. Default: INFO' % ', '.join(LogLevel.__members__.keys()))
    return parser.parse_args()


def run():
    args = parse_command_line()
    # --log-level
    term.log_level = args.log_level

    rbbuild_root_path = Path(
        os.environ.get('RBB_ROOT') or
        Path(__file__).resolve().parent
    ).absolute()
    rbbuild_config_path = Path(
        os.environ.get('RBB_CONFIG_PATH') or
        data_path() / 'config'
    ).absolute()

    try:
        config = RBBuildConfiguration()
        config.load_configuration(rbbuild_root_path, rbbuild_config_path)

        rbbconf = RBBConfMain()

        # Load CLI overrides
        config.load_cli(**vars(args))

        config.load_profile(
            profile_name=config.settings.profile(),
            rbbuild_config_path=rbbuild_config_path,
            user_config_path=Path(config.paths.user_config()),
        )

        application = Application(config=config)
        application.wire(modules=[__name__])

        rbbconf.main(args)
    except Exception as e:
        import traceback
        term.error('failed', e)
        term.debug('Exception stack', traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    run()

