# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest
from copy import copy

from rbbuild.service.oss.fossid import FossIDProjectEntry, FossIDScanEntry, IgnoreRuleType
from rbbuild.package.package import Package

@pytest.fixture
def mypkg():
    pkg = Package( name='mypackage',
                   version='1.2.3.4' )
    pkg.git_repo='ssh://fake_server/test_repo.git'
    pkg.git_hash='master'
    yield pkg


@pytest.fixture
def my_fossid_project(fossid, mypkg):
    yield FossIDProjectEntry( project_code=fossid.project_code(mypkg),
                              description='This is a fake project for rbbuild testing purposes',  # test/data/fake_project/pyproject.toml
                              comment='FossID project created with rbbuild',
                              project_id=99 )

@pytest.fixture
def my_fossid_scan(fossid, my_fossid_project, mypkg):
    yield FossIDScanEntry( project_entry=my_fossid_project,
                           scan_code=fossid.scan_code(mypkg),
                           description='mypackage-1.2.3.4',
                           comment='FossID project created with rbbuild',
                           scan_id=1055,
                           git_repo=mypkg.git_repo,
                           git_hash=mypkg.git_hash )


def test_initial_config(fossid):
    assert fossid.name == 'project'
    assert fossid.api_endpoint_url == 'https://fossid.example.com/15/api.php'


def test_project_code(fossid, mypkg):
    assert fossid.project_code(mypkg) == 'EXAMPLE_mypackage'


def test_scan_code(fossid, mypkg):
    assert fossid.scan_code(mypkg) == 'EXAMPLE_mypackage-1.2.3.4'


def test_url(fossid):
    assert fossid.scan_url(456) == 'https://fossid.example.com/15/index.html?action=scanview&sid=456'


def test_get_project(fossid, mypkg, my_fossid_project, requests_mock):
    resp = {
        'status': '1',
        'data': {
            'description': my_fossid_project.description,
            'comment': my_fossid_project.comment,
            'id': my_fossid_project.project_id,
        }
    }
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)

    assert fossid.get_project(mypkg) == my_fossid_project


def test_create_project(fossid, mypkg, my_fossid_project, requests_mock):
    resp = {
        'status': '1',
        'data': {
            'description': my_fossid_project.description,
            'comment': my_fossid_project.comment,
            'project_id': str(my_fossid_project.project_id),  # API returns ID as string
        }
    }
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)
    assert fossid.create_project(mypkg, my_fossid_project.description) == my_fossid_project


def test_get_scan(fossid, mypkg, my_fossid_scan, requests_mock):
    resp = {
        'status': '1',
        'data': {
            'description': my_fossid_scan.description,
            'comment': my_fossid_scan.comment,
            'project_id': str(my_fossid_scan.project_entry.project_id),  # API returns ID as string
            'id': str(my_fossid_scan.scan_id),                            # API returns ID as string
            'git_repo_url': 'ssh://fake_server/test_repo.git',
            'git_branch': 'master',
        }
    }
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)
    assert fossid.get_scan(mypkg, my_fossid_scan.project_entry) == my_fossid_scan


def test_create_scan(fossid, mypkg, my_fossid_scan, requests_mock):
    resp = {
        'status': '1',
        'data': {
            'scan_code': my_fossid_scan.scan_id,
            'description': my_fossid_scan.description,
            'comment': my_fossid_scan.comment,
            'git_repo_url': 'ssh://fake_server/test_repo.git',
            'git_branch': 'master',
            'scan_id': str(my_fossid_scan.scan_id),  # API returns ID as string
        }
    }
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)
    mock_scan_entry = fossid.create_scan(mypkg, my_fossid_scan.project_entry)
    assert mock_scan_entry == my_fossid_scan


def test_download_content_from_git(fossid, mypkg, my_fossid_scan, requests_mock):
    resp = {
        'status': '1',
        'data': 'NOT STARTED',
    }
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)

    # 1. intial state
    res = next(fossid.download_content_from_git(my_fossid_scan))
    assert res == 'NOT STARTED'

    # 2. retrieving data
    resp['data'] = 'some data'
    res = next(fossid.download_content_from_git(my_fossid_scan))
    assert res == 'some data'
    resp['data'] = 'more data'
    res = next(fossid.download_content_from_git(my_fossid_scan))
    assert res == 'more data'

    # 3. download finished
    resp['data'] = 'FINISHED'
    with pytest.raises(StopIteration):
        res = next(fossid.download_content_from_git(my_fossid_scan))


