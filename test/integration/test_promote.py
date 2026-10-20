#!/usr/bin/env python

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest


# Dry run with a valid package and channel mapping completes without error.
def test_promote_dry_run(promote):
    promote.run(['-n', '-m', 'sample-development:rbbuild-test', 'sample_tools-2.0.0.4'])
    output = promote.read_console()
    assert 'Promoting' in output
    assert 'dry run' in output


# --no-traverse flag is accepted and passed through to the resolver.
def test_promote_dry_run_no_traverse(promote):
    promote.run(['-n', '--no-traverse', '-m', 'sample-development:rbbuild-test', 'sample_tools-2.0.0.4'])
    output = promote.read_console()
    assert 'Promoting' in output


# An unknown source channel name raises RuntimeError.
def test_promote_invalid_source_channel(promote):
    with pytest.raises((RuntimeError, LookupError)):
        promote.run(['-n', '-m', 'nonexistent-channel:rbbuild-test', 'sample_tools-2.0.0.4'])


# An unknown target channel name raises RuntimeError.
def test_promote_invalid_target_channel(promote):
    with pytest.raises((RuntimeError, LookupError)):
        promote.run(['-n', '-m', 'sample-development:nonexistent-channel', 'sample_tools-2.0.0.4'])


# Mapping a channel to itself raises RuntimeError.
def test_promote_same_source_and_target_channel(promote):
    with pytest.raises(RuntimeError, match='same'):
        promote.run(['-n', '-m', 'sample-development:sample-development', 'sample_tools-2.0.0.4'])


# A package that does not exist in the source channel raises LookupError.
def test_promote_package_not_found(promote):
    with pytest.raises(LookupError):
        promote.run(['-m', 'sample-development:rbbuild-test', 'nonexistent_pkg-9.9.9999.0'])


# Omitting -m raises RuntimeError about missing channel mapping.
def test_promote_no_channel_map(promote):
    with pytest.raises((RuntimeError, SystemExit)):
        promote.run(['sample_tools-2.0.0.4'])
