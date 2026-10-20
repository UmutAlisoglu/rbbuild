# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rbbuild.buildsystem.packaging import Packaging


# Build a minimal Paths mock rooted at tmp_path.
def _make_paths(tmp_path):
    paths = MagicMock()
    paths.source        = tmp_path
    paths.build         = tmp_path / 'obj' / 'test'
    paths.staging       = tmp_path / 'staging' / 'test'
    paths.documentation = tmp_path / 'obj' / 'documentation'
    return paths


# ---------------------------------------------------------------------------
# __bool__
# ---------------------------------------------------------------------------

def test_bool_empty(tmp_path):
    assert not Packaging({}, _make_paths(tmp_path))


def test_bool_none(tmp_path):
    assert not Packaging(None, _make_paths(tmp_path))


def test_bool_nonempty(tmp_path):
    assert Packaging({'pkg': {'files': ['f.txt']}}, _make_paths(tmp_path))


# ---------------------------------------------------------------------------
# items()
# ---------------------------------------------------------------------------

def test_items_returns_config_items(tmp_path):
    cfg = {'a': {'files': ['x']}, 'b': {'files': ['y']}}
    result = dict(Packaging(cfg, _make_paths(tmp_path)).items())
    assert result == cfg


# ---------------------------------------------------------------------------
# resolve_files — happy-path cases
# ---------------------------------------------------------------------------

def test_resolve_files_plain_string(tmp_path, monkeypatch):
    (tmp_path / 'myfile.txt').write_text('hello')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    files = p.resolve_files('pkg', {'files': ['myfile.txt']})
    assert len(files) == 1
    path, strip, dest = files[0]
    assert path == Path('myfile.txt')
    assert strip is None
    assert dest == ''


def test_resolve_files_dict_entry_strip_and_dest(tmp_path, monkeypatch):
    src = tmp_path / 'some' / 'path'
    src.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    files = p.resolve_files('pkg', {'files': [{'src': 'some/path', 'strip': 'ma', 'dest': 'DevKit'}]})
    assert len(files) == 1
    path, strip, dest = files[0]
    assert path == Path('some/path')
    assert strip == 'ma'
    assert dest == 'DevKit'


def test_resolve_files_dict_entry_no_optional_keys(tmp_path, monkeypatch):
    (tmp_path / 'thing').mkdir()
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    files = p.resolve_files('pkg', {'files': [{'src': 'thing'}]})
    assert len(files) == 1
    _, strip, dest = files[0]
    assert strip is None
    assert dest == ''


def test_resolve_files_exclude_filters_entries(tmp_path, monkeypatch):
    mod = tmp_path / 'mymod'
    mod.mkdir()
    (mod / 'a.py').write_text('')
    (mod / 'b.pyc').write_text('')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    files = p.resolve_files('pkg', {'files': ['mymod/**'], 'exclude': ['**/*.pyc']})
    names = [f[0].name for f in files]
    assert 'a.py' in names
    assert 'b.pyc' not in names


def test_resolve_files_glob_wildcard(tmp_path, monkeypatch):
    (tmp_path / 'a.so').write_text('')
    (tmp_path / 'b.so').write_text('')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    files = p.resolve_files('pkg', {'files': ['*.so']})
    names = {f[0].name for f in files}
    assert names == {'a.so', 'b.so'}


# ---------------------------------------------------------------------------
# resolve_files — variable substitution
# ---------------------------------------------------------------------------

def test_resolve_files_obj_var(tmp_path, monkeypatch):
    paths = _make_paths(tmp_path)
    paths.build.mkdir(parents=True)
    (paths.build / 'my_exe').write_text('')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, paths)
    files = p.resolve_files('pkg', {'files': ['$OBJ/my_exe']})
    assert len(files) == 1
    assert files[0][0].name == 'my_exe'


