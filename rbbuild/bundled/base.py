# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

# This is a base class to handle bundled packages,
# in particular common code to run executables such as
# cmake or sonar-scanner.

import os
import shutil

from rbbuild.core.runtime_settings import RuntimeSettings


class BundledBase:
    # @param search_path: pathlib.Path.glob() will be called to resolve this path.
    def __init__(self, settings: RuntimeSettings, search_path=None):
        self._settings = settings
        self.base_path = settings.rbbuild_root_path
        # Allow special case to allow bootstrapping rbbuild, where
        # we add <rbb_root>/staging/<tcid>/cmake.../bin to find cmake
        if search_path:
            exe_globbed = [str(p) for p in self.base_path.glob(str(search_path))]
            if not exe_globbed:
                raise FileNotFoundError(f'Could not resolve glob search path {search_path}')
            self.search_paths = exe_globbed

        else:
            self.search_paths = []

        # cache
        self._executables = {}


    @property
    def settings(self):
        return self._settings


    # Unfortunately, PATH environment variable is entirely ignored on
    # Windows CreateProcess function. To keep compatibility, this behavior
    # is not changed.
    # To workaround this issue, we use shutil.which() instead.
    # See: https://bugs.python.org/issue8557.
    def executable(self, exe):
        if exe not in self._executables:
            path_orig = os.environ.get('PATH', '')

            # Add extra search path to find the executable
            if self.search_paths:
                os.environ['PATH'] = os.pathsep.join(self.search_paths + [path_orig])

            try:
                exe_abspath = shutil.which(exe)
            except:
                raise
            finally:
                # Restore PATH to its original value
                if self.search_paths:
                    os.environ['PATH'] = path_orig

            if not(exe_abspath):
                raise FileNotFoundError('%s not found' % (exe))

            # We don't care about other matches and pick the first one
            self._executables[exe] = exe_abspath

        return str(self._executables[exe])

