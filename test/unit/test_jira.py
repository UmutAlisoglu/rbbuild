# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

from urllib.parse import quote_plus

from rbbuild.service.issuetracker.issuetracker_manager import Issue, IssueTrackerManager, OrderHint
from rbbuild.service.remote_service import AuthMethod
from rbbuild.service.issuetracker.jira import Jira


def test_initial_config(jira):
    assert jira.key == 'PROJECT'
    assert jira.url == 'https://jira.example.com/tracker/'
    assert jira.api_endpoint_url == 'https://jira.example.com/tracker/rest/api/2/'


def test_get_issue(jira, requests_mock):
    resp = {
        'fields': {
            'issuelinks': [
                {
                    'type': 'inward',
                    'inwardIssue': {
                        'key': 'PROJECT-1',
                        'summary': 'ticket summary'
                    }
                },
                {
                    'type': 'inward',
                    'inwardIssue': {
                        'key': 'PROJECT-1',
                        'summary': 'ticket summary'
                    }
                }
            ]
        }
    }
    url = f'{jira.api_endpoint_url}issue/PROJECT-1?fields=issuelinks'
    requests_mock.get(url=url, headers=jira.headers, json=resp)
    assert jira.get_issue('PROJECT-1') == resp


def test_search(jira, requests_mock):
    resp = {
        'issues':
        [
            {
                'key': 'PROJECT-1',
                'fields': {
                    'summary': 'ticket summary',
                    'status': {
                        'name': 'Closed'
                    }
                },
            },
            {
                'key': 'PROJECT-2',
                'fields': {
                    'summary': 'ticket summary',
                    'status': {
                        'name': 'Open'
                    }
                },
            },
        ]
    }
    jql = 'assignee=me'
    expected_jql = f'project=PROJECT AND {jql} '
    url = f'{jira.api_endpoint_url}search?jql={quote_plus(expected_jql)}'
    requests_mock.get(url=url, headers=jira.headers, json=resp)
    issues = list(jira.search(jql))

    assert len(issues) == 2
    assert issues[0].key == 'PROJECT-1'
    assert issues[1].key == 'PROJECT-2'


def test_release_versions(jira, requests_mock):
    resp = [
        {
            'name': 'Release_1',
            'description': 'Release description 1',
            'releaseDate': '2025-01-01',
            'archived': True,
        },
        {
            'name': 'Release_2',
            'description': 'Release description 2',
            'releaseDate': '2025-01-20',
            'archived': False,
        },
    ]
    url = f'{jira.api_endpoint_url}project/PROJECT/versions'
    requests_mock.get(url=url, headers=jira.headers, json=resp)
    versions = list(jira.release_versions())
    assert len(versions) == 2
    assert versions[0].name == 'Release_1'
    assert versions[1].name == 'Release_2'
    assert versions[0].release_date == '2025-01-01'
    assert versions[1].release_date == '2025-01-20'


# --- make_order_hint ---

def test_make_order_hint_key_asc(jira):
    assert jira.make_order_hint(OrderHint.KEY_ASC) == 'ORDER BY key ASC'


def test_make_order_hint_key_desc(jira):
    assert jira.make_order_hint(OrderHint.KEY_DESC) == 'ORDER BY key DESC'


# None (or unrecognised) hint falls back to empty string
def test_make_order_hint_none(jira):
    assert jira.make_order_hint(None) == ''


# --- get_issue ---

# Key without '-' raises SyntaxError
def test_get_issue_invalid_key(jira):
    with pytest.raises(SyntaxError):
        jira.get_issue('PROJECT1')


# --- Issue.status_colored ---

def test_issue_status_closed():
    issue = Issue(key='PROJECT-1', summary='test', status='Closed')
    colored = issue.status_colored
    assert 'Closed' in colored


def test_issue_status_open():
    issue = Issue(key='PROJECT-2', summary='test', status='Open')
    colored = issue.status_colored
    assert 'Open' in colored


def test_issue_status_other():
    issue = Issue(key='PROJECT-3', summary='test', status='In Progress')
    colored = issue.status_colored
    assert 'In Progress' in colored


# --- IssueTrackerManager.service() ---

def _make_manager(profile_config, user_config=None):
    return IssueTrackerManager(
        profile_config=profile_config,
        user_config=user_config or {},
        jira=lambda **kw: Jira(auth_method=AuthMethod.NONE, **kw),
    )


# Key not present in profile issuetracker config → LookupError
def test_manager_service_key_not_configured():
    manager = _make_manager({'issuetracker': {}})
    with pytest.raises(LookupError):
        manager.service('NONEXISTENT')


# remote_service not in services config → LookupError
def test_manager_service_remote_service_not_configured():
    profile_config = {
        'issuetracker': {
            'PROJECT': {'remote_service': 'jira_service'},
        },
        'services': {},   # no matching entry
    }
    manager = _make_manager(profile_config)
    with pytest.raises(LookupError):
        manager.service('PROJECT')