@pytest.mark.skip(reason='Limitations of the FossID API disallow mocking nested web service calls')
def test_run(fossid, my_fossid_scan, requests_mock):
    resp = {
        'status': '1',
        'data': {
            'status': 'NEW',
        }
    }
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)

    # 1. initial state
    res = next(fossid.run(my_fossid_scan))
    assert res == 'NEW'

    # 2. doing something ...
    resp['data']['status'] = 'RUN'
    res = next(fossid.run(my_fossid_scan))
    assert res == 'NEW'

    # 3. scan complete
    resp['data']['status'] = 'FINISHED'

    with pytest.raises(StopIteration):
        res = next(fossid.run(my_fossid_scan))


def test_delete_scan(fossid, my_fossid_scan, requests_mock):
    resp = {
        'status': '1',
    }
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)
    assert fossid.delete_scan(my_fossid_scan)


def test_get_all_scans(fossid, my_fossid_project, my_fossid_scan, requests_mock):
    scan_1 = copy(my_fossid_scan)
    scan_1.description += '-1'
    scan_1.scan_code += '-1'
    scan_1.project_entry = None
    scan_2 = copy(my_fossid_scan)
    scan_2.description += '-2'
    scan_2.scan_id += 1
    scan_2.project_entry = None

    resp = {
        'status': '1',
        'data': [
            {
                'description': scan_1.description,
                'comment': scan_1.comment,
                'id': scan_1.scan_id,
                'code': scan_1.scan_code,
                'git_repo_url': scan_1.git_repo,
                'git_branch': scan_1.git_hash,
            },
            {
                'description': scan_2.description,
                'comment': scan_2.comment,
                'id': scan_2.scan_id,
                'code': scan_2.scan_code,
                'git_repo_url': scan_2.git_repo,
                'git_branch': scan_2.git_hash,
            },
        ]
    }
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)

    res = fossid.get_all_scans(my_fossid_project)
    assert res == [scan_1, scan_2]


def test_delete_project_empty(fossid, my_fossid_project, requests_mock):
    resp = {
        'status': '1',
        'data': [],
    }
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)
    assert fossid.delete_project(my_fossid_project)


def test_delete_project_with_scans(fossid, my_fossid_project, my_fossid_scan, requests_mock):
    scan_1 = copy(my_fossid_scan)
    scan_1.description += '-1'
    scan_1.scan_code += '-1'
    scan_1.project_entry = None
    scan_2 = copy(my_fossid_scan)
    scan_2.description += '-2'
    scan_2.scan_id += 1
    scan_2.project_entry = None

    resp = {
        'status': '1',
        'data': [
            {
                'description': scan_1.description,
                'comment': scan_1.comment,
                'id': scan_1.scan_id,
                'code': scan_1.scan_code,
                'git_repo_url': scan_1.git_repo,
                'git_branch': scan_1.git_hash,
            },
            {
                'description': scan_2.description,
                'comment': scan_2.comment,
                'id': scan_2.scan_id,
                'code': scan_2.scan_code,
                'git_repo_url': scan_2.git_repo,
                'git_branch': scan_2.git_hash,
            },
        ]
    }

    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)
    with pytest.raises(RuntimeError):
        fossid.delete_project(my_fossid_project)


def test_generate_report(fossid, fake_project, my_fossid_scan, requests_mock):
    headers = {'Content-type': 'application/vnd.ms-excel'}
    requests_mock.post(url=fossid.api_endpoint_url, headers=headers, text='fake XLSX report')

    report_path = fake_project / 'report.xlsx'
    fossid.generate_report(report_path, my_fossid_scan, report_type='xlsx')

    assert report_path.exists()
    with open(report_path, 'r') as fd:
        assert fd.read().strip() == 'fake XLSX report'


def test_assign_member(fossid, my_fossid_project, requests_mock):
    resp = {
        'status': '1',
    }
    user = 'user'
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)
    assert fossid.assign_member(my_fossid_project, user)


def test_cancel_run(fossid, my_fossid_scan, requests_mock):
    resp = {
        'status': '1',
    }
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)
    assert fossid.cancel_run(my_fossid_scan)


def test_ignore_rules_add(fossid, my_fossid_scan, requests_mock):
    resp = {
        'status': '1',
    }
    requests_mock.post(url=fossid.api_endpoint_url, headers=fossid.headers, json=resp)
    assert fossid.ignore_rules_add(my_fossid_scan, IgnoreRuleType.FILE, '.git')
    assert fossid.ignore_rules_add(my_fossid_scan, IgnoreRuleType.DIRECTORY, 'dir')
    assert fossid.ignore_rules_add(my_fossid_scan, IgnoreRuleType.FOLDER, 'dir')
    assert fossid.ignore_rules_add(my_fossid_scan, IgnoreRuleType.EXTENSION, 'exe')

