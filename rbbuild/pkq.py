#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import argparse
import json
import os
import sys

from copy import copy
from dependency_injector.wiring import Provide, inject
from pathlib import Path
from typing import List

from rbbuild.core.channel import Channel
from rbbuild.core.runtime_settings import OperationMode
from rbbuild.core.toolchain import Toolchain
from rbbuild import data_path
from rbbuild.container.application import Application
from rbbuild.container.configuration import RBBuildConfiguration

from rbbuild.deps.parser import DepsParser
from rbbuild.deps.serializer import Serializer
from rbbuild.librbb.term import term,LogLevel
from rbbuild.package.diff import PackageDiff
from rbbuild.package.package import Package
from rbbuild.query.query import Query
from rbbuild.resolver.resolver import Resolver

from rbbuild.buildsystem.deps_file import DepsFile

from rbbuild.service.scm.manager import SCMManager
from rbbuild.service.repository.manager import RepositoryManager
from rbbuild.service.issuetracker.issuetracker_manager import IssueTrackerManager


class PackageQueryMain:

    @inject
    def resolve(
        self,
        outfile: str,
        deps_file: DepsFile = Provide[Application.buildsystem.deps_file],
        dependencies_config: list = Provide[Application.config.dependencies],
        resolver: Resolver = Provide[Application.resolver.resolver],
        op_mode: OperationMode = Provide[Application.config.op_mode],
    ):
        dependencies = deps_file.from_config(dependencies_config or [])

        resolved = {}
        problems = []
        for namespace, entries in dependencies.items():
            result = resolver.run(entries, transitive=True, skip_build_only=True)
            resolved[namespace] = result.packages
            problems.extend(result.problems)

        if problems:
            raise RuntimeError('\n'.join(problems))

        toml_output = Serializer().resolved_dict_to_toml(resolved)

        if not outfile:
            term.stdout(toml_output)
        else:
            if os.path.exists(outfile) and not op_mode.force:
                raise FileExistsError(f'Output file {term.bright_white(outfile)} already exists. Retry with -f.')
            with open(outfile, 'w') as fd:
                fd.write(toml_output)


    @inject
    def _list_package_versions(
        self,
        pkg: Package,
        max_query_items: int,
        channel: Channel,
        toolchain: Toolchain,
        query_service: Query = Provide[Application.query.query],
    ) -> bool:
        term.info(term.bright_white(str(pkg)))
        try:
            query_service.query(
                pkg=pkg,
                channel=channel,
                toolchain=toolchain,
                report_progress=lambda *_: None,
            )
        except LookupError:
            term.warning('Package not found', str(pkg))
            return False

        for count, (pkg_out, _) in enumerate(query_service.entries, start=1):
            term.info(f'[{term.green("*")}] {pkg_out!s}')
            if max_query_items > 0 and count >= max_query_items:
                break
        return True


    @inject
    def _show_package_details(
        self,
        pkg: Package,
        all_toolchains: bool,
        repoman: RepositoryManager = Provide[Application.service.repository.repoman],
        toolchain: Toolchain = Provide[Application.core.toolchain],
    ) -> bool:
        term.info(term.bright_white(str(pkg)))
        if all_toolchains:
            details = list(repoman.search_toolchains(pkg=pkg))
        else:
            if not pkg.toolchain:
                pkg.toolchain = toolchain
            details = list(repoman.search(pkg=pkg))

        if not details:
            if not all_toolchains and pkg.toolchain:
                probe = copy(pkg)
                probe.toolchain = None
                available = sorted({
                    str(detail.toolchain)
                    for detail in repoman.search_toolchains(pkg=probe)
                    if detail.toolchain
                })
                if available:
                    term.warning(
                        str(pkg.toolchain), 'Package not available for selected toolchain. Available:\n',
                        f'  {"\n  ".join(available)}',
                    )
                    return False

            term.warning('Package not found', str(pkg))
            return False

        selected_str = str(toolchain) if toolchain else None
        for i, detail in enumerate(details):
            if i > 0:
                term.info('')

            if detail.purl:
                term.info(f'  PURL:       {term.cyan(str(detail.purl))}')
            if detail.components:
                term.info('  components:')
                for comp in detail.components:
                    checksum = f' ({term.cyan(comp.checksum)})' if comp.checksum else ''
                    term.info(f'    {comp.name}  {comp.filename}{checksum}')

            if detail.channel:
                term.info(f'  channel:    {term.cyan(detail.channel.name)}')
                if detail.toolchain:
                    tc_str = str(detail.toolchain)
                    label = term.bright_white(tc_str) if tc_str == selected_str else tc_str
                    term.info(f'  toolchain:  {label}')
                if detail.url:
                    term.info(f'  url:        {term.cyan(detail.url)}')
                if detail.git_repo:
                    term.info(f'  git repo:   {detail.git_repo}')
                if detail.git_hash:
                    term.info(f'  git hash:   {term.cyan(detail.git_hash)}')
                if detail.dependencies:
                    term.info('  dependencies:')
                    for child in detail.dependencies:
                        term.info(f'    {child!s}')
        return True


    @inject
    def list_packages(
        self,
        packages: List[str],
        max_query_items,
        all_toolchains: bool = False,
        deps_parser: DepsParser = Provide[Application.deps.parser],
        query_service: Query = Provide[Application.query.query],
        channel: Channel = Provide[Application.core.channel],
        toolchain: Toolchain = Provide[Application.core.toolchain],
    ):
        try:
            max_query_items = int(max_query_items)
        except ValueError:
            raise ValueError(f'Invalid argument: expected number argument (was: {term.bright_white("pkq -l " + max_query_items)})')

        # Mode 1: list all package names
        if not packages:
            term.info(f'Packages in channel {term.bright_white(str(channel))}:')
            query_service.query(text='', channel=channel, toolchain=toolchain, report_progress=lambda *_: None)
            for pkg_out, _ in query_service.entries:
                term.info(f'[{term.green("*")}] {pkg_out.name}')
            return

        had_errors = False
        for pkg_items, attrs in deps_parser.walk([{'deps': packages}]):
            for item in pkg_items:
                pkg = deps_parser.parse_item(item, attrs)

                if pkg.version is None:
                    # Mode 2: list versions in reverse order of specified packages
                    if not self._list_package_versions(pkg, max_query_items, channel, toolchain):
                        had_errors = True
                else:
                    # Mode 3: pinned version → show detail info for the selected
                    # toolchain. With --all-toolchains, every toolchain
                    # configured in the profile is tried instead.
                    if not self._show_package_details(pkg, all_toolchains):
                        had_errors = True

        if had_errors:
            raise RuntimeError('One or more packages could not be processed')


    @inject
    def tree(
        self,
        packages: List[str],
        channel: Channel = Provide[Application.core.channel],
        toolchain: Toolchain = Provide[Application.core.toolchain],
        query_service: Query = Provide[Application.query.query],
    ):
        had_errors = False
        for qpkg in packages:
            try:
                query_service.query(
                    text=qpkg,
                    channel=channel,
                    toolchain=toolchain,
                    report_progress=lambda *_: None,
                )
            except LookupError:
                term.warning('Package not found', qpkg)
                had_errors = True
                continue

            for pkg, depth in query_service.entries:
                if depth == 0:
                    term.info(term.bright_white(str(pkg)))
                    continue
                outstr = f'{pkg.name}-{term.cyan(pkg.version)}'
                if pkg.build_only:
                    outstr += f' ({term.yellow("build_only")})'
                if not pkg.traverse:
                    outstr += f' ({term.yellow("traverse=0")})'
                # entries' depth is 1-based (root is 0); Query.entries numbers
                # direct children starting at 1 for the GUI's tree nesting.
                term.info(f'{(depth-1)*"    "}{outstr}')

        if had_errors:
            raise RuntimeError('One or more packages could not be found')


    @inject
    def manifest(
        self,
        packages: List[str],
        outfile: str,
        repoman: RepositoryManager = Provide[Application.service.repository.repoman],
    ):
        had_errors = False
        for qpkg in packages:
            matches = list(repoman.search(deps_item=qpkg))

            if not matches:
                term.warning('Package not found', qpkg)
                had_errors = True
                continue

            for pkg in matches:
                manifest_path = pkg.manifest.localpath
                with open(manifest_path, 'r') as fd:
                    manifest = fd.read()
                if not outfile:
                   term.info(f'Content of "manifest.json" file ({pkg!s}):')
                   term.print_line()
                   term.stdout(manifest)
                   term.print_line()
                else:
                   with open(outfile, 'w') as fd:
                       json.dump(manifest, fd, indent=4)

        if had_errors:
            raise RuntimeError('One or more packages could not be found')


    @inject
    def changes(
        self,
        changes_range: str,
        channel: Channel = Provide[Application.core.channel],
        toolchain: Toolchain = Provide[Application.core.toolchain],
        query_service: Query = Provide[Application.query.query],
        deps_parser: DepsParser = Provide[Application.deps.parser],
        package_diff: PackageDiff = Provide[Application.package.diff],
        scmman: SCMManager = Provide[Application.service.scm.scmman],
        issueman: IssueTrackerManager = Provide[Application.service.issuetracker.issueman],
    ):
        # Identical versions: nothing to show.
        prev_str, cur_str = deps_parser.parse_deps_range(changes_range)
        if prev_str == cur_str:
            return

        query_service.query(
            text=changes_range,
            channel=channel,
            toolchain=toolchain,
            report_progress=lambda *_: None,
        )

        entries = query_service.cmp_entries
        if not entries:
            return

        root_res, _ = entries[0]
        for text in package_diff.get_compare_text(root_res, scmman, issueman):
            if text:
                term.info(text)

        if len(entries) > 1:
            term.print_line()
            for cmp_res, _ in entries[1:]:
                for text in package_diff.get_compare_text(cmp_res, scmman, issueman):
                    if text:
                        term.info(text)
            term.print_line()


    @inject
    def jira_release(
        self,
        key: str,
        issueman: IssueTrackerManager = Provide[Application.service.issuetracker.issueman],
    ):
        jira = issueman.service(key)

        term.info(f'{term.bright_white("Fix Version") : <40}\t{term.bright_white("Description") : <55}\t{term.bright_white("Release Date")}')
        term.print_line()
        for rel in jira.release_versions():
            if rel.archived is not False:
                continue
            if rel.released is True:
                continue
            term.info(f'{term.cyan(rel.name) : <40}\t{rel.description : <40}\t{rel.release_date}')
        term.print_line()


    # --changelog=<jira-id>:<release-version>
    def jira_changelog(
        self,
        changelog: str,
    ):
        if ':' not in changelog:
            raise SyntaxError(f'Invalid argument --changelog={changelog}. Expected format: <jira-id>:<release-version>')

        key, version = changelog.split(':', maxsplit=1)

        term.info(f'Release information {version} ({key})')
        query = f'{key}:fixVersion={version}'
        self.jira_query(query)


    @inject
    def jira_query(
        self,
        jql_string: str,
        issueman: IssueTrackerManager = Provide[Application.service.issuetracker.issueman],
    ):
        if ':' not in jql_string:
            raise SyntaxError(f'Invalid argument --jql={jql_string}. Expected format: <jira-id>:<jql-string>')

        key, jql = jql_string.split(':', maxsplit=1)
        jira = issueman.service(key)

        term.print_line()
        for issue in jira.search(query=jql):
            term.info(f'{term.cyan(issue.key)} ({issue.status_colored}): {issue.summary}')
        term.print_line()


    # Usage: pkq -r <package> [<parent> ...]
    @inject
    def reverse_search(
        self,
        package: str,
        parents: List[str],
        deps_parser: DepsParser = Provide[Application.deps.parser],
        repoman: RepositoryManager = Provide[Application.service.repository.repoman],
        resolver: Resolver = Provide[Application.resolver.resolver],
        op_mode: OperationMode = Provide[Application.config.op_mode],
    ):
        pkg = None
        for pkg in repoman.search_versions(deps_item=package):
            break

        if not pkg:
            raise RuntimeError(f'Could not resolve {term.bright_white(package)} to a valid package')

        # Explicitly named parents warn on a miss; the auto-discovered "search
        # every package" fallback naturally won't match most of them.
        explicit_parents = bool(parents)
        if not parents:
            parents = repoman.list_package_names()

        term.info(f'{term.bright_white(str(pkg))} is contained in ... ')
        had_errors = False
        for qpkg in parents:
            matches = list(repoman.search(deps_item=qpkg))

            if not matches:
                if explicit_parents:
                    term.warning('Package not found', qpkg)
                    had_errors = True
                continue

            for parent in matches:
                found = None
                for candidate in resolver.collect(this=parent, pkg_in=parent).packages.values():
                    if candidate.version == pkg.version:
                        found = True
                        break
                if found:
                    term.info(f'[{term.green("*")}] {parent!s}')
                elif op_mode.verbose:
                    term.info(f'[{term.red("x")}] {parent!s}')

        if had_errors:
            raise RuntimeError('One or more parent packages could not be found')


    def main(
        self,
        args,
    ):
        # --version
        if args.version:
            from rbbuild.version import __version__
            term.info(__version__)
            return

        changes_range = None

        # pkq <pkg_old>..<pkg_new>
        if args.package and '..' in args.package[0]:
            if len(args.package) > 1:
                term.error('Invalid arguments', 'Cannot handle multiple inputs with range syntax (<pkg>..<pkg>)')
                sys.exit(1)
            changes_range = args.package[0]

        # Process standard in
        elif args.stdin:
            # read from standard in
            if sys.platform == 'win32':
                terminal_end = 'CTRL-Z'
            else:
                terminal_end = 'CTRL-D'

            if sys.stdin.isatty():
                term.info(f'Reading from standard input (type {terminal_end} to finish)')
                term.print_line()

            args.package = []
            for pkgstr in sys.stdin:
                pkgstr = pkgstr.strip()
                if not len(pkgstr) or pkgstr.startswith('#'):
                    continue
                args.package.append(pkgstr)
            if sys.stdin.isatty():
                term.print_line()


        #####################################################################
        # At this point, all configuration and initialization is done.      #
        #####################################################################

        # pkq -R/--resolve
        if args.resolve:
            self.resolve(outfile=args.out)

        # pkq --list
        elif args.list:
            self.list_packages(args.package, args.max_query_items, all_toolchains=args.all_toolchains)

        # pkq --tree
        elif args.tree:
            self.tree(args.package)

        # pkq --manifest
        elif args.manifest:
            self.manifest(args.package, outfile=args.out)

        # pkq <prev>..<cur> (changes)
        elif changes_range:
            self.changes(changes_range)

        # -J/--jira-releases=<jira_project_id>
        elif args.jira_releases:
            self.jira_release(args.jira_releases)

        # --changelog=<jira-id>:<release-version>
        elif args.changelog:
            self.jira_changelog(args.changelog)

        # --jql=<jira-id>:<jql-string>
        elif args.jql:
            self.jira_query(args.jql)

        # -r/--reverse-search=<package> [<parent> ...]
        elif args.reverse_search:
            self.reverse_search(
                package=args.reverse_search,
                parents=args.package,
            )


