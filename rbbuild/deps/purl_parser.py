# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from packageurl import PackageURL
from pathlib import Path
from typing import Dict, Tuple
from urllib.parse import urlparse, quote_plus

from rbbuild.librbb.term import term


class PURLParser:
    def parse(self, pkgstr: str, attrs: Dict[str, str]) -> PackageURL:
        if pkgstr.startswith('http://') or pkgstr.startswith('https://'):
            pkgstr = self._url_to_purlstr(pkgstr, attrs)

        if not pkgstr.startswith('pkg:'):
            raise SyntaxError(f'Invalid package string {term.bright_white(pkgstr)}. Expected string starting with {term.bright_white("pkg:")} or {term.bright_white("http://")} or {term.bright_white("https://")}')

        purl = PackageURL.from_string(pkgstr)

        if purl.type == 'generic':
            purl = self._parse_purl_generic(purl, attrs)

        attrs.update(purl.qualifiers)
        attrs['purl'] = purl.to_string()
        return purl


    def _url_to_purlstr(self, url: str, attrs: Dict[str, str]) -> str:
        name = attrs.pop('name') if 'name' in attrs else None
        version = attrs.pop('version') if 'version' in attrs else None
        # Extract missing information from filename in the URL
        if not name or not version:
            n, v, _ = self._url_extract_values(url)
            name    = name or n
            version = version or v
            if not name:
                raise RuntimeError(f'Could not derive package name from {url}. Try adding {term.bright_white("name=<package name>")}.')

            if not version:
                raise RuntimeError(f'Could not derive package version from {url}. Try adding {term.bright_white("version=<package version>")}.')

        return f'pkg:generic/{name}@{version}?download_url={quote_plus(url)}'


    def _parse_purl_generic(self, purl: PackageURL, attrs: Dict[str, str]) -> PackageURL:
        url = purl.qualifiers.pop('download_url')
        _, _, suffix = self._url_extract_values(url)
        purl.qualifiers['channel'] = None
        purl.qualifiers['toolchain'] = None
        purl.qualifiers['url'] = url
        purl.qualifiers['suffix'] = suffix
        purl.qualifiers['component'] = purl.name
        #purl.qualifiers['build_only'] = '1'
        #purl.qualifiers['no_traverse'] = '1'
        return purl


    def _url_extract_values(self, url) -> Tuple[str, str, str]:
        multi_suffixes = ['tar.xz', 'tar.gz', 'tar.bz2']

        r = urlparse(url)
        filename = Path(r.path).name
        version = None
        suffix = None
        if '.' in filename:
            if filename.count('.') > 1:
                for sfx in multi_suffixes:
                    if filename.endswith(sfx):
                        suffix = filename[len(sfx)-1:]
                        filename = filename[:-len(sfx)-1]
                        break

            if not suffix:
                filename, suffix = filename.rsplit('.', maxsplit=1)

        if '-' in filename:
            name, version = filename.split('-', maxsplit=1)
        else:
            name = filename

        return name, version, suffix

