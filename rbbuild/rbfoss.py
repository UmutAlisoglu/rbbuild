#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import argparse
import itertools
import json
import os
import sys
import tomllib

from dependency_injector.wiring import Provide, inject
from pathlib import Path

from rbbuild import data_path
from rbbuild.container.application import Application
from rbbuild.container.configuration import RBBuildConfiguration

from rbbuild.core.paths import Paths
from rbbuild.librbb.term import term, LogLevel
from rbbuild.package.package import Package
from rbbuild.package.parser import ManifestJSONParser
from rbbuild.resolver.resolver import Resolver
from rbbuild.service.oss.fossid import FossID, FossIDScanEntry, IgnoreRuleType
from rbbuild.service.oss.oss_manager import OSSManager
from rbbuild.service.licensedb import LicenseDB

import rbbuild.rbfoss as rbfoss_mod


class RBFossMain:
    def __init__(self):
        self._mypkg: Package = None


    @inject
    def make_mypkg(
        self,
        paths: Paths = Provide[Application.core.paths],
        manifest_parser: ManifestJSONParser = Provide[Application.package.parser],
    ) -> Package:
        manifest_path = paths.build / 'manifest.json'
        with open(manifest_path, 'r') as jfd:
            manifest = json.load(jfd)
        mypkg = manifest_parser.parse(manifest)
        if not mypkg:
            raise RuntimeError(f'Failed to parse {manifest_path}')
        return mypkg


    @property
    def mypkg(self) -> Package:
        if not self._mypkg:
            self._mypkg = self.make_mypkg()
        return self._mypkg


    def _get_oss(self, oss_man: OSSManager):
        names = list(oss_man.names())
        if not names:
            raise RuntimeError('No OSS configuration found in the current profile!')
        name = names[0]
        return name, oss_man.service(name), oss_man.oss_config(name)


    @inject
    def clean(self, force: bool, oss_man: OSSManager = Provide[Application.service.oss.ossman]) -> None:
        _, fossid, _ = self._get_oss(oss_man)
        fossid_project = fossid.get_project(self.mypkg)
        if not fossid_project:
            term.warning(repr(self.mypkg), f'FossID project {term.bright_white(fossid.project_code(self.mypkg))} not found!')
            return

        fossid_scan = fossid.get_scan(self.mypkg, fossid_project)
        if not fossid_scan:
            term.warning(repr(self.mypkg), f'FossID scan {term.bright_white(fossid.scan_code(self.mypkg))} not found!')
        else:
            fossid.cancel_run(fossid_scan)
            fossid.delete_scan(fossid_scan)
            term.info(f'[{term.green("*")}]', f'Deleted FossID scan {term.bright_white(fossid.scan_code(self.mypkg))}')

        if force:
            try:
                fossid.delete_project(fossid_project)
                term.info(f'[{term.green("*")}]', f'Deleted FossID project {term.bright_white(fossid.project_code(self.mypkg))}')
            except RuntimeError as ex:
                term.warning(repr(self.mypkg), str(ex))


    def _do_check(
        self,
        fossid: FossID,
        pkg: Package,
        licensedb: LicenseDB = Provide[Application.service.licensedb],
    ) -> str:
        if pkg.purl.type == 'rbbuild':
            fossid_project = fossid.get_project(pkg)
            if fossid_project:
                fossid_scan = fossid.get_scan(pkg, fossid_project)
                if fossid_scan:
                    return f'(FossID scan found {term.bright_white(fossid_scan.scan_code)})'
            raise LookupError(f'FossID entry for {str(pkg)} is missing')

        else:
            license_msg = None
            if pkg.licenses:
                licenses = []
                for license in pkg.licenses:
                    spdx_identifier = license.id or license.expression
                    if licensedb.is_registered(spdx_identifier):
                        raise LookupError(f'License expression {spdx_identifier} is not registered!')
                license_msg = f'[{term.bright_white(", ".join(licenses))}]'
                if licensedb.is_permissive(spdx_identifier) is True:
                    return license_msg + ' (permissive license)'

            # TODO: component registry lookup for non-rbbuild package types
            # is not yet implemented.
            if license_msg:
                return f'{license_msg} (found registered component)'
            return '(found registered component)'


    @inject
    def dependencies_check(
        self,
        oss_man: OSSManager = Provide[Application.service.oss.ossman],
        paths: Paths = Provide[Application.core.paths],
        resolver: Resolver = Provide[Application.resolver.resolver],
        manifest_parser: ManifestJSONParser = Provide[Application.package.parser],
        profile_config: dict = Provide[Application.config.profile],
    ):
        _, fossid, fossid_config = self._get_oss(oss_man)

        exclude_dependencies = {}
        for edep in fossid_config.get('exclude_dependencies', []):
            if '-' in edep:
                k, v = edep.split('-', maxsplit=1)
                exclude_dependencies[k] = v
            else:
                exclude_dependencies[edep] = None

        for pkg, _ in resolver.walk_deps_with_count(self.mypkg, skip_build_only=True):
            msg = f'{str(pkg.purl)}'
            term.info(f'[ ] {msg}', end='')

            if pkg.name in exclude_dependencies:
                # If a version was specified, we check for it as well
                if exclude_dependencies[pkg.name] is None or exclude_dependencies[pkg.name] == pkg.version:
                    term.info(f'\r[{term.yellow("skipped")}] {msg}')
                    continue

            try:
                reason = self._do_check(fossid=fossid, pkg=pkg)
                term.info(f'\r[{term.green("*")}] {msg} {reason}')
            except LookupError as ex:
                term.info(f'\r[{term.red("x")}] {term.red(msg)}: {str(ex)}')
            except Exception:
                raise


    @inject
    def cancel_run(self, oss_man: OSSManager = Provide[Application.service.oss.ossman]):
        _, fossid, _ = self._get_oss(oss_man)
        fossid_project = fossid.get_project(self.mypkg)
        if not fossid_project:
            raise RuntimeError(f'Could not find FossID project {term.bright_white(fossid.project_code(self.mypkg))}')

        fossid_scan = fossid.get_scan(self.mypkg, fossid_project)
        if not fossid_scan:
            raise RuntimeError(f'Could not find FossID scan {term.bright_white(fossid.scan_code(self.mypkg))}')

        fossid.cancel_run(fossid_scan)
        term.info(f'[{term.green("*")}] Sent request to cancel FossID Scan {term.bright_white(fossid.scan_code(self.mypkg))}')


    def _setup_ignore_rules(
        self,
        fossid: FossID,
        fossid_scan: FossIDScanEntry,
        fossid_config: dict,
        paths: Paths,
    ):
        pyproject_toml_path = paths.source / 'pyproject.toml'
        repo_cfg = {}
        if pyproject_toml_path.exists():
            with open(pyproject_toml_path, 'rb') as fd:
                pyproject_data = tomllib.load(fd)
            repo_cfg = pyproject_data.get('tool', {}).get('rbfoss', {})

        ignore_files       = set(repo_cfg.get('ignore_files', []))
        ignore_files      |= set(fossid_config.get('ignore_files', []))
        ignore_folders     = set(repo_cfg.get('ignore_folders', []))
        ignore_folders    |= set(fossid_config.get('ignore_folders', []))
        ignore_extensions  = set(repo_cfg.get('ignore_extensions', []))
        ignore_extensions |= set(fossid_config.get('ignore_extensions', []))

        for item in ignore_files:
            term.info(f'[{term.green("*")}]', f'Added file ignore rule {term.magenta(item)}')
            fossid.ignore_rules_add(fossid_scan, IgnoreRuleType.FILE, item)

        for item in ignore_folders:
            term.info(f'[{term.green("*")}]', f'Added folder ignore rule {term.magenta(item)}')
            fossid.ignore_rules_add(fossid_scan, IgnoreRuleType.FOLDER, item)

        for item in ignore_extensions:
            term.info(f'[{term.green("*")}]', f'Added extension ignore rule {term.magenta(item)}')
            fossid.ignore_rules_add(fossid_scan, IgnoreRuleType.EXTENSION, item)


    @inject
    def setup(
        self,
        oss_man: OSSManager = Provide[Application.service.oss.ossman],
        paths: Paths = Provide[Application.core.paths],
    ) -> FossIDScanEntry:
        _, fossid, fossid_cfg = self._get_oss(oss_man)
        fossid_project = fossid.get_project(self.mypkg)
        if not fossid_project:
            project_description = self.mypkg.name
            fossid_project = fossid.create_project(self.mypkg, project_description)
            term.info(f'[{term.green("*")}] FossID project created\n{str(fossid_project)}')
        else:
            term.info(f'[{term.yellow("-")}] FossID project information retrieved\n{str(fossid_project)}')

        term.info(f'[{term.green("*")}] assigning project members: ', ', '.join(fossid_cfg.get('users', [])))
        for user in fossid_cfg.get('users', []):
            fossid.assign_member(fossid_project, user)

        fossid_scan = fossid.get_scan(self.mypkg, fossid_project)
        if not fossid_scan:
            fossid_scan = fossid.create_scan(self.mypkg, fossid_project)
            term.info(f'[{term.green("*")}] FossID scan created\n{str(fossid_scan)}')
            self._setup_ignore_rules(fossid, fossid_scan, fossid_cfg, paths)
        else:
            term.info(f'[{term.yellow("-")}] FossID scan information retrieved\n{str(fossid_scan)}')

        fossid_scan.project_entry = fossid_project
        term.info(f'FossID Scan URL: {term.bright_white(fossid.scan_url(fossid_scan.scan_id))}')

        return fossid_scan


    @inject
    def upload(self, fossid_scan: FossIDScanEntry, oss_man: OSSManager = Provide[Application.service.oss.ossman]):
        _, fossid, _ = self._get_oss(oss_man)
        if not fossid_scan:
            fossid_project = fossid.get_project(self.mypkg)
            if not fossid_project:
                raise RuntimeError('Upload failed. FossID project entry does not exist! Try rbfoss -s')
            fossid_scan = fossid.get_scan(self.mypkg, fossid_project)
            if not fossid_scan:
                raise RuntimeError('Upload failed. FossID scan entry does not exist! Try rbfoss -s')

        spinner = itertools.cycle(['-', '/', '|', '\\'])

        term.info(f'[{term.green("*")}] Checking git upload status\t\t', end='')
        for status in fossid.download_content_from_git(fossid_scan):
            term.redraw_last_line(term.magenta(next(spinner)), end='')

        term.redraw_last_line(term.green('success'))


    @inject
    def run(self, fossid_scan: FossIDScanEntry, oss_man: OSSManager = Provide[Application.service.oss.ossman]):
        _, fossid, _ = self._get_oss(oss_man)
        if not fossid_scan:
            fossid_project = fossid.get_project(self.mypkg)
            fossid_scan = fossid.get_scan(self.mypkg, fossid_project)
            if not fossid_scan:
                raise RuntimeError('Run failed. FossID scan entry does not exist! Try rbfoss -s')

        if not fossid_scan.project_entry:
            fossid_scan.project_entry = fossid.get_project(self.mypkg)

        if not fossid_scan.project_entry:
            raise RuntimeError('Run failed. FossID project entry does not exist! Try rbfoss -s')

        spinner = itertools.cycle(['-', '/', '|', '\\'])

        term.info(f'[{term.green("*")}] Checking FossID scan run status\t', end='')
        for status in fossid.run(fossid_scan):
            term.redraw_last_line(term.magenta(next(spinner)), end='')

        term.redraw_last_line(term.green('success'))


    @inject
    def generate_report(
        self,
        fossid_scan: FossIDScanEntry,
        report_type: str,
        oss_man: OSSManager = Provide[Application.service.oss.ossman],
        paths: Paths = Provide[Application.core.paths],
    ):
        _, fossid, _ = self._get_oss(oss_man)
        if not fossid_scan:
            fossid_project = fossid.get_project(self.mypkg)
            fossid_scan = fossid.get_scan(self.mypkg, fossid_project)
            if not fossid_scan:
                raise RuntimeError('Generate report failed. FossID scan entry does not exist! Try rbfoss -s')

        report_path = paths.build / f'fossid_scan_report.{report_type}'
        term.info(f'[{term.green("*")}] Generating FossID scan report ({report_path.name})\t', end='')
        fossid.generate_report(report_path, fossid_scan, report_type=report_type)
        term.redraw_last_line(term.green('success'))


    @inject
    def main(
        self,
        args,
        oss_man: OSSManager = Provide[Application.service.oss.ossman],
    ):
        if not list(oss_man.names()):
            raise RuntimeError('No OSS configuration found in the current profile!')

        # -c / --clean
        if args.clean:
            self.clean(force=args.force)
            # End any other processing after clean
            return

        # Prepare actions
        default_actions = ['setup', 'upload', 'run']
        action = args.action if args.action else default_actions

        fossid_scan = None

        # checks
        if not self.mypkg.git_repo or not self.mypkg.git_hash:
            raise NotImplementedError('Git resource not defined - Archive uploading is not implemented yet!')

        # Process actions - in predefined order

        #
        # --dependencies
        #
        if 'dependencies' in action:
            self.dependencies_check()

        #
        # --cancel-run
        #
        if 'cancel_run' in action:
            self.cancel_run()

        #
        # --setup
        #
        if 'setup' in action:
            fossid_scan = self.setup()

        #
        # --upload
        #
        if 'upload' in action:
            self.upload(fossid_scan)

        #
        # --run
        #
        if 'run' in action:
            self.run(fossid_scan)

        #
        # --generate-report
        #
        if 'generate_report' in action:
            self.generate_report(fossid_scan, args.report_type)


