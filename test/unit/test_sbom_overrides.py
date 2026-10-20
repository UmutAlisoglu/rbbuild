import pytest

from rbbuild.package.license import License
from rbbuild.package.package import Package, PackageType, IntegrationType
from rbbuild.package.sbom import SBOM, SBOMFormat

# Copyright Example Corp",
# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def deps_parser(app):
    yield app.deps.parser()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Walk deps_config (normalized list) and return the first parsed Package.
def parse_first(deps_parser, deps_config: list) -> Package:
    for pkg_items, attrs in deps_parser.walk(deps_config):
        for item in pkg_items:
            pkg = deps_parser.parse_item(item, attrs)
            if pkg:
                return pkg
    return None


# ---------------------------------------------------------------------------
# 1. Basic parsing of the "entry" key
# ---------------------------------------------------------------------------

# An 'entry' dict item must resolve the package name and version correctly.
def test_sbom_override_entry_key_parses_name_version(deps_parser):
    pkg = parse_first(deps_parser, [{'deps': [{'entry': 'myproduct-1.9.9'}]}])
    assert pkg is not None
    assert pkg.name == 'myproduct'
    assert pkg.version == '1.9.9'


# ---------------------------------------------------------------------------
# 2. Channel prefix in "entry" value
# ---------------------------------------------------------------------------

# The 'entry' value supports the 'channel:pkg-version' syntax.
def test_sbom_override_entry_key_with_channel_prefix(deps_parser):
    pkg = parse_first(deps_parser, [{'deps': [{'entry': 'sample-sources:myproduct-2.0.0'}]}])
    assert pkg is not None
    assert pkg.name == 'myproduct'
    assert pkg.version == '2.0.0'
    assert pkg.channel is not None
    assert pkg.channel.name == 'sample-sources'


# ---------------------------------------------------------------------------
# 3. License override – bare string list (syntactic sugar)
# ---------------------------------------------------------------------------

# licenses field as a list of bare strings is treated as SPDX expressions.
def test_sbom_override_licenses_string_list(deps_parser):
    pkg = parse_first(deps_parser, [{'deps': [{'entry': 'mypkg-1.0.0', 'licenses': ['MIT OR GPL-2.0-only']}]}])
    assert pkg.licenses is not None
    assert len(pkg.licenses) == 1
    assert pkg.licenses[0].expression == 'MIT OR GPL-2.0-only'


# ---------------------------------------------------------------------------
# 4. License override – CycloneDX expression dict
# ---------------------------------------------------------------------------

# licenses field in CycloneDX expression dict format is accepted.
def test_sbom_override_licenses_cyclonedx_expression_dict(deps_parser):
    pkg = parse_first(deps_parser, [{'deps': [{'entry': 'mypkg-1.0.0', 'licenses': [{'expression': 'Apache-2.0'}]}]}])
    assert pkg.licenses is not None
    assert len(pkg.licenses) == 1
    assert pkg.licenses[0].expression == 'Apache-2.0'


# ---------------------------------------------------------------------------
# 5. License override – CycloneDX component dict with license id
# ---------------------------------------------------------------------------

# licenses field in CycloneDX component dict format (license.id) is accepted.
def test_sbom_override_licenses_cyclonedx_id_dict(deps_parser):
    pkg = parse_first(deps_parser, [{'deps': [{'entry': 'mypkg-1.0.0', 'licenses': [{'license': {'id': 'MIT'}}]}]}])
    assert pkg.licenses is not None
    assert len(pkg.licenses) == 1
    assert pkg.licenses[0].id == 'MIT'


# ---------------------------------------------------------------------------
# 6. Copyright override
# ---------------------------------------------------------------------------

# copyright field is stored verbatim on the Package.
def test_sbom_override_copyright(deps_parser):
    pkg = parse_first(deps_parser, [{'deps': [{'entry': 'mypkg-1.0.0', 'copyright': 'Copyright 2025 Example Corp'}]}])
    assert pkg.copyright == 'Copyright 2025 Example Corp'


# ---------------------------------------------------------------------------
# 7. CPE override
# ---------------------------------------------------------------------------

# cpe field is stored verbatim on the Package.
def test_sbom_override_cpe(deps_parser):
    cpe_value = 'cpe:2.3:a:Example:myproduct:1.9.9:*:*:*:*:*:*:*'
    pkg = parse_first(deps_parser, [{'deps': [{'entry': 'mypkg-1.9.9', 'cpe': cpe_value}]}])
    assert pkg.cpe == cpe_value


# ---------------------------------------------------------------------------
# 8. integration_type override
# ---------------------------------------------------------------------------

# integration_type field is parsed into the IntegrationType enum.
def test_sbom_override_integration_type(deps_parser):
    pkg = parse_first(deps_parser, [{'deps': [{'entry': 'mypkg-1.0.0', 'integration_type': 'dynamic_link'}]}])
    assert pkg.integration_type == IntegrationType.DYNAMIC_LINK


# ---------------------------------------------------------------------------
# 9. component_type override
# ---------------------------------------------------------------------------

# component_type field is parsed into the PackageType enum.
def test_sbom_override_component_type(deps_parser):
    pkg = parse_first(deps_parser, [{'deps': [{'entry': 'mypkg-1.0.0', 'component_type': 'library'}]}])
    assert pkg.component_type == PackageType.LIBRARY


