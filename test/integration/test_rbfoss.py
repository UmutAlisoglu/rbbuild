#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import json
import pytest
import sys

from pathlib import Path

# Platform-specific toolchain ID (mirrors what load_cli selects from the profile)
_TOOLCHAIN_ID = 'win32-mingw' if sys.platform == 'win32' else 'linux-native'

_FOSSID_API_URL  = 'https://fossid.example.com/15/api.php'
_PROJECT_ORG     = 'EXAMPLE'
_PKG_NAME        = 'fake_project'
_PKG_VERSION     = '0.0.1.0'
_PROJECT_CODE    = f'{_PROJECT_ORG}_{_PKG_NAME}'
_SCAN_CODE       = f'{_PROJECT_CODE}-{_PKG_VERSION}'
_PROJECT_ID      = 99
_SCAN_ID         = 1055

_MANIFEST = {
    'json_version': 4,
    'package': {
        'version_package': _PKG_NAME,
        'version_string':  _PKG_VERSION,
        'git': {
            'repo':   'ssh://fake_server/fake_project.git',
            'hash':   'abc1234',
            'branch': 'master',
        },
        'toolchain': _TOOLCHAIN_ID,
        'channel':   'example-development',
        'components': [],
    },
    'dependencies': {},
}

_RESP_OK       = {'status': '1'}
_RESP_NOT_FOUND = {'status': '0'}

_RESP_PROJECT_FOUND = {
    'status': '1',
    'data': {
        'description': _PKG_NAME,
        'comment':     'FossID project created with rbbuild',
        'id':          _PROJECT_ID,
    },
}

_RESP_PROJECT_CREATED = {
    'status': '1',
    'data': {'project_id': _PROJECT_ID},
}

_RESP_SCAN_FOUND = {
    'status': '1',
    'data': {
        'description': f'{_PKG_NAME}-{_PKG_VERSION}',
        'comment':     'FossID project created with rbbuild',
        'project_id':  _PROJECT_ID,
        'id':          _SCAN_ID,
        'git_repo_url': 'ssh://fake_server/fake_project.git',
        'git_branch':   'abc1234',
    },
}

_RESP_SCAN_CREATED = {
    'status': '1',
    'data': {'scan_id': _SCAN_ID},
}


def _write_manifest(workdir: Path):
    build_dir = workdir / f'obj/{_TOOLCHAIN_ID}'
    build_dir.mkdir(parents=True)
    (build_dir / 'manifest.json').write_text(json.dumps(_MANIFEST))


# No [profile.oss.*] in the default (standalone) profile → RuntimeError before any HTTP call
def test_rbfoss_no_oss_config(rbfoss_empty):
    with pytest.raises(RuntimeError, match='No OSS configuration found'):
        rbfoss_empty.run([])


# --setup: project and scan are both absent → create both, then add ignore rules
def test_rbfoss_setup_creates_project_and_scan(rbfoss, requests_mock):
    _write_manifest(rbfoss.workdir)

    # The profile has ignore_files=['.gitignore','Jenkinsfile'] and ignore_folders=['.git']
    # Sets are used internally so the order of the 3 ignore_rules_add calls is not fixed;
    # all return status '1' so any order is fine.
    requests_mock.post(
        url=_FOSSID_API_URL,
        response_list=[
            {'json': _RESP_NOT_FOUND},       # get_project → not found
            {'json': _RESP_PROJECT_CREATED}, # create_project
            {'json': _RESP_OK},              # assign_member (testuser)
            {'json': _RESP_NOT_FOUND},       # get_scan → not found
            {'json': _RESP_SCAN_CREATED},    # create_scan
            {'json': _RESP_OK},              # ignore_rules_add (file 1)
            {'json': _RESP_OK},              # ignore_rules_add (file 2)
            {'json': _RESP_OK},              # ignore_rules_add (folder)
        ],
    )

    rbfoss.run(['-s'])

    output = rbfoss.read_console()
    assert 'FossID project created' in output
    assert 'FossID scan created' in output


# --setup: project and scan already exist → retrieve only, no create/ignore calls
def test_rbfoss_setup_finds_existing(rbfoss, requests_mock):
    _write_manifest(rbfoss.workdir)

    requests_mock.post(
        url=_FOSSID_API_URL,
        response_list=[
            {'json': _RESP_PROJECT_FOUND}, # get_project → found
            {'json': _RESP_OK},            # assign_member (testuser)
            {'json': _RESP_SCAN_FOUND},    # get_scan → found
        ],
    )

    rbfoss.run(['-s'])

    output = rbfoss.read_console()
    assert 'FossID project information retrieved' in output
    assert 'FossID scan information retrieved' in output


# --clean: project not found → warning logged, no error raised
def test_rbfoss_clean_project_not_found(rbfoss, requests_mock):
    _write_manifest(rbfoss.workdir)

    requests_mock.post(
        url=_FOSSID_API_URL,
        response_list=[
            {'json': _RESP_NOT_FOUND}, # get_project → not found
        ],
    )

    rbfoss.run(['-c'])

    output = rbfoss.read_console()
    assert 'not found' in output.lower()


