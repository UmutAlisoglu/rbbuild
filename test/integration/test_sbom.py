# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import json
import shutil
import sys
import pytest

from datetime import datetime, timezone

_TOOLCHAIN_ID    = 'win32-mingw' if sys.platform == 'win32' else 'linux-native'
_skip_without_toolchain = pytest.mark.skipif(
    shutil.which('cmake') is None,
    reason='cmake not available in PATH',
)


@_skip_without_toolchain
def test_sbom_minimal(rbbuild_empty, cdx_1_6):
    rbbuild = rbbuild_empty
    with open(rbbuild.workdir / 'main.cc', 'w') as fd:
        fd.write('int main() {return 0;}')

    rbbuild.run(['-g', '.'])
    rbbuild.run(['-sbp'])
    obj_path = rbbuild.workdir / f'obj/{_TOOLCHAIN_ID}'
    sbom_path = [*obj_path.glob(f'project-0.0.*.0-{_TOOLCHAIN_ID}-sbom.cdx.json')][0]
    assert sbom_path.exists()
    assert cdx_1_6.validate(sbom_path)

    with open(sbom_path, 'r') as fd:
        sbom = json.load(fd)

    # Content checks
    # top-level
    assert sbom['$schema'] == 'http://cyclonedx.org/schema/bom-1.6.schema.json'
    assert sbom['bomFormat'] == 'CycloneDX'
    assert sbom['specVersion'] == '1.6'
    assert sbom['serialNumber'].startswith('urn:uuid:')
    assert sbom['version'] == 1
    # metadata
    assert sbom['metadata']['timestamp'].startswith(str(datetime.now(timezone.utc).date()))  # ISO 8601 date
    assert sbom['metadata']['licenses'][0]['license']['id'] == 'CC0-1.0'         # document license
    assert sbom['metadata']['component']['type'] == 'application'
    assert sbom['metadata']['component']['name'] == 'project'                    # derived from test path, which is called 'project'
    assert sbom['metadata']['component']['version'].startswith('0.0.')

    # metadata.tools - rbbuild
    tools = sbom['metadata']['tools']['components']
    assert tools[0]['type'] == 'application'
    assert tools[0]['manufacturer'] == {'name': 'Robert Bosch GmbH'}
    assert tools[0]['name'] == 'rbbuild'
    assert len(tools[0]['version']) > 8
    assert [r['url'] for r in tools[0]['externalReferences']] == ['https://github.com/boschglobal/rbbuild']

    # metadata.tools - profile (vendor from [profile.supplier])
    assert tools[1]['manufacturer'] == {'name': 'rbbuild user'}
    assert tools[1]['name'] == 'standalone'
    assert tools[1]['version'] == '1.0.0'
    assert 'externalReferences' not in tools[1]

    # dependencies
    assert 'components' not in sbom
    assert 'dependencies' not in sbom


@_skip_without_toolchain
def test_sbom_with_deps(rbbuild, cdx_1_6):
    with open(rbbuild.workdir / 'main.cc', 'w') as fd:
        fd.write('int main() {return 0;}')

    with open(rbbuild.workdir / 'rbbuild.toml', 'w') as fd:
        fd.write('[dependencies]\ndeps=["libbar"]')

    rbbuild.run(['-g', '.'])

    rbbuild.run(['-FI'])
    rbbuild.run(['-sbp'])
    obj_path = rbbuild.workdir / f'obj/{_TOOLCHAIN_ID}'
    sbom_path = [*obj_path.glob(f'project-0.0.*.0-{_TOOLCHAIN_ID}-sbom.cdx.json')][0]

    assert sbom_path.exists()
    assert cdx_1_6.validate(sbom_path)

    with open(sbom_path, 'r') as fd:
        sbom = json.load(fd)

    # Content checks
    # top-level
    assert sbom['$schema'] == 'http://cyclonedx.org/schema/bom-1.6.schema.json'
    assert sbom['bomFormat'] == 'CycloneDX'
    assert sbom['specVersion'] == '1.6'
    assert sbom['serialNumber'].startswith('urn:uuid:')
    assert sbom['version'] == 1
    # metadata
    assert sbom['metadata']['timestamp'].startswith(str(datetime.now(timezone.utc).date()))  # ISO 8601 date
    assert sbom['metadata']['licenses'][0]['license']['id'] == 'CC0-1.0'         # document license
    assert sbom['metadata']['component']['type'] == 'application'
    assert sbom['metadata']['component']['name'] == 'project'                    # derived from test path, which is called 'project'
    assert sbom['metadata']['component']['version'].startswith('0.0.')

    # metadata.tools - rbbuild
    tools = sbom['metadata']['tools']['components']
    assert tools[0]['manufacturer'] == {'name': 'Robert Bosch GmbH'}
    assert tools[0]['name'] == 'rbbuild'
    assert len(tools[0]['version']) > 8
    assert len(tools[0]['externalReferences']) == 1

    # metadata.tools - profile (vendor from [profile.supplier])
    assert tools[1]['manufacturer'] == {'name': 'Example Corp'}
    assert tools[1]['name'] == 'test'
    assert tools[1]['version'] == '1.0.0'
    assert 'externalReferences' not in tools[1]

    # metadata.component - supplier defaults to [profile.supplier]
    assert sbom['metadata']['component']['supplier'] == {
        'name': 'Example Corp',
        'url': ['https://example.com/'],
        'contact': [{'email': 'info@example.com'}],
    }

    # dependencies
    assert 'components' in sbom
    assert 'dependencies' in sbom


