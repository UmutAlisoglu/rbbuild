# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

from rbbuild.service.issuetracker.jira import Jira
from rbbuild.service.remote_service import AuthMethod


def _make_jira(auth_method, user=None, credentials='secret'):
    return Jira(
        key='TEST',
        url='https://example.com/',
        auth_method=auth_method,
        user=user,
        credentials=credentials,
    )


# BEARER_TOKEN with a username → self.auth = (user, credentials)
def test_bearer_token_with_user():
    jira = _make_jira(AuthMethod.BEARER_TOKEN, user='testuser')
    assert jira.auth == ('testuser', 'secret')
    assert 'Authorization' not in jira.headers


# BEARER_TOKEN without username → Authorization: Bearer header, no auth tuple
def test_bearer_token_without_user():
    jira = _make_jira(AuthMethod.BEARER_TOKEN, user=None)
    assert jira.auth is None
    assert jira.headers.get('Authorization') == 'Bearer secret'


# BASIC auth → self.auth = (user, credentials)
def test_basic_auth():
    jira = _make_jira(AuthMethod.BASIC, user='basicuser')
    assert jira.auth == ('basicuser', 'secret')
    assert 'Authorization' not in jira.headers


# NONE auth → no credentials, no auth header
def test_no_auth():
    jira = _make_jira(AuthMethod.NONE)
    assert jira.auth is None
    assert jira.headers == {}


# Invalid auth method → TypeError
def test_invalid_auth_method():
    with pytest.raises(TypeError):
        _make_jira(auth_method='not_an_auth_method')


# AuthMethod.from_config: 'auth-method' of a [profile.services.<name>] table
def test_from_config_undefined_is_none():
    assert AuthMethod.from_config({'type': 'jira'}, 'svc') == AuthMethod.NONE


@pytest.mark.parametrize('value, expected', [
    ('none',         AuthMethod.NONE),
    ('basic',        AuthMethod.BASIC),
    ('bearer-token', AuthMethod.BEARER_TOKEN),
    ('bearer_token', AuthMethod.BEARER_TOKEN),
    ('BEARER-TOKEN', AuthMethod.BEARER_TOKEN),
])
def test_from_config_values(value, expected):
    assert AuthMethod.from_config({'auth-method': value}, 'svc') == expected


def test_from_config_invalid_raises():
    with pytest.raises(SyntaxError, match=r'svc.*invalid auth-method "oauth".*bearer-token'):
        AuthMethod.from_config({'auth-method': 'oauth'}, 'svc')