# $OBJ in strip is expanded, so strip does not depend on the toolchain folder.
def test_resolve_files_obj_var_in_strip(tmp_path, monkeypatch):
    paths = _make_paths(tmp_path)
    paths.build.mkdir(parents=True)
    (paths.build / 'libgreet.so').write_text('')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, paths)
    entry = {'src': '$OBJ/libgreet.so', 'strip': '$OBJ/', 'dest': 'mypkg'}
    files = p.resolve_files('pkg', {'files': [entry]})
    path, strip, dest = files[0]
    assert Path(path).relative_to(strip) == Path('libgreet.so')
    assert dest == 'mypkg'


def test_resolve_files_staging_var(tmp_path, monkeypatch):
    paths = _make_paths(tmp_path)
    paths.staging.mkdir(parents=True)
    (paths.staging / 'artifact.tar.gz').write_text('')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, paths)
    files = p.resolve_files('pkg', {'files': ['$STAGING/artifact.tar.gz']})
    assert len(files) == 1
    assert files[0][0].name == 'artifact.tar.gz'


def test_resolve_files_documentation_var(tmp_path, monkeypatch):
    paths = _make_paths(tmp_path)
    paths.documentation.mkdir(parents=True)
    (paths.documentation / 'index.html').write_text('')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, paths)
    files = p.resolve_files('pkg', {'files': ['$DOCUMENTATION/index.html']})
    assert len(files) == 1
    assert files[0][0].name == 'index.html'


# ---------------------------------------------------------------------------
# resolve_files — error cases
# ---------------------------------------------------------------------------

def test_resolve_files_missing_files_key_raises(tmp_path):
    p = Packaging({}, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='missing or empty "files" key'):
        p.resolve_files('pkg', {})


def test_resolve_files_empty_files_list_raises(tmp_path):
    p = Packaging({}, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='missing or empty "files" key'):
        p.resolve_files('pkg', {'files': []})


def test_resolve_files_dict_missing_src_raises(tmp_path):
    p = Packaging({}, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='"src" key'):
        p.resolve_files('pkg', {'files': [{'strip': 'ma'}]})


def test_resolve_files_absolute_path_raises(tmp_path):
    p = Packaging({}, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='relative'):
        p.resolve_files('pkg', {'files': ['/absolute/path']})


def test_resolve_files_no_match_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    files = p.resolve_files('pkg', {'files': ['nonexistent_*.bin']})
    assert files == []


def test_resolve_files_pycache_excluded_for_python_type(tmp_path, monkeypatch):
    mod = tmp_path / 'mypkg'
    mod.mkdir()
    (mod / '__init__.py').write_text('')
    pycache = mod / '__pycache__'
    pycache.mkdir()
    (pycache / '__init__.cpython-311.pyc').write_bytes(b'')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    files = p.resolve_files('lib', {'type': 'python', 'files': ['mypkg/**']})
    names = [f[0].name for f in files]
    assert '__init__.py' in names
    assert '__init__.cpython-311.pyc' not in names
    assert not any('__pycache__' in str(f[0]) for f in files)


def test_resolve_files_pycache_not_excluded_for_auto_type(tmp_path, monkeypatch):
    mod = tmp_path / 'mypkg'
    mod.mkdir()
    pycache = mod / '__pycache__'
    pycache.mkdir()
    (pycache / 'module.cpython-311.pyc').write_bytes(b'')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    # type='auto' (default) must NOT suppress __pycache__ automatically
    files = p.resolve_files('pkg', {'files': ['mypkg/**']})
    assert any('__pycache__' in str(f[0]) for f in files)


# ---------------------------------------------------------------------------
# make_archive
# ---------------------------------------------------------------------------

def test_make_archive_creates_gz(tmp_path):
    src = tmp_path / 'file.txt'
    src.write_text('hello')
    out = tmp_path / 'out.tar.gz'
    Packaging({}, _make_paths(tmp_path)).make_archive(out, [(src, None, '')])
    assert out.exists()
    with tarfile.open(out, 'r:gz') as tar:
        assert any([f.endswith('file.txt') for f in tar.getnames()])


