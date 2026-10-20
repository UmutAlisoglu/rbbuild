# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest
import re

from datetime import datetime, timezone

from rbbuild.package.license import License
from rbbuild.package.package import Package, PackageType, Supplier, Tool, ExternalReference, IntegrationType
from rbbuild.version import __version__

urn_uuid_pattern = 'urn:uuid:[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}'


@pytest.fixture
def manifest(app):
    yield app.package.manifest()


def test_manifest_from_pkg_default(manifest):
    pkg = Package(name='test_package_name', version='1.2.3-master.4')
    assert pkg

    result = manifest.from_package(pkg)
    assert result

    # Top-level
    assert result.get('json_version') == 5
    ts = datetime.fromisoformat(result.get('timestamp'))
    assert ts.tzinfo == timezone.utc
    assert re.match(urn_uuid_pattern, result.get('serial_number'))
    assert result.get('document_license') == 'CC0-1.0'

    # Tools - rbbuild
    # Note: active profile is added here. In our tests, test is always the active profile
    assert result.get('tools') is None

    # Package
    assert result.get('package')
    assert result['package']['version_package'] == 'test_package_name'
    assert result['package']['version_string'] == '1.2.3-master.4'
    assert 'purl' not in result['package']   # PURL is set in BuildSystem.make_mypkg()
    assert result['package']['components'] == {}
    assert result['package'].get('licenses') is None
    assert result['package'].get('copyright') is None
    assert result['package'].get('provenance') is None
    assert result['package'].get('supplier') is None
    assert result['package'].get('linkage') is None
    assert result['package'].get('cpe') is None


def test_manifest_from_pkg_full(app, manifest):
    base_url = 'https://artifactory.example.com/ui/repos/tree/General'
    repository = 'myartifactory-development-local'
    root_path = 'components'

    settings = app.core.settings()
    tools = [
        Tool(
            vendor='Example Corp',
            name='rbbuild',
            version=__version__,
            external_references=[
                ExternalReference(type='website', url='https://example.com/rbbuild/'),
                ExternalReference(type='website', url='https://example.com/dist/rbbuild/'),
            ]
        ),
        Tool(
            vendor='Example Corp',
            name=settings.profile_name,
            version=settings.profile_version,
            external_references=[
                ExternalReference(type='website', url='https://example.com/profiles/'),
                ExternalReference(type='website', url='https://example.com/dist/profiles/'),
            ]
        ),
    ]

    pkg = Package(name='pkg', version='1.2.3-master.4')
    pkg.channel = app.core.channel()
    pkg.toolchain = app.core.toolchain()
    pkg.url = f'{base_url}/{repository}/{root_path}/pkg/1.2.3-master.4'
    pkg.component_type = PackageType.LIBRARY
    pkg.licenses = License.coerce('MIT AND BSD-3')
    pkg.copyright = 'copyright 2024 Example Corp'
    pkg.ancestors = ['original_pkg']
    pkg.cpe = 'cpe:2.3:a:Example Corp:rbbuild_test:6.0.0:*:*:*:*:*:*:*'
    pkg.supplier = Supplier( name='Example Corp',
                             email='info@example.com',
                             url='https://example.com/' )
    pkg.integration_type = IntegrationType.STATIC_LINK
    pkg.git_hash = '1234'
    pkg.git_repo = 'some-repo'
    pkg.tools = tools

    result = manifest.from_package(pkg)

    # Top-level
    assert result.get('json_version') == 5
    ts = datetime.fromisoformat(result.get('timestamp'))
    assert ts.tzinfo == timezone.utc
    assert re.match(urn_uuid_pattern, result.get('serial_number'))
    assert result.get('document_license') == 'CC0-1.0'

    # Tools - rbbuild
    assert result.get('tools')
    assert result['tools'][0].get('vendor')               == 'Example Corp'
    assert result['tools'][0].get('name')                 == 'rbbuild'
    assert result['tools'][0].get('version')
    assert result['tools'][0].get('external_references')  == [
        {
            'type': 'website',
            'url': 'https://example.com/rbbuild/',
        },
        {
            'type': 'website',
            'url':  'https://example.com/dist/rbbuild/',
        }
    ]
    # Tools - profiles
    # Note: active profile is added here. In our tests, test is always the active profile
    assert result['tools'][1].get('vendor')               == 'Example Corp'
    assert result['tools'][1].get('name')                 == 'test'
    assert result['tools'][1].get('version') is not None
    assert result['tools'][1].get('external_references')  == [
        {
            'type': 'website',
            'url': 'https://example.com/profiles/',
        },
        {
            'type': 'website',
            'url': 'https://example.com/dist/profiles/'
        }
    ]

    # Package
    assert result.get('package')
    assert result['package']['version_package'] == 'pkg'
    assert result['package']['version_string'] == '1.2.3-master.4'
    assert 'purl' not in result['package']
    assert result['package']['channel'] == 'example-development'
    assert result['package']['toolchain'] == 'linux-native'
    assert result['package']['url'] == f'{base_url}/{repository}/{root_path}/pkg/1.2.3-master.4'
    assert result['package']['components'] == {}
    assert result['package']['component_type'] == 'library'
    assert result['package']['git']['hash'] == '1234'
    assert result['package']['git']['repo'] == 'some-repo'
    assert result['package']['licenses'] == [{'expression': 'MIT AND BSD-3'}]
    assert result['package']['copyright'] == 'copyright 2024 Example Corp'
    assert result['package']['ancestors'] == ['original_pkg']
    assert result['package']['cpe'] == 'cpe:2.3:a:Example Corp:rbbuild_test:6.0.0:*:*:*:*:*:*:*'
    assert result['package']['supplier'] == { 'name': 'Example Corp',
                                              'email': 'info@example.com',
                                              'url': 'https://example.com/' }
    assert result['package']['integration_type'] == 'static_link'


