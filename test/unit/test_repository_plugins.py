# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock

from rbbuild.service.repository import plugins
from rbbuild.service.repository.plugins import ENTRY_POINT_GROUP, load_repository_plugins
from rbbuild.service.repository.repository import Repository


class _GoodRepo(Repository):
    pass


# Build an entry-point stand-in whose load() returns obj (or raises exc).
def _make_ep(name, obj=None, exc=None):
    ep = MagicMock()
    ep.name = name
    ep.value = f'pkg.mod:{name}'
    if exc:
        ep.load.side_effect = exc
    else:
        ep.load.return_value = obj
    return ep


def _patch_entry_points(monkeypatch, eps):
    calls = []

    def fake_entry_points(**kwargs):
        calls.append(kwargs)
        return eps

    monkeypatch.setattr(plugins, 'entry_points', fake_entry_points)
    return calls


def test_load_repository_plugins_uses_entry_point_group(monkeypatch):
    calls = _patch_entry_points(monkeypatch, [])
    assert load_repository_plugins() == {}
    assert calls == [{'group': ENTRY_POINT_GROUP}]


def test_load_repository_plugins_returns_classes_by_name(monkeypatch):
    _patch_entry_points(monkeypatch, [_make_ep('csi', _GoodRepo)])
    assert load_repository_plugins() == {'csi': _GoodRepo}


def test_load_repository_plugins_skips_unloadable(monkeypatch):
    _patch_entry_points(monkeypatch, [
        _make_ep('broken', exc=ImportError('boom')),
        _make_ep('csi', _GoodRepo),
    ])
    assert load_repository_plugins() == {'csi': _GoodRepo}


def test_load_repository_plugins_skips_non_repository(monkeypatch):
    _patch_entry_points(monkeypatch, [
        _make_ep('notrepo', dict),
        _make_ep('notclass', 'a string'),
    ])
    assert load_repository_plugins() == {}