def parse_command_line(cmdline=None):
    parser = argparse.ArgumentParser(description='rbfoss -- Robert Bosch rbbuild FossID wrapper')
    # Actions
    parser.add_argument( '-D', '--dependencies',    action='append_const', dest='action', const='dependencies',    help='Check dependencies' )
    parser.add_argument( '-s', '--setup',           action='append_const', dest='action', const='setup',           help='Setup FossID project and scan entity' )
    parser.add_argument( '-u', '--upload',          action='append_const', dest='action', const='upload',          help='Upload source code from git to FossID' )
    parser.add_argument( '-r', '--run',             action='append_const', dest='action', const='run',             help='Run FossID scan (use with -f to enforce full scan)' )
    parser.add_argument( '-g', '--generate-report', action='append_const', dest='action', const='generate_report', help='Generate FossID report' )
    parser.add_argument(       '--cancel-run',      action='append_const', dest='action', const='cancel_run',      help='Cancel any ongoing scan run' )
    parser.add_argument(       '--report-type',     action='store',        default='xlsx', help='Type of the FossID report (xlsx, html)' )

    # Other options
    parser.add_argument( '-c', '--clean',           action='store_const',  const=True, default=False, help='Delete FossID scan (use with -f to delete project as well)' )
    parser.add_argument( '-f', '--force',           action='store_const',  const=True, default=False, help='Force action (valid with: -c or -r)' )
    parser.add_argument( '-P', '--profile',         action='store',                                   help='Select profile' )
    parser.add_argument(       '--ignore-errors',   action='store_const',  const=True, default=False, help='Ignore dependency errors' )
    parser.add_argument(       '--log-level',       action='store',        dest='log_level',           help='Highest log level: %s. Default: INFO' % ', '.join(LogLevel.__members__.keys()))
    parser.add_argument( '-v', '--verbose',         action='store_const',  const=True, default=False, help='Set verbose mode to see more log output' )
    parser.add_argument( '-n', '--dry-run',         action='store_const',  const=True, default=False, help='Only show operations that would be executed' )
    return parser.parse_args(args=cmdline)


def run():
    args = parse_command_line()

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

        source_path = Path(config.paths.source())
        config.load_project_configuration(source_path)
        config.load_jenkinsfile(source_path)
        config.load_cli_profile(**vars(args))
        config.load_profile(
            profile_name=config.settings.profile(),
            rbbuild_config_path=rbbuild_config_path,
            user_config_path=Path(config.paths.user_config()),
        )
        config.load_cli(**vars(args))

        rbfoss = RBFossMain()

        application = Application(config=config)
        application.wire(modules=[rbfoss_mod.__name__])

        rbfoss.main(args)
    except Exception as e:
        import traceback
        term.error('failed', e)
        term.debug('Exception stack', traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    run()