@pytest.mark.parametrize( 'input_license, output_license',
                          [
                              ('Apache-2.0', [{'expression': 'Apache-2.0'}]),
                              ([{'expression': 'Apache-2.0', 'acknowledgement': 'declared'}], None),
                              ([{'license': {'id': 'Apache-2.0'}}], None),
                              ([{'id': 'Apache-2.0'}], [{'license': {'id': 'Apache-2.0'}}]),
                              ([{'license': {'id': 'Apache-2.0'}}, {'license': {'id': 'BSD-3'}}], None),
                              ([{'id': 'Apache-2.0'}, {'id': 'BSD-3'}], [{'license': {'id': 'Apache-2.0'}}, {'license': {'id': 'BSD-3'}}]),
                              ([{'license': {'name': 'Some License', 'text': {'content': 'text, text, blabla'}}}], None),
                              ([{ 'license': {
                                      'name': 'Some License',
                                      'text': {'content': 'text, text, blabla'},
                                      'acknowledgement': 'declared',
                                      'url': 'http://some-url/',
                                      'properties': {'x': 1, 'y': 2},
                                      'licensing': {'licenseTypes': 'academic'}
                                  }
                                }],
                                None),
                          ]
                        )
def test_manifest_sbom_licenses(manifest, input_license, output_license):
    pkg = Package(name='pkg', version='1.2.3-master.4')
    pkg.licenses = License.coerce(input_license)

    result = manifest.from_package(pkg)
    if not output_license:
        output_license = input_license

    assert result['package']['licenses'] == output_license


@pytest.mark.parametrize( 'input_license',
                          [
                              [{'expression': 'Apache-2.0'}, {'expression': 'BSD-3'}],  # only one item
                              [{'expression': 'Apache-2.0', 'id': 'xxx'}],              # only expression allowed
                              [{'expression': 'Apache-2.0', 'name': 'xxx'}],            # only expression allowed
                              [{'license': {
                                  'id': 'GPL-2.0',
                                  'name': 'GNU Public License'}
                              }],                                                       # either id or name, not both
                              [{'license': {'url': 'blabla'}}],                         # either id or name or expression
                              [{'license': {'id': 'GPL-2.0', 'invalid_key': 'blabla'}}] # key not allowed
                          ]
                        )
def test_manifest_sbom_licenses_invalid(input_license):
    with pytest.raises(SyntaxError):
        License.coerce(input_license)


# ---------------------------------------------------------------------------
# make_filename
# ---------------------------------------------------------------------------

def test_make_filename_no_toolchain(manifest):
    result = manifest.make_filename('mypkg', '1.2.3', toolchain=None)
    assert result == 'mypkg-1.2.3-manifest.json'


