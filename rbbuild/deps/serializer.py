# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from typing import Dict, List, Union

from rbbuild.package.package import Package, PackageInstallAction
from rbbuild.package.type import PackageType


# Inverse of DepsParser: turns Package objects back into deps-entry
# strings/dicts and full [[dependencies]] TOML.
class Serializer:

    # Prefers the readable "line" entry format (plain string, flags as
    # space-separated attrs) and only falls back to the dict/'entry' form
    # when SBOM metadata is present - SBOM fields (cpe, copyright, licenses,
    # integration_type, component_type, supplier) can't all be expressed as
    # space-separated attrs (supplier is a nested table), so once any of
    # them is set the whole entry is written as a dict for consistency.
    def package_to_deps_item(self, pkg: Package) -> Union[str, dict]:
        entry_str = str(pkg)
        if pkg.channel:
            entry_str = f'{pkg.channel}:{entry_str}'

        line_attrs = {}
        line_attrs.update(self._component_specifier_attrs(pkg))

        if pkg.installdir and pkg.installdir != pkg.namespace:
            line_attrs['installdir'] = pkg.installdir

        if pkg.install_action != PackageInstallAction.DEFAULT:
            line_attrs['package_install_action'] = str(pkg.install_action)

        sbom_attrs = self._sbom_attrs(pkg)

        if sbom_attrs:
            return {'entry': entry_str, **line_attrs, **sbom_attrs}

        if not line_attrs:
            return entry_str

        return self._line_format(entry_str, line_attrs)


    def _sbom_attrs(self, pkg: Package) -> dict:
        attrs = {}

        if pkg.cpe:
            attrs['cpe'] = pkg.cpe

        if pkg.copyright:
            attrs['copyright'] = pkg.copyright

        if pkg.licenses:
            attrs['licenses'] = [str(lic) for lic in pkg.licenses]

        if pkg.integration_type is not None:
            attrs['integration_type'] = str(pkg.integration_type)

        if (pkg.component_type is not None
                and pkg.component_type != PackageType.APPLICATION):
            attrs['component_type'] = str(pkg.component_type)

        supplier_attrs = self._supplier_attrs(pkg)
        if supplier_attrs:
            attrs['supplier'] = supplier_attrs

        return attrs


    # Renders entry_str plus attrs as DepsParser.parse_attrs()'s
    # space-separated "<flag>|<key>=<value>" syntax.
    def _line_format(self, entry_str: str, attrs: dict) -> str:
        parts = [entry_str]
        for key, value in attrs.items():
            parts.append(key if value is True else f'{key}={value}')
        return ' '.join(parts)


    # dependencies_config has the same shape as Application.config.dependencies.
    # table selects the TOML table name the sections are written under -
    # 'dependencies' for rbbuild.toml, 'tool.rbbuild.dependencies' for
    # pyproject.toml.
    def sections_to_toml(
            self, dependencies_config: List[dict],
            table: str = 'dependencies') -> str:
        sections = []
        for section in dependencies_config:
            lines = [f'[[{table}]]']
            for key, value in section.items():
                if key == 'deps':
                    continue
                lines.append(f'{key} = {self._toml_value(value)}')

            lines.append('deps = [')
            for item in section.get('deps', []):
                if isinstance(item, Package):
                    item = self.package_to_deps_item(item)
                lines.append(f'    {self._toml_deps_item(item)},')
            lines.append(']')

            sections.append('\n'.join(lines))

        return '\n\n'.join(sections)


    # Adapter for the {namespace: {pkgid: Package}} shape produced by
    # Resolver.run() (used by pkq.py's resolve()).
    def resolved_dict_to_toml(
            self, resolved: Dict[str, Dict[str, Package]]) -> str:
        dependencies_config = []
        for namespace, packages in resolved.items():
            section = {}
            if namespace:
                section['namespace'] = namespace
            section['deps'] = list(packages.values())
            dependencies_config.append(section)

        return self.sections_to_toml(dependencies_config)


    # component_specifier keys are a components x suffixes cross-product,
    # but the editor only ever sets one uniform flag pair per Package, so
    # any single key's values apply to the whole entry.
    def _component_specifier_attrs(self, pkg: Package) -> dict:
        spec = pkg.component_specifier
        if spec is None or not spec.items:
            return {}

        attrs = {}
        values = next(iter(spec.items.values()))
        if values.get('build_only'):
            attrs['build_only'] = True
        if values.get('traverse') is False:
            attrs['traverse'] = False

        components = sorted({key[0] for key in spec.items if key[0]})
        if components:
            attrs['components'] = ','.join(components)

        suffixes = sorted({key[1] for key in spec.items if key[1]})
        if suffixes:
            attrs['suffixes'] = ','.join(suffixes)

        return attrs


    def _supplier_attrs(self, pkg: Package) -> dict:
        if pkg.supplier is None:
            return {}

        supplier = {}
        if pkg.supplier.name:
            supplier['name'] = pkg.supplier.name
        if pkg.supplier.email:
            supplier['email'] = pkg.supplier.email
        if pkg.supplier.url:
            supplier['url'] = pkg.supplier.url
        return supplier


    def _toml_string(self, value: str) -> str:
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'


    def _toml_value(self, value) -> str:
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, str):
            return self._toml_string(value)
        if isinstance(value, list):
            items = ', '.join(self._toml_value(item) for item in value)
            return f'[{items}]'
        if isinstance(value, dict):
            items = ', '.join(
                f'{k} = {self._toml_value(v)}' for k, v in value.items())
            return f'{{ {items} }}'
        raise TypeError(f'Unsupported TOML value type: {type(value)}')


    def _toml_deps_item(self, item: Union[str, dict]) -> str:
        if isinstance(item, str):
            return self._toml_string(item)
        return self._toml_value(item)
