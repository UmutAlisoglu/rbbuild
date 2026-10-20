#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import pytest

def test_fail_no_argument(concat_files):
    with pytest.raises(SystemExit):
        concat_files.run(args=[])


def test_fail_dir_input(concat_files):
    outfile = str(concat_files.workdir / 'outfile')
    with pytest.raises((IsADirectoryError, PermissionError)):
        concat_files.run(args=[outfile, 'testdata'])


def test_valid_dir_input_base(concat_files):
    concat_files.run(['outfile', '-T', '.'])
    outfile = concat_files.workdir / 'outfile'
    assert outfile.exists()
    with open(outfile) as fd:
        assert fd.read().strip() == 'testdata/a\n1\ntestdata/b\n2'


def test_valid_dir_input_testdata(concat_files):
    concat_files.run(['outfile', '-T', 'testdata'])
    outfile = concat_files.workdir / 'outfile'
    assert outfile.exists()
    with open(outfile) as fd:
        assert fd.read().strip() == 'a\n1\nb\n2'


def test_valid_file_input_single_file(concat_files):
    concat_files.run(['outfile', 'testdata/a'])
    outfile = concat_files.workdir / 'outfile'
    assert outfile.exists()
    with open(outfile) as fd:
        assert fd.read().strip() == 'testdata/a\n1'


def test_valid_file_input_two_files(concat_files):
    concat_files.run(['outfile', 'testdata/a', 'testdata/b'])
    outfile = concat_files.workdir / 'outfile'
    assert outfile.exists()
    with open(outfile) as fd:
        assert fd.read().strip() == 'testdata/a\n1\ntestdata/b\n2'


def test_delim_static(concat_files):
    concat_files.run(['-d' '%%%', 'outfile', 'testdata/a', 'testdata/b'])
    outfile = concat_files.workdir / 'outfile'
    assert outfile.exists()
    with open(outfile) as fd:
        assert fd.read().strip() == '%%%\n1\n%%%\n2'


def test_delim_dyn_arg(concat_files):
    concat_files.run(['-d' '*{}*', 'outfile', 'testdata/a', 'testdata/b'])
    outfile = concat_files.workdir / 'outfile'
    assert outfile.exists()
    with open(outfile) as fd:
        assert fd.read().strip() == '*testdata/a*\n1\n*testdata/b*\n2'


def test_delim_dyn_arg_dir(concat_files):
    concat_files.run(['-d' '*{}*', 'outfile', '-T', 'testdata'])
    outfile = concat_files.workdir / 'outfile'
    assert outfile.exists()
    with open(outfile) as fd:
        assert fd.read().strip() == '*a*\n1\n*b*\n2'


def test_html_single(concat_files):
    concat_files.run(['-H', 'outfile.html', 'testdata/a'])
    outfile = concat_files.workdir / 'outfile.html'
    assert outfile.exists()
    doc=(
'''<!DOCTYPE html>
<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=utf-8"/>
</head>
<body>
<pre>
</pre>
<h1>testdata/a</h1>
<pre>
1
</pre>
</body>
</html>''')
    with open(outfile) as fd:
        assert fd.read().strip() == doc


def test_html_multiple(concat_files):
    concat_files.run(['-H', 'outfile.html', '-T', 'testdata'])
    outfile = concat_files.workdir / 'outfile.html'
    assert outfile.exists()
    doc=(
'''<!DOCTYPE html>
<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=utf-8"/>
</head>
<body>
<pre>
</pre>
<h1>a</h1>
<pre>
1
</pre>
<h1>b</h1>
<pre>
2
</pre>
</body>
</html>''')
    with open(outfile) as fd:
        assert fd.read().strip() == doc