def parse_command_line(cmdline=None):
    parser = argparse.ArgumentParser(description='pkq -- Robert Bosch package query tool from binary repositories (Artifactory)')
    parser.add_argument( '-o', '--out',               action='store',        dest='out',                help='Output file' )
    parser.add_argument( '-s', '--source-dir',        action='store',        dest='source_dir',         help='Source directory for dependency lookup (default: current directory)' )
    parser.add_argument( '-t', '--toolchain',         action='store',        dest='tcid',               help='Select toolchain by name or ID' )
    parser.add_argument( '-v', '--verbose',           action='store_const',  const=True, default=False, help='Verbose output' )
    parser.add_argument( '-f', '--force',             action='store_const',  const=True, default=False, help='Force action' )
    parser.add_argument( '-P', '--profile',           action='store',                                   help='Select profile' )
    parser.add_argument( '-',  '--stdin',             action='store_const',  const=True, default=False, help='Read packages from console standard in (disables GUI)')
    parser.add_argument( '-C', '--channel',        action='store',        dest='channel',            help='Select a channel' )
    parser.add_argument(       '--platform',          action='store',        dest='platform',           help='Specify target platform' )

    parser.add_argument( '-r', '--reverse-search',    action='store',        metavar='pattern',         help='Return all parent packages matching "pattern" that contain "package": pkq -r <pattern> <package> [<package> ...]')
    parser.add_argument( '-R', '--resolve',           action='store_const',  const=True, default=False, help='Resolve package versions. Use with -o to write deps.json file.')
    parser.add_argument(       '--diff-mode',         action='store',        dest='diffmode', nargs='?', default='basic',   help='Diff mode: basic (minimal JIRA), commits (minimal git), jira (details), git (details)')
    parser.add_argument(       '--filter-changes',    action='store',        dest='filter_changes', nargs='?', default='new,deleted,changed,moved', help='Specify change filter (default: new,deleted,changed,moved)')
    parser.add_argument(       '--jql',               action='store',        nargs='?', help='Perform JQL query and print matching tickets. Syntax: <jira-id>:<jql-string>')
    parser.add_argument(       '--changelog',         action='store',        nargs='?', help='Retrieve Jira tickets from <jira-id>:<release-version>')
    parser.add_argument( '-J', '--jira-releases',     action='store',        dest='jira_releases', nargs='?', help='List Jira releases from <jira-id>')
    parser.add_argument( '-l', '--list',              action='store_const',  const=True, default=False, help='List all available versions')
    parser.add_argument(       '--max-query-items',   action='store',        dest='max_query_items', default=10, help='Maximum number of items to show (use with --list)')
    parser.add_argument(       '--all-toolchains',    action='store_const',  dest='all_toolchains', const=True, default=False, help='Mode 3 (pinned version, use with --list): show details for every toolchain configured in the profile instead of just the selected one')
    parser.add_argument(       '--tree',              action='store_const',  const=True, default=False, help='Print out dependency tree' )
    # parser.add_argument(       '--max-depth',        action='store',        default=0, dest='max_tree_depth', nargs='?',  help='Maximum depth of tree to display (use with --tree)' )
    parser.add_argument(       '--manifest',          action='store',        dest='manifest', nargs='?', default=None, const=sys.stdout, help='Write out manifest file' )
    parser.add_argument(       '--no-traverse',       action='store_const',  const=True, default=False, help='Do not traverse the tree but only take the top-most entries.' )
    parser.add_argument(       '--ignore-errors',     action='store_const',  const=True, default=False, help='Ignore dependency errors' )
    parser.add_argument(       '--log-level',         action='store',        dest='log_level',          help='Highest log level: %s. Default: INFO' % ', '.join(LogLevel.__members__.keys()))
    parser.add_argument(       '--version',           action='store_const',  const=True, default=False, help='Display version and exit' )
    parser.add_argument(       '--offline',           action='store_const',  const=True, default=False, help='Do not connect to a server, work with download cache only' )

    # Optional make targets
    parser.add_argument('package',                 metavar='package',      nargs='*',                help='Package string. Syntax: [<channel>:]<pkgname>[-<version>]')
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

        # Load project configuration when resolving dependencies
        if args.resolve:
            source_dir = Path(args.source_dir) if args.source_dir else Path.cwd()
            config.load_project_configuration(source_dir)

        pkgquery = PackageQueryMain()

        application = Application(config=config)
        application.wire(modules=[__name__])

        pkgquery.main(args)
    except Exception as e:
        import traceback
        term.error('failed', e)
        term.debug('Exception stack', traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    run()

