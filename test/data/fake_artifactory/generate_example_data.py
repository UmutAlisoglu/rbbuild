#!/usr/bin/env python

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

# Generates the generic fake repositories used by the integration tests:
#
#   example-development-local/components/   (channel "example-development")
#   sample-development-local/components/sample_tools, conflict_demo-like
#                                           (channel "sample-development")
#
# Run from the project root: python test/data/fake_artifactory/generate_example_data.py
# The output is deterministic, so re-running does not change committed files.

import hashlib
import io
import json
import lzma
import shutil
import tarfile

from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TIMESTAMP = '2026-01-01T00:00:00+00:00'
_TOOLCHAINS = ['linux-native', 'win32-mingw']


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _make_tar_xz(files: dict) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as tar:
        for name, content in sorted(files.items()):
            data = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
    return lzma.compress(buf.getvalue())


class Repo:
    def __init__(self, repo_dir: str, root: str, channel: str):
        self.root = _HERE / repo_dir / root
        self.channel = channel


    # comps: {name: {'files': {path: content}, 'build_only': bool}}
    def publish(self, name, version, toolchain, comps, deps=None, git=True):
        outdir = self.root / name / version
        outdir.mkdir(parents=True, exist_ok=True)
        prefix = f'{name}-{version}-{toolchain}'

        entries = []
        for cname, comp in comps.items():
            if cname == 'sbom':
                suffix = 'json'
                filename = f'{prefix}-sbom.cdx.json'
                data = json.dumps({
                    'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1,
                }, indent=4).encode()
            else:
                suffix = 'tar.xz'
                filename = f'{prefix}-{cname}.tar.xz'
                data = _make_tar_xz(comp.get('files', {}))
            (outdir / filename).write_bytes(data)
            entry = {
                'name': cname,
                'suffix': suffix,
                'filename': filename,
                'checksum': _sha1(data),
            }
            if comp.get('build_only'):
                entry['build_only'] = True
            entries.append(entry)

        manifest = {
            'json_version': 5,
            'timestamp': _TIMESTAMP,
            'serial_number': 'urn:uuid:' + str(self._uuid(prefix)),
            'document_license': 'CC0-1.0',
            'package': self.package_node(name, version, toolchain, entries, git),
        }
        if deps:
            manifest['dependencies'] = self.dependencies_node(deps)

        path = outdir / f'{prefix}-manifest.json'
        path.write_text(json.dumps(manifest, indent=4) + '\n')
        return manifest


    def package_node(self, name, version, toolchain, entries, git=True):
        node = {
            'version_package': name,
            'version_string': version,
            'components': entries,
            'toolchain': toolchain,
            'channel': self.channel,
            'purl': f'pkg:rbbuild/example/{name}@{version}?toolchain={toolchain}',
            'component_type': 'application',
        }
        if git:
            node['git'] = {
                'repo': f'https://example.com/git/{name}.git',
                'hash': _sha1(f'{name}-{version}'.encode()),
                'branch': 'main',
            }
        return node


    # deps: list of (child manifest dict, build_only); each child keeps its own
    # nested dependencies
    def dependencies_node(self, deps):
        result = {}
        for child, build_only in deps:
            self._add_dependency(result, child, build_only)
        return result


    def _add_dependency(self, result, child, build_only):
        node = {'package': child['package']}
        if child.get('dependencies'):
            node['dependencies'] = child['dependencies']
        node = json.loads(json.dumps(node))
        if build_only:
            self._mark_build_only(node)
        pkg = node['package']
        key = f'{pkg["version_package"]}-{pkg["version_string"]}@{pkg["toolchain"]}'
        result[key] = node


    def _mark_build_only(self, node):
        for comp in node['package']['components']:
            comp['build_only'] = True
        for sub in node.get('dependencies', {}).values():
            self._mark_build_only(sub)


    @staticmethod
    def _uuid(text):
        import uuid
        return uuid.UUID(hashlib.md5(text.encode()).hexdigest())


def _lib_files(name, version, major):
    suffix = '' if major >= 2 else f'_v{major}'
    return {
        'prod': {'files': {f'usr/lib/{name}{suffix}.so': f'{name} {version}\n'}},
        'dev': {'files': {f'usr/include/{name[3:]}{suffix}.h': f'// {name} {version}\n'}},
        'licenses': {'files': {f'licenses/{name}-license.txt': 'MIT\n'}},
        'debug': {'files': {}},
    }


def generate_example_development():
    repo_dir = _HERE / 'example-development-local'
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    repo = Repo('example-development-local', 'components', 'example-development')

    # libbaz: many versions without components (sorting, query limits)
    for version in ['0.9.0.1', '1.0.0.1', '1.0.0.2', '1.1.0.3', '1.1.0.4', '2.0.0.5']:
        repo.publish('libbaz', version, 'linux-native', {}, git=False)

    # libfoo: prod/dev files change between 1.x and 2.x
    libfoo = {}
    for version, major in [('1.0.0.1', 1), ('1.1.0.2', 1), ('2.0.0.3', 2)]:
        for tc in _TOOLCHAINS:
            libfoo[(version, tc)] = repo.publish(
                'libfoo', version, tc, _lib_files('libfoo', version, major))

    # testlib <- testtool: build-only chain
    testlib = {}
    testtool = {}
    for tc in _TOOLCHAINS:
        testlib[tc] = repo.publish('testlib', '1.0.0.1', tc, {
            'dev': {'files': {'usr/include/testlib.h': '// testlib\n'}},
        })
        testtool[tc] = repo.publish('testtool', '1.0.0.1', tc, {
            'prod': {'files': {'usr/bin/testtool': '#!/bin/sh\n'}},
            'dev': {'files': {'usr/include/testtool.h': '// testtool\n'}},
        }, deps=[(testlib[tc], False)])

    # libbar: runtime dependency libfoo, build-only dependency testtool
    for version, foo_version in [('1.0.0.1', '1.0.0.1'), ('2.0.0.2', '2.0.0.3')]:
        for tc in _TOOLCHAINS:
            repo.publish('libbar', version, tc, _lib_files('libbar', version, 2),
                         deps=[(libfoo[(foo_version, tc)], False), (testtool[tc], True)])

    # The latest libbar is only available for another toolchain
    tc = 'linux-ubuntu-armhf'
    foo = repo.publish('libfoo', '2.0.0.3', tc, _lib_files('libfoo', '2.0.0.3', 2))
    repo.publish('libbar', '3.0.0.3', tc, _lib_files('libbar', '3.0.0.3', 2),
                 deps=[(foo, False)])


def generate_sample_tools():
    repo_dir = _HERE / 'sample-development-local' / 'components' / 'sample_tools'
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    repo = Repo('sample-development-local', 'components', 'sample-development')

    def comps(version):
        result = {
            name: {'files': {f'{name}/{name}.toml': f'version = "{version}"\n'}}
            for name in ['alpha', 'beta', 'gamma']
        }
        result['sbom'] = {'build_only': True}
        return result

    for version in ['1.0.0.1', '1.0.0.2', '1.1.0.3', '2.0.0.4']:
        # 1.0.0.2 was only published for linux-native
        for tc in (_TOOLCHAINS[:1] if version == '1.0.0.2' else _TOOLCHAINS):
            repo.publish('sample_tools', version, tc, comps(version))


if __name__ == '__main__':
    generate_example_development()
    generate_sample_tools()