def test_make_archive_creates_xz(tmp_path):
    src = tmp_path / 'file.txt'
    src.write_text('hello')
    out = tmp_path / 'out.tar.xz'
    Packaging({}, _make_paths(tmp_path)).make_archive(out, [(src, None, '')])
    assert out.exists()
    with tarfile.open(out, 'r:xz') as tar:
        assert any([f.endswith('file.txt') for f in tar.getnames()])


def test_make_archive_strip_applied(tmp_path):
    src = tmp_path / 'sub' / 'file.txt'
    src.parent.mkdir()
    src.write_text('hello')
    out = tmp_path / 'out.tar.gz'
    Packaging({}, _make_paths(tmp_path)).make_archive(out, [(src, str(src.parent), '')])
    with tarfile.open(out, 'r:gz') as tar:
        names = tar.getnames()
    assert 'file.txt' in names
    assert 'sub/file.txt' not in names


def test_make_archive_dest_prepended(tmp_path):
    src = tmp_path / 'file.txt'
    src.write_text('hello')
    out = tmp_path / 'out.tar.gz'
    Packaging({}, _make_paths(tmp_path)).make_archive(out, [(src, None, 'myprefix')])
    with tarfile.open(out, 'r:gz') as tar:
        names = tar.getnames()
    assert 'myprefix/file.txt' in names


def test_make_archive_creates_zip(tmp_path):
    src = tmp_path / 'file.txt'
    src.write_text('hello')
    out = tmp_path / 'out.zip'
    Packaging({}, _make_paths(tmp_path)).make_archive(out, [(src, None, '')])
    assert out.exists()
    with zipfile.ZipFile(out, 'r') as zf:
        assert any([f.endswith('file.txt') for f in zf.namelist()])


def test_make_archive_zip_strip_and_dest(tmp_path):
    src = tmp_path / 'sub' / 'file.txt'
    src.parent.mkdir()
    src.write_text('hello')
    out = tmp_path / 'out.zip'
    Packaging({}, _make_paths(tmp_path)).make_archive(out, [(src, str(src.parent), 'myprefix')])
    with zipfile.ZipFile(out, 'r') as zf:
        names = zf.namelist()
    assert 'myprefix/file.txt' in names


def test_make_archive_zip_directory_expanded(tmp_path, monkeypatch):
    mod = tmp_path / 'mymod'
    mod.mkdir()
    (mod / 'a.txt').write_text('a')
    (mod / 'sub').mkdir()
    (mod / 'sub' / 'b.txt').write_text('b')
    monkeypatch.chdir(tmp_path)
    out = tmp_path / 'out.zip'
    Packaging({}, _make_paths(tmp_path)).make_archive(out, [(Path('mymod'), None, '')])
    with zipfile.ZipFile(out, 'r') as zf:
        names = zf.namelist()
    assert 'mymod/a.txt' in names
    assert 'mymod/sub/b.txt' in names


def test_make_archive_unsupported_suffix_raises(tmp_path):
    p = Packaging({}, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='not supported'):
        p.make_archive(tmp_path / 'out.rar', [])


# ---------------------------------------------------------------------------
# build_components
# ---------------------------------------------------------------------------

def test_build_components_skips_python_type(tmp_path, monkeypatch):
    (tmp_path / 'file.txt').write_text('hello')
    monkeypatch.chdir(tmp_path)
    p = Packaging({'lib': {'type': 'python', 'files': ['file.txt']}}, _make_paths(tmp_path))
    components = p.build_components(MagicMock())
    assert components == []


def test_build_components_default_type_is_auto(tmp_path, monkeypatch):
    f = tmp_path / 'archive.tar.gz'
    f.write_bytes(b'dummy content')
    monkeypatch.chdir(tmp_path)
    paths = _make_paths(tmp_path)
    p = Packaging({'pkg': {'files': ['archive.tar.gz']}}, paths)
    mypkg = MagicMock()
    mypkg.name = 'mypkg'
    mypkg.version = '1.0.0.0'
    mypkg.toolchain = 'test'
    components = p.build_components(mypkg)
    assert len(components) == 1
    assert components[0].name == 'pkg'
    assert components[0].suffix == 'gz'


