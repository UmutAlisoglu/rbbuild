# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

from rbbuild.deps.serializer import Serializer


@pytest.fixture
def serializer():
    yield Serializer()


@pytest.fixture
def deps_parser(app):
    yield app.deps.parser()


# Walk deps_config (normalized list) and return the first parsed Package.
def parse_first(deps_parser, deps_config: list):
    for pkg_items, attrs in deps_parser.walk(deps_config):
        for item in pkg_items:
            pkg = deps_parser.parse_item(item, attrs)
            if pkg:
                return pkg
    return None


# ---------------------------------------------------------------------------
# package_to_deps_item()
# ---------------------------------------------------------------------------

# A package with no flag/SBOM overrides serializes to a bare entry string.
def test_package_to_deps_item_plain_string(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0']}])
    assert serializer.package_to_deps_item(pkg) == 'mypkg-1.0.0'


# The channel is re-included as a prefix if set on the package.
def test_package_to_deps_item_with_channel(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['sample-sources:mypkg-1.0.0']}])
    assert serializer.package_to_deps_item(pkg) == 'sample-sources:mypkg-1.0.0'


# A bare 'build_only' flag round-trips to a line-format string, not a dict -
# flags alone (no SBOM data) stay in the more readable line form.
def test_package_to_deps_item_build_only_flag(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0 build_only']}])
    item = serializer.package_to_deps_item(pkg)
    assert item == 'mypkg-1.0.0 build_only'


# components=/suffixes= attrs are reconstructed from the ComponentSpecifier
# keys and rendered back as line-format attrs (still no SBOM data).
def test_package_to_deps_item_components_and_suffixes(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0 components=dev,prod suffixes=tar.gz']}])
    item = serializer.package_to_deps_item(pkg)
    assert item.startswith('mypkg-1.0.0 ')
    assert 'suffixes=tar.gz' in item
    comp_value = item.split('components=')[1].split()[0]
    assert set(comp_value.split(',')) == {'dev', 'prod'}


# installdir/package_install_action are also line-representable and don't
# force dict format on their own. installdir is only emitted when it
# differs from namespace (see _component_specifier_attrs precedence).
def test_package_to_deps_item_installdir_and_install_action_stay_line_format(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'namespace': 'ns1', 'deps': ['mypkg-1.0.0 installdir=custom_dir package_install_action=copy']}])
    item = serializer.package_to_deps_item(pkg)
    assert item.startswith('mypkg-1.0.0 ')
    assert 'installdir=custom_dir' in item
    assert 'package_install_action=copy' in item


# All SBOM override fields are serialized back onto the entry dict.
def test_package_to_deps_item_sbom_overrides(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': [{
        'entry': 'mypkg-1.0.0',
        'cpe': 'cpe:2.3:a:Example:mypkg:1.0.0:*:*:*:*:*:*:*',
        'copyright': 'Copyright 2025 Example Corp',
        'licenses': ['MIT'],
        'integration_type': 'dynamic_link',
        'component_type': 'library',
        'supplier': {'name': 'Example', 'email': 'foo@example.com'},
    }]}])
    item = serializer.package_to_deps_item(pkg)
    assert item['cpe'] == 'cpe:2.3:a:Example:mypkg:1.0.0:*:*:*:*:*:*:*'
    assert item['copyright'] == 'Copyright 2025 Example Corp'
    assert item['licenses'] == ['MIT']
    assert item['integration_type'] == 'dynamic_link'
    assert item['component_type'] == 'library'
    assert item['supplier'] == {'name': 'Example', 'email': 'foo@example.com'}


# component_type is omitted when it is still the default (APPLICATION).
def test_package_to_deps_item_omits_default_component_type(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0']}])
    item = serializer.package_to_deps_item(pkg)
    assert item == 'mypkg-1.0.0'


# Once any SBOM field is set, flags are folded into the same dict rather
# than staying in the entry string as line attrs.
def test_package_to_deps_item_flags_and_sbom_combined_force_dict(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': [{
        'entry': 'mypkg-1.0.0', 'build_only': True,
        'cpe': 'cpe:2.3:a:Example:mypkg:1.0.0:*:*:*:*:*:*:*',
    }]}])
    item = serializer.package_to_deps_item(pkg)
    assert item == {
        'entry': 'mypkg-1.0.0', 'build_only': True,
        'cpe': 'cpe:2.3:a:Example:mypkg:1.0.0:*:*:*:*:*:*:*',
    }


