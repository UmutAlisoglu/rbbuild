# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import os

from unittest.mock import MagicMock

from rbbuild.buildsystem.pytest import PyTest
from rbbuild.core.runtime_settings import OperationMode
from rbbuild.core.toolchain import Toolchain

# Unit tests for rbbuild.buildsystem.pytest.PyTest.


def _op_mode(**kwargs) -> OperationMode:
    defaults = dict(
        debug=False, verbose=False, force=False, ignore_errors=False,
        dry_run=False, offline=False, manifest_only=False, transitive=True,
    )
    defaults.update(kwargs)
    return OperationMode(**defaults)


# PyTest.__init__ must not mutate the real process os.environ - it should
# only set RBB_TOOLCHAIN_ID on its own copy, used for the pytest subprocess.
def test_init_does_not_mutate_real_os_environ(monkeypatch):
    monkeypatch.delenv('RBB_TOOLCHAIN_ID', raising=False)

    pytest_tool = PyTest(paths=MagicMock(), toolchain=Toolchain(tcid=None, toolchains_config={}), op_mode=_op_mode())

    assert pytest_tool.environ['RBB_TOOLCHAIN_ID'] == 'none-any'
    assert 'RBB_TOOLCHAIN_ID' not in os.environ

