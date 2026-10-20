# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import json
import pytest

from cyclonedx.schema import OutputFormat, SchemaVersion
from cyclonedx.validation import make_schemabased_validator

from rbbuild.package.package import Package
from rbbuild.package.sbom import SBOM, SBOMFormat

# Unit tests for rbbuild.package.sbom — SBOM class.


def _assert_cdx_valid(data: dict) -> None:
    """Validate a CycloneDX 1.6 JSON document via the official schema validator."""
    validator = make_schemabased_validator(OutputFormat.JSON, SchemaVersion.V1_6)
    errors = validator.validate_str(json.dumps(data))
    assert errors is None, f'CycloneDX 1.6 schema violations: {errors}'


@pytest.fixture
def simple_manifest():
    return {
        'json_version': 5,
        'timestamp': '2024-01-01T00:00:00+00:00',
        'serial_number': 'urn:uuid:00000000-0000-0000-0000-000000000000',
        'document_license': 'CC0-1.0',
        'package': {
            'version_package': 'testpkg',
            'version_string': '1.0.0',
            'purl': 'pkg:rbbuild/testpkg@1.0.0',
            'components': [],
        },
    }


# ---------------------------------------------------------------------------
# SBOMFormat and sbomformat property
# ---------------------------------------------------------------------------

# SBOMFormat.AUTO resolves to CYCLONEDX_1_6 (line 21).
def test_sbomformat_auto_maps_to_cyclonedx():
    sbom = SBOM(SBOMFormat.AUTO)
    assert sbom.sbomformat == SBOMFormat.CYCLONEDX_1_6


def test_sbomformat_explicit():
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    assert sbom.sbomformat == SBOMFormat.CYCLONEDX_1_6


# ---------------------------------------------------------------------------
# json property
# ---------------------------------------------------------------------------

# Accessing json before generate() raises RuntimeError (line 29).
def test_sbom_json_not_initialized_raises():
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    with pytest.raises(RuntimeError, match='not initialized'):
        _ = sbom.json


# ---------------------------------------------------------------------------
# schema_file property
# ---------------------------------------------------------------------------

# schema_file returns correct filename for CycloneDX 1.6 (lines 35-38).
def test_sbom_schema_file_cyclonedx(simple_manifest):
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    assert sbom.schema_file == 'cyclonedx-1.6.schema.json'


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------

# generate() produces a valid CycloneDX 1.6 SBOM (line 45).
def test_sbom_generate_basic(simple_manifest):
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(simple_manifest)
    result = sbom.json
    _assert_cdx_valid(result)
    assert result['bomFormat'] == 'CycloneDX'
    assert result['specVersion'] == '1.6'
    assert result['metadata']['component']['name'] == 'testpkg'


# Manifest with purl: component gets purl set (line 123).
def test_sbom_generate_with_purl(simple_manifest):
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(simple_manifest)
    _assert_cdx_valid(sbom.json)
    comp = sbom.json['metadata']['component']
    assert comp['purl'] == 'pkg:rbbuild/testpkg@1.0.0'
    assert comp['bom-ref'] == 'pkg:rbbuild/testpkg@1.0.0'


# ---------------------------------------------------------------------------
# make_filename()
# ---------------------------------------------------------------------------

# make_filename() returns a correctly formatted filename (lines 58-64).
def test_sbom_make_filename(simple_manifest):
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    pkg = Package(name='mypkg', version='1.0.0')
    result = sbom.make_filename(pkg)
    assert 'mypkg' in result
    assert '1.0.0' in result
    assert result.endswith('sbom.cdx.json')


# ---------------------------------------------------------------------------
# from_json()
# ---------------------------------------------------------------------------

# from_json() recognises CycloneDX 1.6 format.
def test_sbom_from_json_cyclonedx():
    data = {'bomFormat': 'CycloneDX', 'specVersion': '1.6'}
    sbom = SBOM.from_json(data)
    assert sbom.sbomformat == SBOMFormat.CYCLONEDX_1_6
    assert sbom.json is data


# from_json() with unknown format raises NotImplementedError.
def test_sbom_from_json_unknown_raises():
    data = {'bomFormat': 'Unknown', 'specVersion': '99'}
    with pytest.raises(NotImplementedError, match='Unknown SBOM format'):
        SBOM.from_json(data)


# ---------------------------------------------------------------------------
# _cyclonedx_1_6 with dependencies (lines 91-98, 133-139)
# ---------------------------------------------------------------------------

# Dependencies are flattened into cdx['components'] and cdx['dependencies'].
# The top-level package itself must NOT appear in components[] (it is in metadata).
def test_sbom_with_dependencies(simple_manifest):
    simple_manifest['dependencies'] = {
        'child@linux-native': {
            'package': {
                'version_package': 'child',
                'version_string': '0.5.0',
                'purl': 'pkg:rbbuild/child@0.5.0',
                'components': [],
            },
        },
    }
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(simple_manifest)
    result = sbom.json
    _assert_cdx_valid(result)
    assert 'components' in result
    assert 'dependencies' in result
    assert any(c['name'] == 'child' for c in result['components'])
    # top-level package must not be duplicated in components
    component_refs = [c['bom-ref'] for c in result['components']]
    assert 'pkg:rbbuild/testpkg@1.0.0' not in component_refs


# ---------------------------------------------------------------------------
# _cyclonedx_1_6 with tools (lines 101-104)
# ---------------------------------------------------------------------------