# Serializing then re-parsing an entry with combined flags + SBOM overrides
# reproduces the same package data (this also exercises the ast.literal_eval
# native-bool fix in DepsParser._coerce_flag()).
def test_package_to_deps_item_round_trip(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': [{
        'entry': 'mypkg-1.0.0',
        'build_only': True,
        'cpe': 'cpe:2.3:a:Example:mypkg:1.0.0:*:*:*:*:*:*:*',
    }]}])
    item = serializer.package_to_deps_item(pkg)
    reparsed = deps_parser.parse_item(item)

    assert reparsed.name == pkg.name
    assert reparsed.version == pkg.version
    assert reparsed.cpe == pkg.cpe
    assert reparsed.component_specifier.check(None, None, 'build_only') is True


def test_package_to_deps_item_traverse_false_line_format(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0 traverse=0']}])
    item = serializer.package_to_deps_item(pkg)
    assert item == 'mypkg-1.0.0 traverse=False'
    reparsed = deps_parser.parse_item(item)
    assert reparsed.component_specifier.check(None, None, 'traverse') is False


def test_package_to_deps_item_legacy_no_traverse_written_as_traverse(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0 no_traverse']}])
    assert serializer.package_to_deps_item(pkg) == 'mypkg-1.0.0 traverse=False'


def test_package_to_deps_item_traverse_default_not_written(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0 traverse=1']}])
    assert serializer.package_to_deps_item(pkg) == 'mypkg-1.0.0'


# ---------------------------------------------------------------------------
# sections_to_toml()
# ---------------------------------------------------------------------------

def test_sections_to_toml_basic(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0']}])
    toml_text = serializer.sections_to_toml([{'namespace': 'ns1', 'deps': [pkg]}])
    assert '[[dependencies]]' in toml_text
    assert 'namespace = "ns1"' in toml_text
    assert '"mypkg-1.0.0"' in toml_text


def test_sections_to_toml_with_overrides(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': [{'entry': 'mypkg-1.0.0', 'build_only': True, 'cpe': 'cpe:xyz'}]}])
    toml_text = serializer.sections_to_toml([{'deps': [pkg]}])
    assert 'entry = "mypkg-1.0.0"' in toml_text
    assert 'build_only = true' in toml_text
    assert 'cpe = "cpe:xyz"' in toml_text


# Section-level restrict_platform/restrict_toolchain pass through unchanged,
# since they are plain dict keys, not Package attributes.
def test_sections_to_toml_preserves_section_restrictions(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0']}])
    toml_text = serializer.sections_to_toml([{'restrict_platform': 'linux', 'deps': [pkg]}])
    assert 'restrict_platform = "linux"' in toml_text


def test_sections_to_toml_multiple_sections(deps_parser, serializer):
    pkg1 = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0']}])
    pkg2 = parse_first(deps_parser, [{'deps': ['otherpkg-2.0.0']}])
    toml_text = serializer.sections_to_toml([
        {'namespace': 'ns1', 'deps': [pkg1]},
        {'namespace': 'ns2', 'deps': [pkg2]},
    ])
    assert toml_text.count('[[dependencies]]') == 2
    assert 'namespace = "ns1"' in toml_text
    assert 'namespace = "ns2"' in toml_text


# table= overrides the emitted header, e.g. for pyproject.toml's nested
# [[tool.rbbuild.dependencies]] form.
def test_sections_to_toml_with_dotted_table(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0']}])
    toml_text = serializer.sections_to_toml(
        [{'namespace': 'ns1', 'deps': [pkg]}], table='tool.rbbuild.dependencies')
    assert '[[tool.rbbuild.dependencies]]' in toml_text
    assert '[[dependencies]]' not in toml_text


# ---------------------------------------------------------------------------
# resolved_dict_to_toml()
# ---------------------------------------------------------------------------

def test_resolved_dict_to_toml(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0']}])
    toml_text = serializer.resolved_dict_to_toml({'ns1': {'mypkg-1.0.0': pkg}})
    assert '[[dependencies]]' in toml_text
    assert 'namespace = "ns1"' in toml_text
    assert '"mypkg-1.0.0"' in toml_text


# An empty namespace key omits the namespace line entirely (top-level deps).
def test_resolved_dict_to_toml_empty_namespace(deps_parser, serializer):
    pkg = parse_first(deps_parser, [{'deps': ['mypkg-1.0.0']}])
    toml_text = serializer.resolved_dict_to_toml({'': {'mypkg-1.0.0': pkg}})
    assert 'namespace' not in toml_text
    assert '"mypkg-1.0.0"' in toml_text