def test_build_components_multi_file_creates_archive(tmp_path, monkeypatch):
    (tmp_path / 'a.txt').write_text('a')
    (tmp_path / 'b.txt').write_text('b')
    monkeypatch.chdir(tmp_path)
    paths = _make_paths(tmp_path)
    paths.build.mkdir(parents=True)
    p = Packaging({'pkg': {'files': ['a.txt', 'b.txt']}}, paths)
    mypkg = MagicMock()
    mypkg.name = 'mypkg'
    mypkg.version = '1.0.0.0'
    mypkg.toolchain = 'test'
    components = p.build_components(mypkg)
    assert len(components) == 1
    assert components[0].suffix == 'tar.xz'
    archive = paths.build / 'mypkg-1.0.0.0-test-pkg.tar.xz'
    assert archive.exists()


def test_build_components_auto_single_file_with_suffix_raises(tmp_path, monkeypatch):
    f = tmp_path / 'lib.tar.xz'
    f.write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    p = Packaging({'pkg': {'files': ['lib.tar.xz'], 'suffix': 'tar.xz'}}, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='must not be used with a plain component'):
        p.build_components(MagicMock())


def test_build_components_unknown_type_raises(tmp_path, monkeypatch):
    f = tmp_path / 'lib.tar.gz'
    f.write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    p = Packaging({'pkg': {'type': 'bogus', 'files': ['lib.tar.gz']}}, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='unknown type'):
        p.build_components(MagicMock())


@pytest.mark.parametrize('ptype', ['auto', 'plain', 'archive'])
def test_build_components_depends_on_non_python_raises(tmp_path, monkeypatch, ptype):
    (tmp_path / 'lib.tar.gz').write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    cfg = {'pkg': {'type': ptype, 'files': ['lib.tar.gz'], 'depends_on': ['other']}}
    p = Packaging(cfg, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='depends-on'):
        p.build_components(MagicMock())