# ---------------------------------------------------------------------------
# 10. Multiple SBOM fields in one dict entry
# ---------------------------------------------------------------------------

# All SBOM override fields can be combined in a single dict entry.
def test_sbom_override_multiple_fields(deps_parser):
    pkg = parse_first(deps_parser, [{'deps': [{
        'entry': 'sample-development:myproduct-1.9.9',
        'licenses': ['MIT OR GPL-2.0-only'],
        'cpe': 'cpe:2.3:a:Example:myproduct:1.9.9:*:*:*:*:*:*:*',
        'copyright': 'Copyright Example Corp',
        'integration_type': 'dynamic_link',
        'component_type': 'library',
    }]}])
    assert pkg.name == 'myproduct'
    assert pkg.version == '1.9.9'
    assert pkg.licenses[0].expression == 'MIT OR GPL-2.0-only'
    assert pkg.cpe == 'cpe:2.3:a:Example:myproduct:1.9.9:*:*:*:*:*:*:*'
    assert pkg.copyright == 'Copyright Example Corp'
    assert pkg.integration_type == IntegrationType.DYNAMIC_LINK
    assert pkg.component_type == PackageType.LIBRARY


# ---------------------------------------------------------------------------
# 11. Section-level attributes inherited by dict entry
# ---------------------------------------------------------------------------

# A dict 'entry' item inherits section-level attributes such as build_only.
def test_sbom_override_inherits_section_build_only(deps_parser):
    deps_config = [{
        'deps': [{'entry': 'mypkg-1.0.0', 'licenses': ['Apache-2.0']}],
        'build_only': 'True',
    }]
    pkg = parse_first(deps_parser, deps_config)
    assert pkg is not None
    assert pkg.component_specifier is not None
    # build_only is stored per (component, suffix) key inside _items
    assert all(v.get('build_only') is True for v in pkg.component_specifier.items.values())
    assert pkg.licenses[0].expression == 'Apache-2.0'


# ---------------------------------------------------------------------------
# 12. Dict entry and plain string entry coexist in the same deps list
# ---------------------------------------------------------------------------

# Dict entries and plain string entries can coexist in the same deps list.
def test_sbom_override_mixed_with_string_entries(deps_parser):
    deps_config = [{'deps': [
        'libfoo',
        {'entry': 'myproduct-1.9.9', 'licenses': ['MIT'], 'copyright': 'Copyright Example Corp'},
    ]}]
    pkgs = []
    for pkg_items, attrs in deps_parser.walk(deps_config):
        for item in pkg_items:
            pkg = deps_parser.parse_item(item, attrs)
            if pkg:
                pkgs.append(pkg)

    assert len(pkgs) == 2
    names = {p.name for p in pkgs}
    assert 'libfoo' in names
    assert 'myproduct' in names

    overridden = next(p for p in pkgs if p.name == 'myproduct')
    assert overridden.licenses[0].expression == 'MIT'
    assert overridden.copyright == 'Copyright Example Corp'


# ---------------------------------------------------------------------------
# 13. SBOM CycloneDX generation reflects license override
# ---------------------------------------------------------------------------

# SBOM.generate() produces a CycloneDX component that includes the overridden license.
def test_sbom_generate_includes_license_override():
    pkg = Package(name='myproduct', version='1.9.9')
    pkg.licenses = License.coerce(['Apache-2.0'])
    pkg.copyright = 'Copyright 2025 Example Corp'
    pkg.cpe = 'cpe:2.3:a:Example:myproduct:1.9.9:*:*:*:*:*:*:*'

    manifest = {
        'serial_number': 'urn:uuid:00000000-0000-0000-0000-000000000001',
        'timestamp': '2025-01-01T00:00:00+00:00',
        'document_license': 'CC0-1.0',
        'package': {
            'version_package': pkg.name,
            'version_string': pkg.version,
            'licenses': [lic.to_dict() for lic in pkg.licenses],
            'copyright': pkg.copyright,
            'cpe': pkg.cpe,
        }
    }

    sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
    sbom.generate(manifest)
    cdx = sbom.json

    component = cdx['metadata']['component']
    assert component['licenses'] == [{'expression': 'Apache-2.0'}]
    assert component['copyright'] == 'Copyright 2025 Example Corp'
    assert component['cpe'] == 'cpe:2.3:a:Example:myproduct:1.9.9:*:*:*:*:*:*:*'


# ---------------------------------------------------------------------------
# 14. ancestors override
# ---------------------------------------------------------------------------

# ancestors field is stored as a list on the Package.
def test_sbom_override_ancestors(deps_parser):
    pkg = parse_first(deps_parser, [{'deps': [{'entry': 'mypkg-1.0.0', 'ancestors': ['original_pkg-1.0.0']}]}])
    assert pkg.ancestors == ['original_pkg-1.0.0']


# ---------------------------------------------------------------------------
# 15. Invalid SBOM field in dict entry raises SyntaxError
# ---------------------------------------------------------------------------

# An unrecognised key in a dict entry must raise a SyntaxError.
def test_sbom_override_invalid_field_raises_error(deps_parser):
    deps_config = [{'deps': [{'entry': 'mypkg-1.0.0', 'not_a_valid_field': 'some_value'}]}]
    with pytest.raises(SyntaxError):
        for pkg_items, attrs in deps_parser.walk(deps_config):
            for item in pkg_items:
                deps_parser.parse_item(item, attrs)
