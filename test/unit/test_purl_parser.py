# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

from rbbuild.deps.purl_parser import PURLParser

# Unit tests for rbbuild.deps.purl_parser.


@pytest.fixture
def parser():
    return PURLParser()


# ---------------------------------------------------------------------------
# parse() — basic pkg: strings
# ---------------------------------------------------------------------------

def test_parse_rbbuild_purl(parser):
    purl = parser.parse('pkg:rbbuild/mycomp@1.2.3', {})
    assert purl.type == 'rbbuild'
    assert purl.name == 'mycomp'
    assert purl.version == '1.2.3'


# String that is neither http(s) nor pkg: raises SyntaxError (line 15).
def test_parse_invalid_string_raises(parser):
    with pytest.raises(SyntaxError):
        parser.parse('invalid_string', {})


# ---------------------------------------------------------------------------
# parse() — http URL conversion path
# ---------------------------------------------------------------------------

# http URL where name+version are in the filename.
def test_parse_http_url_with_name_version_in_filename(parser):
    url = 'http://example.com/downloads/mypkg-2.3.4.tar.gz'
    purl = parser.parse(url, {})
    assert purl.type == 'generic'
    assert purl.name == 'mypkg'
    assert purl.version == '2.3.4'


# https URL with name/version provided explicitly in attrs.
def test_parse_https_url_explicit_name_version(parser):
    url = 'https://example.com/downloads/mypkg-2.3.4.tar.gz'
    purl = parser.parse(url, {'name': 'explicit_name', 'version': '9.9.9'})
    assert purl.name == 'explicit_name'
    assert purl.version == '9.9.9'


# URL where name cannot be derived raises RuntimeError (line 36).
# A URL with root path gives empty filename → name cannot be derived.
def test_parse_http_url_no_name_raises(parser):
    with pytest.raises(RuntimeError, match='Could not derive package name'):
        parser.parse('http://example.com/', {})


# URL where version cannot be derived raises RuntimeError (line 39).
def test_parse_http_url_no_version_raises(parser):
    with pytest.raises(RuntimeError, match='Could not derive package version'):
        parser.parse('http://example.com/downloads/nodash.tar.gz', {})


# ---------------------------------------------------------------------------
# _url_extract_values edge cases
# ---------------------------------------------------------------------------

# Filename with single extension (not multi-part like tar.xz) → line 76.
# File: 'mypkg-1.0.zip' → suffix='zip', no '-' in name part after stripping.
def test_url_extract_values_single_extension(parser):
    name, version, suffix = parser._url_extract_values('http://example.com/mypkg-1.0.zip')
    assert name == 'mypkg'
    assert version == '1.0'
    assert suffix == 'zip'


# Multi-part extension tar.xz is handled correctly — name/version extracted.
def test_url_extract_values_tar_xz(parser):
    name, version, suffix = parser._url_extract_values(
        'http://example.com/components/mylib-3.2.1.tar.xz'
    )
    assert name == 'mylib'
    assert version == '3.2.1'
    assert suffix is not None  # multi-part extension suffix is captured


# Filename with no dot at all: no version, suffix=None (hits line 76 - no '-').
def test_url_extract_values_no_extension(parser):
    name, version, suffix = parser._url_extract_values('http://example.com/nodash')
    assert name == 'nodash'
    assert version is None
    assert suffix is None


# Filename with extension but no '-': name only, no version (line 76 path).
def test_url_extract_values_no_version(parser):
    name, version, suffix = parser._url_extract_values('http://example.com/pkgname.zip')
    assert name == 'pkgname'
    assert version is None
    assert suffix == 'zip'


# ---------------------------------------------------------------------------
# _parse_purl_generic
# ---------------------------------------------------------------------------

# Generic purl gets extra qualifiers set by _parse_purl_generic.
def test_parse_generic_purl_sets_qualifiers(parser):
    url = 'http://example.com/mylib-5.0.tar.gz'
    purl = parser.parse(url, {})
    assert purl.qualifiers.get('url') == url
    assert purl.qualifiers.get('component') == 'mylib'
