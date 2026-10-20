#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import sys
import argparse
import json
import os
import time

from dependency_injector.wiring import Provide, inject
from pathlib import Path

from rbbuild import data_path
from rbbuild.container.application import Application
from rbbuild.container.configuration import RBBuildConfiguration

from rbbuild.core.channel import Channel
from rbbuild.core.runtime_settings import OperationMode

from rbbuild.deps.parser import DepsParser
from rbbuild.package.package import Package
from rbbuild.resolver.resolver import Resolver
from rbbuild.service.repository.manager import RepositoryManager
from rbbuild.service.scm.manager import SCMManager
from rbbuild.librbb.term import term, LogLevel


class PromoteMain:

    @inject
    def do_promote(
        self,
        qpkglist,
        channel_map,
        n_start,
        n_end,
        tag: bool = False,
        deps_parser: DepsParser = Provide[Application.deps.parser],
        resolver: Resolver = Provide[Application.resolver.resolver],
        repoman: RepositoryManager = Provide[Application.service.repository.repoman],
        scmman: SCMManager = Provide[Application.service.scm.scmman],
        op_mode: OperationMode = Provide[Application.config.op_mode],
    ):
        incr = 1 if n_start < n_end else -1
        if n_start < 0 or n_end < 0 or n_end > len(qpkglist) or n_start > len(qpkglist):
            raise RuntimeError('Invalid range')
        n_packages = abs(n_end - n_start)
        if n_packages != 1:
            term.info(f'Promoting {term.magenta(str(n_packages))} packages ...')
            term.info(f'First package [{term.magenta(str(n_start))}]:\t{term.bright_white(qpkglist[n_start])}')
            term.info(f'Last package [{term.magenta(str(n_end-1))}]:\t{term.bright_white(qpkglist[n_end-1])}')

        for n in range(n_start, n_end, incr):
            qpkg = qpkglist[n]

            try:
                pkg = deps_parser.parse_item(qpkg)

                if op_mode.dry_run:
                    # Skip all network calls in dry-run mode.
                    # If the package string carries an explicit channel prefix, use
                    # that channel's mapping; otherwise show all mapped channels.
                    if pkg.channel:
                        dst_ch = channel_map.get(pkg.channel.name)
                        if dst_ch:
                            term.info(f'Promoting [{term.magenta(str(n))}] {term.bright_white(qpkg)} {term.cyan(pkg.channel.name)} \u2192 {term.cyan(dst_ch.name)} (dry run)')
                        else:
                            term.warning('skipped', f'{qpkg}: no mapping defined for channel {pkg.channel.name}')
                    else:
                        for src_name, dst_ch in channel_map.items():
                            term.info(f'Promoting [{term.magenta(str(n))}] {term.bright_white(qpkg)} {term.cyan(src_name)} \u2192 {term.cyan(dst_ch.name)} (dry run)')
                    continue

                result = resolver.run({repr(pkg): pkg}, transitive=op_mode.transitive)
                if result.problems:
                    raise LookupError('\n'.join(result.problems))

                for pkgname, pkg in result.packages.items():
                    destination_channel = channel_map.get(pkg.channel.name)
                    if not destination_channel:
                        msg = f'{pkgname}: no mapping defined for channel {pkg.channel.name}'
                        term.warning('skipped', msg)
                        continue

                    msg = f'Promoting [{term.magenta(str(n))}] {term.bright_white(str(pkg))} {term.cyan(pkg.channel.name)} \u2192 {term.cyan(destination_channel.name)}'
                    if op_mode.dry_run:
                        msg += ' (dry run)'
                    msg += ' ... '
                    term.info(msg)

                    n_comp = 0
                    n_skipped = 0
                    for comp in repoman.promote(pkg=pkg, destination_channel=destination_channel):
                        if not comp:
                            n_skipped += 1
                        n_comp += 1

                    term.info(f'Uploaded {n_comp-n_skipped}/{n_comp} files')
                    if tag:
                        if pkg.git_repo and pkg.git_hash:
                            tag_name = pkg.version
                            try:
                                term.info(f'Tagging {term.bright_white(str(pkg))} with {term.cyan(tag_name)} ... ', end='')
                                scm = scmman.service(url=pkg.git_repo)
                                created = scm.create_tag(tag_name=tag_name, commit_hash=pkg.git_hash)
                                term.info('ok' if created else 'already exists')
                            except Exception as e:
                                term.error(f'Failed to tag: {e}')
                        else:
                            term.warning('skipped', f'{pkg}: no git_repo or git_hash in manifest')

            except (SyntaxError, LookupError) as ex:
                # Manifest errors and dependency resolution problems
                term.error('failed', f'{qpkg}: {str(ex)}')

                if op_mode.ignore_errors:
                    continue
                else:
                    raise ex

            except Exception as ex:
                # Assuming all other problems are connection-related.
                term.error('failed', f'{qpkg}: {str(ex)}')
                # Avoid subsequently running into the same error in case of
                # networking-related issues.
                time.sleep(1)
                raise ex



    @inject
    def main(
        self,
        args,
        channels_config: dict = Provide[Application.config.profile.channels],
        repoman: RepositoryManager = Provide[Application.service.repository.repoman],
    ):
        channel_map_str = {}

        if args.channel_map:
            for mapping in args.channel_map.split(','):
                if ':' not in mapping:
                    raise SyntaxError('Invalid argument: expected syntax -m <in>:<out>[,<in>:<out>...]')
                key, value = mapping.split(':', maxsplit=1)
                channel_map_str[key] = value
        elif args.map_file:
            if not Path(args.map_file).exists():
                raise RuntimeError(f'Channel mapping file does not exists {args.map_file}')

            with open(args.map_file, 'r') as fd:
                if args.map_file.lower().endswith('.json'):
                    channel_map_str = json.load(fd)
                else:
                    for line in fd:
                        line = line.strip()
                        if ':' not in line:
                            raise SyntaxError('Invalid item in channel map: expected syntax <in>:<out>[,<in>:<out>...]')
                        key, value = line.split(':', maxsplit=1)
                        channel_map_str[key] = value

        if not channel_map_str:
            raise RuntimeError('Invalid argument: no channel mapping found')

        channel_map = {}         # source channel name → target Channel object
        source_channels = {}     # source channel name → source Channel object
        for chin, chout in channel_map_str.items():
            try:
                source_channel = Channel(name=chin, default_channel=chin, channels_config=channels_config, source_path='')
            except LookupError:
                raise RuntimeError(f'Failed to resolve channel {chin}')

            try:
                target_channel = Channel(name=chout, default_channel=chout, channels_config=channels_config, source_path='')
            except LookupError:
                raise RuntimeError(f'Failed to resolve channel {chout}')

            if source_channel.name == target_channel.name:
                raise RuntimeError('Source and destination channels are the same')

            channel_map[source_channel.name] = target_channel
            source_channels[source_channel.name] = source_channel

        qpkglist = []
        # 1. gather: list all packages from each source channel and write to file
        if args.package_list_file:
            term.info('Gathering packages ... ')
            for src_ch in source_channels.values():
                for pkgname in repoman.list_package_names(channel=src_ch):
                    for pkg in repoman.search_versions(pkg=Package(name=pkgname), channel=src_ch):
                        entry = f'{src_ch.name}:{pkg.name}-{pkg.version}'
                        term.redraw_last_line(term.cyan(entry))
                        qpkglist.append(entry)
            term.info()

            term.info(f'Writing {args.package_list_file} ...')
            with open(args.package_list_file, 'w') as fd:
                for qpkg in qpkglist:
                    fd.write(qpkg + '\n')
            term.info(f'Wrote {len(qpkglist)} entries')

            sys.exit(0)


        # 2. input file and range
        if args.input_list_file:
            term.info(f'Reading {args.input_list_file} ...')
            with open(args.input_list_file, 'r') as fd:
                for line in fd:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    qpkglist.append(line)


        elif args.all_packages:
            term.info('Gathering packages ... ', end='', flush=True)
            for src_ch in source_channels.values():
                for pkgname in repoman.list_package_names(channel=src_ch):
                    for pkg in repoman.search_versions(pkg=Package(name=pkgname), channel=src_ch):
                        entry = f'{src_ch.name}:{pkg.name}-{pkg.version}'
                        term.redraw_last_line(term.cyan(entry))
                        qpkglist.append(entry)

            term.info()
            term.info(f'Promoting {term.bright_white(str(len(qpkglist)))} packages')

        else:
            if args.package:
                qpkglist = [args.package]
            else:
                if sys.platform == 'win32':
                    terminal_end = 'CTRL-Z'
                elif sys.platform == 'linux':
                    terminal_end = 'CTRL-D'
                else:
                    raise Exception(f'Unknown platform "{sys.platform}"')
                term.info(f'Reading from standard input (type {term.bright_white(terminal_end)} to finish)')
                term.print_line()
                for pkgstr in sys.stdin:
                    pkgstr = pkgstr.strip()
                    if not len(pkgstr) or pkgstr.startswith('#'):
                        continue
                    qpkglist.append(pkgstr)
                term.print_line()

        # --retries=<n>
        num_attempts = 1
        retries = 0
        if args.retries:
            retries = int(args.retries)
            if retries < 0:
                num_attempts = -1
            else:
                num_attempts += retries

        if not qpkglist:
            term.info('No packages specified')
            sys.exit(0)
        n_entries = len(qpkglist)
        term.debug('run', f'List contains {n_entries} entries.')
        while num_attempts != 0:
            try:
                # Optional: range
                n_start = 0
                n_end = n_entries
                if args.range:
                    range_input = args.range.split('-', maxsplit=1)
                    if range_input[0] == '':
                        n_end = int(range_input[1])
                    elif range_input[1] == '':
                        n_start = int(range_input[0])
                    else:
                        n_start, n_end = tuple(list(map(int, range_input)))

                self.do_promote(qpkglist, channel_map, n_start, n_end, tag=args.tag)
                num_attempts = 0

            except KeyboardInterrupt:
                term.info('\nTerminating after KeyboardInterrupt')
                sys.exit(0)

            except Exception:
                if retries != 0 and num_attempts > 0:
                    num_attempts -= 1
                    term.info('Retry after exception ...')
                else:
                    raise

                term.print_line()