# --clean: project and scan found → cancel run, delete scan; console confirms deletion
def test_rbfoss_clean(rbfoss, requests_mock):
    _write_manifest(rbfoss.workdir)

    requests_mock.post(
        url=_FOSSID_API_URL,
        response_list=[
            {'json': _RESP_PROJECT_FOUND}, # get_project → found
            {'json': _RESP_SCAN_FOUND},    # get_scan → found
            {'json': _RESP_OK},            # cancel_run
            {'json': _RESP_OK},            # delete_scan
        ],
    )

    rbfoss.run(['-c'])

    output = rbfoss.read_console()
    assert 'Deleted FossID scan' in output


# --clean --force: after scan deletion, also delete the project
def test_rbfoss_clean_force(rbfoss, requests_mock):
    _write_manifest(rbfoss.workdir)

    requests_mock.post(
        url=_FOSSID_API_URL,
        response_list=[
            {'json': _RESP_PROJECT_FOUND}, # get_project → found
            {'json': _RESP_SCAN_FOUND},    # get_scan → found
            {'json': _RESP_OK},            # cancel_run
            {'json': _RESP_OK},            # delete_scan
            # delete_project calls get_all_scans first, then delete
            {'json': {'status': '1', 'data': []}},  # get_all_scans → empty
            {'json': _RESP_OK},                     # delete project
        ],
    )

    rbfoss.run(['-c', '-f'])

    output = rbfoss.read_console()
    assert 'Deleted FossID scan' in output
    assert 'Deleted FossID project' in output


# --setup --upload: git source is transferred to FossID
def test_rbfoss_upload(rbfoss, requests_mock):
    _write_manifest(rbfoss.workdir)

    requests_mock.post(
        url=_FOSSID_API_URL,
        response_list=[
            {'json': _RESP_PROJECT_FOUND},                           # get_project → found (setup)
            {'json': _RESP_OK},                                      # assign_member (setup)
            {'json': _RESP_SCAN_FOUND},                              # get_scan → found (setup)
            {'json': {'status': '1', 'data': 'NOT STARTED'}},       # check_status_download → not started
            {'json': _RESP_OK},                                      # download_content_from_git (initiate)
            {'json': {'status': '1', 'data': 'FINISHED'}},          # check_status_download → finished
        ],
    )

    rbfoss.run(['-s', '-u'])

    output = rbfoss.read_console()
    assert 'Checking git upload status' in output


# --setup --run: FossID scan is executed
def test_rbfoss_run_scan(rbfoss, requests_mock):
    _write_manifest(rbfoss.workdir)

    requests_mock.post(
        url=_FOSSID_API_URL,
        response_list=[
            {'json': _RESP_PROJECT_FOUND},                                  # get_project → found (setup)
            {'json': _RESP_OK},                                             # assign_member (setup)
            {'json': _RESP_SCAN_FOUND},                                     # get_scan → found (setup)
            {'json': {'status': '1', 'data': {'status': 'NEW'}}},          # check_status SCAN → NEW (run)
            {'json': {'status': '1', 'data': []}},                         # get_all_scans → empty (run new)
            {'json': _RESP_OK},                                             # run → ok (run new)
            {'json': {'status': '1', 'data': {'status': 'FINISHED'}}},    # check_status SCAN → finished
        ],
    )

    rbfoss.run(['-s', '-r'])

    output = rbfoss.read_console()
    assert 'Checking FossID scan run status' in output


# --setup --generate-report --report-type=html: FossID scan report is written to the build directory
def test_rbfoss_generate_report(rbfoss, requests_mock):
    _write_manifest(rbfoss.workdir)

    requests_mock.post(
        url=_FOSSID_API_URL,
        response_list=[
            {'json': _RESP_PROJECT_FOUND},          # get_project → found (setup)
            {'json': _RESP_OK},                     # assign_member (setup)
            {'json': _RESP_SCAN_FOUND},             # get_scan → found (setup)
            {'text': '<html>scan report</html>'},   # generate_report → HTML response
        ],
    )

    rbfoss.run(['-s', '-g', '--report-type=html'])

    output = rbfoss.read_console()
    assert 'Generating FossID scan report' in output
    report_path = rbfoss.workdir / f'obj/{_TOOLCHAIN_ID}/fossid_scan_report.html'
    assert report_path.exists()
    assert 'scan report' in report_path.read_text()


# --cancel-run: sends a request to abort an ongoing FossID scan
def test_rbfoss_cancel_run(rbfoss, requests_mock):
    _write_manifest(rbfoss.workdir)

    requests_mock.post(
        url=_FOSSID_API_URL,
        response_list=[
            {'json': _RESP_PROJECT_FOUND},  # get_project → found
            {'json': _RESP_SCAN_FOUND},     # get_scan → found
            {'json': _RESP_OK},             # cancel_run
        ],
    )

    rbfoss.run(['--cancel-run'])

    output = rbfoss.read_console()
    assert 'cancel FossID Scan' in output


# -D --dependencies: walks the dependency tree; no FossID calls when deps list is empty
def test_rbfoss_dependencies_check(rbfoss, requests_mock):
    _write_manifest(rbfoss.workdir)

    # manifest has no dependencies → dependency loop is empty → no FossID API calls
    rbfoss.run(['-D'])