def test_make_filename_with_toolchain(manifest):
    from rbbuild.core.toolchain import Toolchain
    toolchains = {'linux-native': {'platform': 'linux', 'tcid': 'native', 'cmake_file': None}}
    tc = Toolchain(tcid='linux-native', toolchains_config=toolchains)
    result = manifest.make_filename('mypkg', '1.2.3', toolchain=tc)
    assert result == 'mypkg-1.2.3-linux-native-manifest.json'


def test_make_filename_legacy(manifest):
    from rbbuild.core.toolchain import Toolchain
    toolchains = {'linux-native': {'platform': 'linux', 'tcid': 'native', 'cmake_file': None}}
    tc = Toolchain(tcid='linux-native', toolchains_config=toolchains)
    result = manifest.make_filename('mypkg', '1.2.3', toolchain=tc, legacy=True)
    assert result == 'mypkg-1.2.3-native-manifest.json'


# ---------------------------------------------------------------------------
# from_package — additional fields
# ---------------------------------------------------------------------------

def test_manifest_from_pkg_with_purl(manifest):
    from packageurl import PackageURL
    pkg = Package(name='mypkg', version='1.0.0')
    pkg.purl = PackageURL.from_string('pkg:rbbuild/mypkg@1.0.0')
    result = manifest.from_package(pkg)
    assert result['package']['purl'] == 'pkg:rbbuild/mypkg@1.0.0'


# External references of a tool are optional and omitted if undefined.
def test_manifest_from_pkg_tool_without_references(manifest):
    pkg = Package(name='mypkg', version='1.0.0')
    pkg.tools = [Tool(vendor='Example Corp', name='rbbuild', version='6.0')]
    result = manifest.from_package(pkg)
    assert result['tools'] == [
        {'vendor': 'Example Corp', 'name': 'rbbuild', 'version': '6.0'},
    ]


def test_manifest_from_pkg_with_components(manifest):
    from rbbuild.package.component import Component
    pkg = Package(name='mypkg', version='1.0.0')
    pkg.components = [
        Component(name='default', suffix='tar.xz', filename='mypkg-1.0.0-native.tar.xz'),
        Component(name='dev', suffix='tar.xz', filename='mypkg-1.0.0-native-dev.tar.xz',
                  checksum='abc123', build_only=True),
    ]
    result = manifest.from_package(pkg)
    comps = result['package']['components']
    assert len(comps) == 2
    assert comps[0]['name'] == 'default'
    assert comps[0]['suffix'] == 'tar.xz'
    assert comps[1]['checksum'] == 'abc123'
    assert comps[1]['build_only'] is True


def test_manifest_from_pkg_with_dependencies(manifest):
    parent = Package(name='parent', version='2.0.0')
    child = Package(name='child', version='1.0.0')
    parent.dependencies = {'child': child}
    result = manifest.from_package(parent)
    assert 'dependencies' in result
    dep_manifest = result['dependencies']['child']
    assert dep_manifest['package']['version_package'] == 'child'
    # dependencies should NOT have top-level fields
    assert 'json_version' not in dep_manifest


# top_level=False skips the json_version/timestamp/serial/document_license fields.
def test_manifest_from_pkg_not_top_level(manifest):
    pkg = Package(name='mypkg', version='1.0.0')
    result = manifest.from_package(pkg, top_level=False)
    assert 'json_version' not in result
    assert 'timestamp' not in result
    assert result['package']['version_package'] == 'mypkg'


# ---------------------------------------------------------------------------
# PackageParser.parse() — missing branch coverage
# ---------------------------------------------------------------------------

@pytest.fixture
def manifest_parser(app_test):
    yield app_test.package.parser()


# Non-legacy manifest without 'package' key → SyntaxError
def test_parse_missing_package_key(manifest_parser):
    manifest_json = {'json_version': 5, 'timestamp': '2024-01-01T00:00:00+00:00'}
    with pytest.raises(SyntaxError):
        manifest_parser.parse(manifest_json)


# Null (None) child dependency value → warning, dep is skipped
def test_parse_null_dependency(manifest_parser, monkeypatch):
    import sys
    from rbbuild.librbb.term import term as term_obj
    monkeypatch.setattr(term_obj, 'log_file', sys.stderr)
    manifest_json = {
        'json_version': 5,
        'package': {
            'version_package': 'mypkg',
            'version_string': '1.0.0',
            'toolchain': 'linux-native',
        },
        'dependencies': {
            'dep_null@linux-native': None,
        },
    }
    pkg = manifest_parser.parse(manifest_json)
    assert pkg is not None
    assert pkg.dependencies == {}