def parse_command_line(cmdline=None):
    parser = argparse.ArgumentParser(description='promote -- Robert Bosch tool to promote packages')
    parser.add_argument( '-m', '--channel-map',    action='store',        dest='channel_map',        help='Channel mappings of form <in>:<out>[,<in>:<out>...]' )
    parser.add_argument( '-M', '--map-file',       action='store',        dest='map_file',           help='Path to file with channel mappings' )
    parser.add_argument( '-t', '--toolchain',      action='store',        dest='tcid',               help='Select toolchain by name or ID' )
    parser.add_argument( '-n', '--dry-run',        action='store_const',  const=True, default=False, help='Only show operations that would be executed' )
    parser.add_argument( '-f', '--force',          action='store_const',  const=True, default=False, help='Force action' )
    parser.add_argument( '-P', '--profile',        action='store',                                   help='Select profile' )
    parser.add_argument( '-g', '--gather',         action='store',        dest='package_list_file',  help='Create package list file (plain text file) and exit' )
    parser.add_argument( '-i', '--input-file',     action='store',        dest='input_list_file',    help='Use package list file (generated with --gather) as input for promote' )
    parser.add_argument(       '--range',          action='store',        dest='range',              help='Range for --input-file (e.g. 0-100). Only the specified indeces will be promoted' )
    parser.add_argument( '-A', '--all-packages',   action='store_const',  const=True, default=False, help='Promote all packages' )
    parser.add_argument(       '--retries',        action='store',                                   help='Number of retries on failure (default: 0, infinite number of retries if negative' )
    parser.add_argument(       '--no-traverse',    action='store_const',  const=True, default=False, help='Do not traverse the tree but only take the top-most entries.' )
    parser.add_argument(       '--platform',       action='store',        dest='platform',           help='Specify target platform' )
    parser.add_argument(       '--ignore-errors',  action='store_const',  const=True, default=False, help='Ignore dependency errors' )
    parser.add_argument(       '--log-level',      action='store',        dest='log_level',          help='Highest log level: %s. Default: INFO' % ', '.join(LogLevel.__members__.keys()))
    parser.add_argument(       '--offline',        action='store_const',  const=True, default=False, help='Do not connect to a server, work with download cache only' )
    parser.add_argument('-T', '--tag',             action='store_const',  const=True, default=False, help='Tags the git hash for all the components being promoted with the version number')

    # Optional make targets
    parser.add_argument('package',                 metavar='package',      nargs='?',              help='Package to promote. Syntax: [<channel>:]<pkgname>[-<version>]')

    return parser.parse_args(args=cmdline)


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

        config.load_cli_profile(**vars(args))
        config.load_profile(
            profile_name=config.settings.profile(),
            rbbuild_config_path=rbbuild_config_path,
            user_config_path=Path(config.paths.user_config()),
        )

        # Load CLI overrides
        config.load_cli(**vars(args))

        promote = PromoteMain()

        application = Application(config=config)
        application.wire(modules=[__name__])

        promote.main(args)
    except Exception as e:
        import traceback
        term.error('failed', e)
        term.debug('Exception stack', traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    run()
