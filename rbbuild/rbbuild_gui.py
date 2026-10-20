#!/usr/bin/env python

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import os
import sys
import argparse

from pathlib import Path

from rbbuild import data_path
from rbbuild.container.application import Application
from rbbuild.container.configuration import RBBuildConfiguration
from rbbuild.librbb.term import term, LogLevel

#
# rbbuild-gui is only available if the "ui" optional dependencies are available.
#

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:
    pip_cmd = 'uv pip install rbbuild[ui]'
    term.error('Missing Python dependencies', f'{sys.argv[0]} cannot be called because dependencies are missing.\n\nTo fix this, call:\n\t{term.bright_white(pip_cmd)}')
    sys.exit(1)


from rbbuild.ui.app import RBBuildGuiApp
from rbbuild.ui.pkq.view import PkqView


# Before doing anything with PySide, we need to check on Linux
# whether libxcb-cursor.so is installed.
# Otherwise, PySide crashes with a core dump.
if sys.platform == 'linux':
    import subprocess
    import platform
    try:
        cmd = 'ldconfig -p|grep libxcb-cursor.so'
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        distro_command = ''
        if platform.freedesktop_os_release().get('NAME') in ['Ubuntu']:
            distro_command = 'sudo apt install libxcb-cursor0'
        term.error('Missing system dependency', f'{term.bright_white(cmd)} failed.\n\nTo fix this, install libxcb-cursor:\n\t{term.bright_white(distro_command)}')
        sys.exit(1)


# Entry point for the "rbbuild-gui" console script.
#
# Currently launches the package-query (pkq) view. Future tool GUIs
# (rbbuild, rbfoss, ...) are expected to reuse the same RBBuildGuiApp shell.
# See documentation/developer-manual/gui_architecture.md.
def parse_command_line(cmdline=None):
    parser = argparse.ArgumentParser(description='rbbuild-gui -- Graphical interface for rbbuild tools')
    parser.add_argument( '-t', '--toolchain',         action='store',        dest='tcid',               help='Select toolchain by name or ID' )
    parser.add_argument( '-v', '--verbose',           action='store_const',  const=True, default=False, help='Verbose output' )
    parser.add_argument( '-P', '--profile',           action='store',                                   help='Select profile' )
    parser.add_argument( '-C', '--channel',           action='store',        dest='channel',            help='Select a channel' )
    parser.add_argument(       '--platform',          action='store',        dest='platform',           help='Specify target platform' )
    parser.add_argument(       '--log-level',         action='store',        dest='log_level',          help='Highest log level: %s. Default: INFO' % ', '.join(LogLevel.__members__.keys()))
    parser.add_argument(       '--version',           action='store_const',  const=True, default=False, help='Display version and exit' )
    parser.add_argument('package', metavar='package', nargs='?', default=None, help='Initial package query. Syntax: [<channel>:]<pkgname>[-<version>]')
    return parser.parse_args(args=cmdline)


# Builds a fresh DI container for the given (or default) profile - used for
# both initial bootstrap and runtime profile switching (a full rebuild
# rather than an in-place config override, see "Switching profile" in
# documentation/developer-manual/gui_architecture.md). On a profile switch,
# channel/tcid CLI overrides from the original launch are reset so a
# channel/toolchain picked for one profile doesn't silently carry over into
# another profile where it may not resolve.
def build_application(rbbuild_root_path: Path, rbbuild_config_path: Path, args, profile_name: str = None) -> Application:
    cli_args = args
    if profile_name:
        cli_args = argparse.Namespace(**{**vars(args), 'profile': profile_name, 'channel': None, 'tcid': None})

    config = RBBuildConfiguration()
    config.load_configuration(rbbuild_root_path, rbbuild_config_path)

    config.load_cli_profile(**vars(cli_args))
    config.load_profile(
        profile_name=config.settings.profile(),
        rbbuild_config_path=rbbuild_config_path,
        user_config_path=Path(config.paths.user_config()),
    )
    config.load_cli(**vars(cli_args))

    application = Application(config=config)
    application.wire(modules=[__name__])
    return application


def run():
    args = parse_command_line()

    term.log_level = args.log_level

    if args.version:
        from rbbuild.version import __version__
        term.info(__version__)
        return

    rbbuild_root_path = Path(
        os.environ.get('RBB_ROOT') or
        Path(__file__).resolve().parent
    ).absolute()
    rbbuild_config_path = Path(
        os.environ.get('RBB_CONFIG_PATH') or
        data_path() / 'config'
    ).absolute()

    try:
        qt_app = QApplication(sys.argv)
        application = build_application(rbbuild_root_path, rbbuild_config_path, args)
        app = RBBuildGuiApp(application, title='rbbuild Command Center', qt_app=qt_app)

        # Rebuilds the DI container for a different profile and remounts a
        # fresh PkqView. A failed switch leaves the current view untouched —
        # the new Application is only swapped in on success.
        def switch_profile(profile_name: str):
            nonlocal application
            try:
                new_application = build_application(rbbuild_root_path, rbbuild_config_path, args, profile_name=profile_name)
            except Exception as e:
                term.error('failed to switch profile', e)
                return

            try:
                application.unwire()
            except Exception:
                pass

            application = new_application
            mount_pkq(application, restore_history=False)

        # restore_history is False for profile switches - the persisted
        # recent-queries history isn't profile-specific, so re-showing the
        # previous profile's package/channel/toolchain here would be
        # confusing rather than useful.
        def mount_pkq(current_application: Application, restore_history: bool = True):
            app.set_content(PkqView(
                app.notebook, current_application, args,
                on_profile_change=switch_profile, restore_history=restore_history,
                active_deps=app.active_deps, on_active_deps_change=app.refresh_active_deps,
                deps_drop_target=app.frame_sidebar,
            ))

        mount_pkq(application)
        app.mainloop()
    except Exception as e:
        import traceback
        term.error('failed', e)
        term.debug('Exception stack', traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    run()