# Dependency key with namespace prefix (e.g. 'myns/dep@toolchain')
def test_parse_dependency_with_namespace(manifest_parser):
    manifest_json = {
        'json_version': 5,
        'package': {
            'version_package': 'container_pkg',
            'version_string': '1.0.0',
            'toolchain': 'linux-native',
        },
        'dependencies': {
            'myns/dep_pkg@linux-native': {
                'json_version': 5,
                'package': {
                    'version_package': 'dep_pkg',
                    'version_string': '0.5.0',
                    'toolchain': 'linux-native',
                },
            }
        },
    }
    pkg = manifest_parser.parse(manifest_json)
    assert pkg is not None
    assert len(pkg.dependencies) == 1


# ---------------------------------------------------------------------------
# pkg.toolchain is correctly populated for all deps after parsing
# ---------------------------------------------------------------------------

# A dep with toolchain= in its package section must have pkg.toolchain set.
def test_parse_dep_toolchain_set_from_package_section(manifest_parser):
    manifest_json = {
        'json_version': 5,
        'package': {
            'version_package': 'parent',
            'version_string': '1.0.0',
            'toolchain': 'linux-native',
        },
        'dependencies': {
            'child@linux-native': {
                'package': {
                    'version_package': 'child',
                    'version_string': '2.0.0',
                    'toolchain': 'linux-native',
                },
            },
        },
    }
    pkg = manifest_parser.parse(manifest_json)
    assert pkg is not None
    child = next(iter(pkg.dependencies.values()))
    # toolchain must be set — not None
    assert child.toolchain is not None
    assert str(child.toolchain) == 'linux-native'


# Two deps with different toolchains must each have their own toolchain set.
def test_parse_deps_distinct_toolchains(manifest_parser):
    manifest_json = {
        'json_version': 5,
        'package': {
            'version_package': 'parent',
            'version_string': '1.0.0',
            'toolchain': 'linux-native',
        },
        'dependencies': {
            'dep_linux@linux-native': {
                'package': {
                    'version_package': 'dep_linux',
                    'version_string': '1.0.0',
                    'toolchain': 'linux-native',
                },
            },
            'dep_win@win32-mingw': {
                'package': {
                    'version_package': 'dep_win',
                    'version_string': '1.0.0',
                    'toolchain': 'win32-mingw',
                },
            },
        },
    }
    pkg = manifest_parser.parse(manifest_json)
    assert pkg is not None
    assert len(pkg.dependencies) == 2
    deps = {d.name: d for d in pkg.dependencies.values()}
    assert str(deps['dep_linux'].toolchain) == 'linux-native'
    assert str(deps['dep_win'].toolchain) == 'win32-mingw'


# ---------------------------------------------------------------------------
# manifest.load
# ---------------------------------------------------------------------------

def test_manifest_load(app, tmp_path):
    import json as _json
    manifest_obj = app.package.manifest()
    manifest_data = {
        'json_version': 5,
        'timestamp': '2024-01-01T00:00:00+00:00',
        'serial_number': 'urn:uuid:00000000-0000-0000-0000-000000000000',
        'document_license': 'CC0-1.0',
        'package': {
            'version_package': 'testpkg',
            'version_string': '3.0.0',
            'components': [],
        },
    }
    manifest_path = tmp_path / 'testpkg-3.0.0-manifest.json'
    manifest_path.write_text(_json.dumps(manifest_data))
    pkg = manifest_obj.load(manifest_path)
    assert pkg.name == 'testpkg'
    assert pkg.version == '3.0.0'
    assert pkg.manifest is not None
    assert pkg.manifest.filename == 'testpkg-3.0.0-manifest.json'



# A manifest without toolchain yields a package without toolchain.
def test_parse_package_without_toolchain(manifest_parser):
    manifest_json = {
        'json_version': 5,
        'package': {
            'version_package': 'pure',
            'version_string': '1.0.0',
        },
    }
    pkg = manifest_parser.parse(manifest_json)
    assert pkg.toolchain is None


def test_manifest_from_pkg_without_toolchain_omits_toolchain(manifest):
    pkg = Package(name='pure', version='1.0.0')
    assert 'toolchain' not in manifest.from_package(pkg)['package']
