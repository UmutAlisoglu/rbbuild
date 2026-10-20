# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest
from rbbuild.sourcedir.jenkinsfile import Jenkinsfile


def test_empty_jenkinsfile(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    jf.touch()
    jenkinsfile = Jenkinsfile(path=jf)
    assert jenkinsfile.data == {}


def test_empty_block_legacy(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    with open(jf, 'w') as fd:
        fd.write('gvciPlugin() {}')
    jenkinsfile = Jenkinsfile(path=jf)
    assert jenkinsfile.data == {}


def test_empty_block(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    with open(jf, 'w') as fd:
        fd.write('rbbuild() {}')
    jenkinsfile = Jenkinsfile(path=jf)
    assert jenkinsfile.data == {}


def test_no_rbbuild_jenkinsfile(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    with open(jf, 'w') as fd:
        fd.write('no_rbbuild_jenkinsfile_statements() {}')
    jenkinsfile = Jenkinsfile(path=jf)
    assert jenkinsfile.data == {}


def test_unkown_block(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    with open(jf, 'w') as fd:
        fd.write(
'''rbbuild() {
   unkown_block {}
}
''')
    with pytest.raises(Exception):
        jenkinsfile = Jenkinsfile(path=jf)
        _ = jenkinsfile.data


def test_profile(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    with open(jf, 'w') as fd:
        fd.write(
'''rbbuild() {
    profile = 'myprofile'
}
''')
    jenkinsfile = Jenkinsfile(path=jf)
    assert jenkinsfile.data == {'profile': 'myprofile'}


def test_profile_legacy(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    with open(jf, 'w') as fd:
        fd.write(
'''gvciPlugin() {
    profile = 'myprofile'
}
''')
    jenkinsfile = Jenkinsfile(path=jf)
    assert jenkinsfile.data == {'profile': 'myprofile'}


def test_toolchain_and_profile(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    with open(jf, 'w') as fd:
        fd.write(
'''rbbuild() {
    toolchain = ['native', 'yocto-armhf-4.0']
    profile = 'myprofile'
}
''')
    jenkinsfile = Jenkinsfile(path=jf)
    assert len(jenkinsfile.data) == 2
    assert jenkinsfile.data['profile'] == 'myprofile'
    assert jenkinsfile.data['toolchain'] == ['native', 'yocto-armhf-4.0']


def test_inline_comment(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    with open(jf, 'w') as fd:
        fd.write(
'''rbbuild() {
    // this is some comment
    toolchain = ['native', 'yocto-armhf-4.0']
    // this is another comment that contains a = symbol
    profile = 'myprofile'
}
''')
    jenkinsfile = Jenkinsfile(path=jf)
    assert len(jenkinsfile.data) == 2
    assert jenkinsfile.data['profile'] == 'myprofile'
    assert jenkinsfile.data['toolchain'] == ['native', 'yocto-armhf-4.0']


def test_getitem(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    jf.write_text("rbbuild() {\n    profile = 'mypkg'\n}\n")
    jenkinsfile = Jenkinsfile(path=jf)
    assert jenkinsfile['profile'] == 'mypkg'


def test_contains(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    jf.write_text("rbbuild() {\n    profile = 'mypkg'\n}\n")
    jenkinsfile = Jenkinsfile(path=jf)
    assert 'profile' in jenkinsfile
    assert 'other' not in jenkinsfile


def test_get_method(tmp_path):
    jf = tmp_path / 'Jenkinsfile'
    jf.write_text("rbbuild() {\n    profile = 'mypkg'\n}\n")
    jenkinsfile = Jenkinsfile(path=jf)
    assert jenkinsfile.get('profile') == 'mypkg'
    assert jenkinsfile.get('missing', 'default') == 'default'
    assert jenkinsfile.get('missing') is None