def test_build_components_depends_on_ignored_for_python_type(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = {'lib': {'type': 'python', 'files': ['x'], 'depends_on': ['other']}}
    p = Packaging(cfg, _make_paths(tmp_path))
    assert p.build_components(MagicMock()) == []


@pytest.mark.parametrize('ptype', ['auto', 'plain', 'archive'])
@pytest.mark.parametrize('key, value', [
    ('platform_specific', True),
    ('wheel_tag', 'py3-none-linux_x86_64'),
])
def test_build_components_wheel_keys_non_python_raise(tmp_path, monkeypatch, ptype, key, value):
    (tmp_path / 'lib.tar.gz').write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    cfg = {'pkg': {'type': ptype, 'files': ['lib.tar.gz'], key: value}}
    p = Packaging(cfg, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match=key.replace('_', '-')):
        p.build_components(MagicMock())


def test_build_components_plain_type_single_file(tmp_path, monkeypatch):
    f = tmp_path / 'my_component'
    f.write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    p = Packaging({'pkg': {'type': 'plain', 'files': ['my_component']}}, _make_paths(tmp_path))
    components = p.build_components(MagicMock())
    assert len(components) == 1
    assert components[0].suffix == ''
    assert components[0].filename == 'my_component'


def test_build_components_plain_type_with_suffix_raises(tmp_path, monkeypatch):
    f = tmp_path / 'my_component'
    f.write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    p = Packaging({'pkg': {'type': 'plain', 'suffix': 'bin', 'files': ['my_component']}}, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='must not be used with a plain component'):
        p.build_components(MagicMock())


def test_build_components_plain_type_multi_file_raises(tmp_path, monkeypatch):
    (tmp_path / 'a.txt').write_text('a')
    (tmp_path / 'b.txt').write_text('b')
    monkeypatch.chdir(tmp_path)
    p = Packaging({'pkg': {'type': 'plain', 'files': ['a.txt', 'b.txt']}}, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='requires exactly one matched file'):
        p.build_components(MagicMock())


def test_build_components_archive_type_single_file_still_archives(tmp_path, monkeypatch):
    f = tmp_path / 'my_component'
    f.write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    paths = _make_paths(tmp_path)
    paths.build.mkdir(parents=True)
    p = Packaging({'pkg': {'type': 'archive', 'files': ['my_component']}}, paths)
    mypkg = MagicMock()
    mypkg.name = 'mypkg'
    mypkg.version = '1.0.0.0'
    mypkg.toolchain = 'test'
    components = p.build_components(mypkg)
    assert len(components) == 1
    assert components[0].suffix == 'tar.xz'
    archive = paths.build / 'mypkg-1.0.0.0-test-pkg.tar.xz'
    assert archive.exists()


def test_build_components_archive_type_custom_suffix(tmp_path, monkeypatch):
    f = tmp_path / 'my_component'
    f.write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    paths = _make_paths(tmp_path)
    paths.build.mkdir(parents=True)
    p = Packaging({'pkg': {'type': 'archive', 'suffix': 'tar.gz', 'files': ['my_component']}}, paths)
    mypkg = MagicMock()
    mypkg.name = 'mypkg'
    mypkg.version = '1.0.0.0'
    mypkg.toolchain = 'test'
    components = p.build_components(mypkg)
    assert components[0].suffix == 'tar.gz'
    archive = paths.build / 'mypkg-1.0.0.0-test-pkg.tar.gz'
    assert archive.exists()


def test_build_components_archive_type_zip_suffix(tmp_path, monkeypatch):
    f = tmp_path / 'my_component'
    f.write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    paths = _make_paths(tmp_path)
    paths.build.mkdir(parents=True)
    p = Packaging({'pkg': {'type': 'archive', 'suffix': 'zip', 'files': ['my_component']}}, paths)
    mypkg = MagicMock()
    mypkg.name = 'mypkg'
    mypkg.version = '1.0.0.0'
    mypkg.toolchain = 'test'
    components = p.build_components(mypkg)
    assert components[0].suffix == 'zip'
    archive = paths.build / 'mypkg-1.0.0.0-test-pkg.zip'
    assert archive.exists()


def test_build_components_build_only_flag(tmp_path, monkeypatch):
    f = tmp_path / 'tool.tar.gz'
    f.write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    p = Packaging({'pkg': {'files': ['tool.tar.gz'], 'build_only': True}}, _make_paths(tmp_path))
    mypkg = MagicMock()
    components = p.build_components(mypkg)
    assert components[0].build_only is True


@pytest.mark.parametrize(
    'flags, expected',
    [
        ({}, True),
        ({'traverse': False}, False),
        ({'traverse': True}, True),
        ({'no_traverse': True}, False),
        ({'no_traverse': False}, True),
    ]
)
def test_build_components_traverse_flag(tmp_path, monkeypatch, flags, expected):
    f = tmp_path / 'tool.tar.gz'
    f.write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    p = Packaging({'pkg': {'files': ['tool.tar.gz'], **flags}}, _make_paths(tmp_path))
    components = p.build_components(MagicMock())
    assert components[0].traverse is expected


def test_build_components_traverse_contradiction(tmp_path, monkeypatch):
    f = tmp_path / 'tool.tar.gz'
    f.write_bytes(b'data')
    monkeypatch.chdir(tmp_path)
    p = Packaging(
        {'pkg': {'files': ['tool.tar.gz'], 'traverse': True, 'no_traverse': True}},
        _make_paths(tmp_path))
    with pytest.raises(SyntaxError):
        p.build_components(MagicMock())


def test_build_components_empty_files_skipped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = Packaging({'pkg': {'files': ['nonexistent_*.bin']}}, _make_paths(tmp_path))
    components = p.build_components(MagicMock())
    assert components == []


# ---------------------------------------------------------------------------
# resolve_excluded
# ---------------------------------------------------------------------------

def test_resolve_excluded_empty_when_no_exclude_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    excluded = p.resolve_excluded({'type': 'auto'})
    assert excluded == set()


def test_resolve_excluded_returns_matched_paths(tmp_path, monkeypatch):
    (tmp_path / 'a.pyc').write_bytes(b'')
    (tmp_path / 'b.py').write_text('')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    excluded = p.resolve_excluded({'exclude': ['*.pyc']})
    assert Path('a.pyc') in excluded
    assert Path('b.py') not in excluded


def test_resolve_excluded_adds_pycache_for_python_type(tmp_path, monkeypatch):
    mod = tmp_path / 'mypkg'
    mod.mkdir()
    pycache = mod / '__pycache__'
    pycache.mkdir()
    (pycache / 'mod.cpython-312.pyc').write_bytes(b'')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    excluded = p.resolve_excluded({'type': 'python'})
    assert any('__pycache__' in str(e) for e in excluded)


def test_resolve_excluded_no_pycache_for_auto_type(tmp_path, monkeypatch):
    mod = tmp_path / 'mypkg'
    mod.mkdir()
    pycache = mod / '__pycache__'
    pycache.mkdir()
    (pycache / 'mod.cpython-312.pyc').write_bytes(b'')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    excluded = p.resolve_excluded({'type': 'auto'})
    assert not any('__pycache__' in str(e) for e in excluded)


# ---------------------------------------------------------------------------
# resolve_shared_data — happy-path cases
# ---------------------------------------------------------------------------

def test_resolve_shared_data_absent_returns_empty(tmp_path):
    p = Packaging({}, _make_paths(tmp_path))
    assert p.resolve_shared_data('pkg', {'files': ['x']}) == []


def test_resolve_shared_data_plain_string(tmp_path, monkeypatch):
    (tmp_path / 'config.cfg').write_text('[s]\nk=v')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    result = p.resolve_shared_data('pkg', {'shared_data': ['config.cfg']})
    assert len(result) == 1
    path, strip, dest = result[0]
    assert path == Path('config.cfg')
    assert strip is None
    assert dest == ''


def test_resolve_shared_data_dict_entry_strip_and_dest(tmp_path, monkeypatch):
    data_dir = tmp_path / 'pkg' / 'data'
    data_dir.mkdir(parents=True)
    (data_dir / 'defaults.cfg').write_text('')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    result = p.resolve_shared_data('pkg', {
        'shared_data': [{'src': 'pkg/data/defaults.cfg', 'strip': 'pkg/data', 'dest': 'share/mypkg'}]
    })
    assert len(result) == 1
    path, strip, dest = result[0]
    assert path == Path('pkg/data/defaults.cfg')
    assert strip == 'pkg/data'
    assert dest == 'share/mypkg'


def test_resolve_shared_data_glob_pattern(tmp_path, monkeypatch):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    (data_dir / 'a.cfg').write_text('')
    (data_dir / 'b.cfg').write_text('')
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    result = p.resolve_shared_data('pkg', {'shared_data': [{'src': 'data/*.cfg', 'dest': 'share/pkg'}]})
    names = {r[0].name for r in result}
    assert names == {'a.cfg', 'b.cfg'}


def test_resolve_shared_data_no_match_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = Packaging({}, _make_paths(tmp_path))
    result = p.resolve_shared_data('pkg', {'shared_data': ['nonexistent_*.cfg']})
    assert result == []


# ---------------------------------------------------------------------------
# resolve_shared_data — error cases
# ---------------------------------------------------------------------------

def test_resolve_shared_data_dict_missing_src_raises(tmp_path):
    p = Packaging({}, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='"src" key'):
        p.resolve_shared_data('pkg', {'shared_data': [{'dest': 'share/pkg'}]})


def test_resolve_shared_data_absolute_path_raises(tmp_path):
    p = Packaging({}, _make_paths(tmp_path))
    with pytest.raises(SyntaxError, match='relative'):
        p.resolve_shared_data('pkg', {'shared_data': ['/absolute/path.cfg']})