# Tools section in manifest is converted to cdx metadata.tools.components.
def test_sbom_with_tools(simple_manifest):
    simple_manifest['tools'] = [
        {
            'vendor': 'ACME',
            'name': 'mybuildtool',
            'version': '2.0',
            'external_references': [
                {'type': 'website', 'url': 'https://example.com'},
            ],
        },
    ]
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(simple_manifest)
    _assert_cdx_valid(sbom.json)
    tools = sbom.json['metadata']['tools']['components']
    assert len(tools) == 1
    assert tools[0]['type'] == 'application'
    assert tools[0]['name'] == 'mybuildtool'
    assert tools[0]['version'] == '2.0'
    assert tools[0]['manufacturer'] == {'name': 'ACME'}
    assert tools[0]['externalReferences'][0]['url'] == 'https://example.com'


# External references are optional.
def test_sbom_with_tool_without_references(simple_manifest):
    simple_manifest['tools'] = [
        {'vendor': 'ACME', 'name': 'mybuildtool', 'version': '2.0'},
    ]
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(simple_manifest)
    _assert_cdx_valid(sbom.json)
    tool = sbom.json['metadata']['tools']['components'][0]
    assert tool == {
        'type': 'application',
        'manufacturer': {'name': 'ACME'},
        'name': 'mybuildtool',
        'version': '2.0',
    }


# Package supplier is mapped to a CycloneDX organizationalEntity.
def test_sbom_package_supplier(simple_manifest):
    simple_manifest['package']['supplier'] = {
        'name': 'ACME',
        'email': 'info@example.com',
        'url': 'https://example.com',
    }
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(simple_manifest)
    _assert_cdx_valid(sbom.json)
    assert sbom.json['metadata']['component']['supplier'] == {
        'name': 'ACME',
        'url': ['https://example.com'],
        'contact': [{'email': 'info@example.com'}],
    }


def test_sbom_package_supplier_omits_undefined_fields(simple_manifest):
    simple_manifest['package']['supplier'] = {
        'name': 'ACME', 'email': None, 'url': None,
    }
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(simple_manifest)
    _assert_cdx_valid(sbom.json)
    assert sbom.json['metadata']['component']['supplier'] == {'name': 'ACME'}


# ---------------------------------------------------------------------------
# Dependencies without own dependencies (any purl type)
# ---------------------------------------------------------------------------

@pytest.fixture
def leaf_manifest(simple_manifest):
    simple_manifest['dependencies'] = {
        'component1@tc': {
            'package': {
                'version_package': 'component1',
                'version_string': '4.1',
                'purl': 'pkg:example.product/ns/component1@4.1',
                'components': [],
            },
        },
        'component2@tc': {
            'package': {
                'version_package': 'component2',
                'version_string': '1.0.14',
                'purl': 'pkg:example.product/ns/component2@1.0.14',
                'components': [],
            },
        },
    }
    return simple_manifest


# Components appear in components[] with their PURL.
def test_sbom_leaf_component_has_purl(leaf_manifest):
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(leaf_manifest)
    result = sbom.json
    _assert_cdx_valid(result)
    purls = {c.get('purl') for c in result['components']}
    assert 'pkg:example.product/ns/component1@4.1' in purls
    assert 'pkg:example.product/ns/component2@1.0.14' in purls


# Components are present in dependencies[] without dependsOn entries.
def test_sbom_leaf_in_dependencies(leaf_manifest):
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(leaf_manifest)
    _assert_cdx_valid(sbom.json)
    deps = {d['ref']: d for d in sbom.json['dependencies']}
    assert deps['pkg:example.product/ns/component1@4.1']['dependsOn'] == []
    assert deps['pkg:example.product/ns/component2@1.0.14']['dependsOn'] == []


# Parent's dependsOn references the components.
def test_sbom_leaf_in_parent_depends_on(leaf_manifest):
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(leaf_manifest)
    _assert_cdx_valid(sbom.json)
    top_dep = next(
        d for d in sbom.json['dependencies']
        if d['ref'] == 'pkg:rbbuild/testpkg@1.0.0'
    )
    assert top_dep['dependsOn'] == [
        'pkg:example.product/ns/component1@4.1',
        'pkg:example.product/ns/component2@1.0.14',
    ]


# Top-level package must not appear in components[].
def test_sbom_leaf_top_level_not_in_components(leaf_manifest):
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(leaf_manifest)
    _assert_cdx_valid(sbom.json)
    component_refs = [c['bom-ref'] for c in sbom.json['components']]
    assert 'pkg:rbbuild/testpkg@1.0.0' not in component_refs


# dependsOn must not contain duplicate entries even if the same package
# appears more than once in the manifest dependencies dict.
def test_sbom_depends_on_no_duplicates(simple_manifest):
    child_pkg = {
        'package': {
            'version_package': 'child',
            'version_string': '1.0',
            'purl': 'pkg:rbbuild/child@1.0',
            'components': [],
        }
    }
    simple_manifest['dependencies'] = {
        'child@a': child_pkg,
        'child@b': child_pkg,
    }
    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(simple_manifest)
    _assert_cdx_valid(sbom.json)
    top_dep = next(
        d for d in sbom.json['dependencies']
        if d['ref'] == 'pkg:rbbuild/testpkg@1.0.0'
    )
    assert top_dep['dependsOn'].count('pkg:rbbuild/child@1.0') == 1
