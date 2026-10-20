# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from enum import Enum
from typing import Tuple, Iterator

from rbbuild.package.package import Package


class SBOMFormat(Enum):
    AUTO = 0
    CYCLONEDX_1_6 = 1


class SBOM:
    def __init__(self, sbomformat: SBOMFormat):
        self._sbomformat = sbomformat
        self._json = None


    @property
    def sbomformat(self) -> SBOMFormat:
        if self._sbomformat == SBOMFormat.AUTO:
            return SBOMFormat.CYCLONEDX_1_6

        return self._sbomformat


    @property
    def json(self) -> dict:
        if not self._json:
            raise RuntimeError('SBOM JSON data not initialized (via generate() or from_json())')
        return self._json


    @property
    def schema_file(self) -> str:
        if self.sbomformat == SBOMFormat.CYCLONEDX_1_6:
            return 'cyclonedx-1.6.schema.json'

        raise NotImplementedError(f'Schema format {str(self.sbomformat)} is not implemented')


    def generate(self, manifest: dict):
        if self.sbomformat == SBOMFormat.CYCLONEDX_1_6:
            self._json = self._cyclonedx_1_6(manifest)
        else:
            raise NotImplementedError(f'Schema format {str(self.sbomformat)} is not implemented')


    def make_filename(self, pkg: Package) -> str:
        if self.sbomformat == SBOMFormat.CYCLONEDX_1_6:
            suffix = 'sbom.cdx.json'
        else:
            raise NotImplementedError(f'Schema format {str(self.sbomformat)} is not implemented')
        return '-'.join(filter(None, [pkg.name, pkg.version, str(pkg.toolchain) if pkg.toolchain else None, suffix]))


    @classmethod
    def from_json(self, data: dict) -> 'SBOM':
        if data.get('bomFormat') == 'CycloneDX' and data.get('specVersion') == '1.6':
            sbom = SBOM(SBOMFormat.CYCLONEDX_1_6)
        else:
            raise NotImplementedError('Unknown SBOM format!')

        sbom._json = data
        return sbom


    def _cyclonedx_1_6(self, manifest: dict, top_level=True) -> dict:
        cdx = {}
        if top_level is True:
            cdx['$schema'] = 'http://cyclonedx.org/schema/bom-1.6.schema.json'
            cdx['bomFormat'] = 'CycloneDX'
            cdx['specVersion'] = '1.6'
            cdx['serialNumber'] = manifest['serial_number']
            cdx['version'] = 1
            cdx['metadata'] = {
                'timestamp': manifest['timestamp'],   # rbbuild defines this field only in top-level
            }
            if 'document_license' in manifest:
                cdx['metadata']['licenses'] = [{'license': {'id': manifest.get('document_license')}}]

        cdx.setdefault('metadata', {})
        cdx['metadata']['component'] =  self._cyclonedx_1_6_component(manifest['package'])

        # TODO: rbbuild and CycloneDX are different w.r.t dependencies
        # For CycloneDX, we need:
        # * fill all dependencies in cdx["components"] as a flat list ("assembly")
        # * fill all dependencies in cdx["dependencies"] as a flat list with "dependsOn" relations


        if 'dependencies' in manifest:
            components = {}
            deps = {}
            top_ref = manifest['package'].get(
                'purl',
                f'{manifest["package"]["version_package"]}-{manifest["package"]["version_string"]}'
            )
            for comp, dep in self._cyclonedx_1_6_traverse_manifest_deps(manifest):
                if comp['bom-ref'] not in components:
                    components[comp['bom-ref']] = comp
                deps[dep['ref']] = dep
            components.pop(top_ref, None)
            cdx['components'] = list(components.values())
            cdx['dependencies'] = list(deps.values())

        if 'tools' in manifest:
            cdx.setdefault('metadata', {})
            cdx['metadata']['tools'] = {
                'components': [self._cyclonedx_1_6_tool(tool) for tool in manifest['tools']],
            }

        return cdx


    # Convert rbbuild manifest "tools" item into CycloneDX "component" object
    def _cyclonedx_1_6_tool(self, tool: dict) -> dict:
        component = {
            'type': 'application',
            'manufacturer': {'name': tool['vendor']},
            'name': tool['name'],
        }
        if tool.get('version'):
            component['version'] = tool['version']
        if tool.get('external_references'):
            component['externalReferences'] = tool['external_references']
        return component


    # Convert rbbuild manifest "package" object into CycloneDX "component" object
    def _cyclonedx_1_6_component(self, package: dict) -> dict:
        component = {
            'type': package.get('component_type', 'application'),
            'name': package['version_package'],
            'version': package['version_string'],
        }
        component['bom-ref'] = package.get('purl', f'{package["version_package"]}-{package["version_string"]}')
        if 'purl' in package:
            component['purl'] = package['purl']

        # TODO: git_hash/git_repo, integration_type
        for field in ['copyright', 'licenses', 'ancestors', 'cpe']:
            if field in package:
                component[field] = package[field]
        supplier = self._cyclonedx_1_6_supplier(package.get('supplier') or {})
        if supplier:
            component['supplier'] = supplier
        return component


    # CycloneDX organizationalEntity allows neither "email" nor a plain "url"
    def _cyclonedx_1_6_supplier(self, supplier: dict) -> dict:
        entity = {}
        if supplier.get('name'):
            entity['name'] = supplier['name']
        if supplier.get('url'):
            entity['url'] = [supplier['url']]
        if supplier.get('email'):
            entity['contact'] = [{'email': supplier['email']}]
        return entity


    def _cyclonedx_1_6_traverse_manifest_deps(self, pkg: dict) -> Iterator[Tuple[dict, dict]]:
        comp = self._cyclonedx_1_6_component(pkg['package'])
        dep = { 'ref': pkg['package'].get('purl', f'{pkg["package"]["version_package"]}-{pkg["package"]["version_string"]}'),
                'dependsOn': [] }
        for dpkg in pkg.get('dependencies', {}).values():
            child_ref = dpkg['package'].get('purl', f'{dpkg["package"]["version_package"]}-{dpkg["package"]["version_string"]}')
            if child_ref not in dep['dependsOn']:
                dep['dependsOn'].append(child_ref)
            yield from self._cyclonedx_1_6_traverse_manifest_deps(dpkg)
        yield comp, dep

