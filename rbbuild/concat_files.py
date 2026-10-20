#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import sys
import glob
import os.path
import argparse
import shutil
import tempfile
import fnmatch


class TextWriter:
    def __init__(self, outfile, append, delimiter):
        if append:
            mode = 'a'
        else:
            mode = 'w'

        if not delimiter:
            self.delimiter = '{}'
        else:
            self.delimiter = delimiter

        self.outf = open(outfile, mode, encoding='utf-8')


    def __del__(self):
        if hasattr(self, 'outf'):
            self.outf.close()


    def write(self, line):
        self.outf.write(line)

    def writeSection(self, line):
        self.outf.write(self.delimiter.format(line) + '\n')


class HTMLWriter:
    def __init__(self, outfile, append):
        self.outfile_name = outfile
        self.outf = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False)
        self.outf.write('<!DOCTYPE html>\n'
                        '<html>\n'
                        '<head>\n'
                        '<meta http-equiv="content-type" content="text/html; charset=utf-8"/>\n'
                        '</head>\n'
                        '<body>\n'
                        '<pre>\n')
        self.append = append
        if append:
            with open(outfile, 'r', encoding='utf-8') as infile:
                # Skip header
                for _ in range(3):
                    next(infile)
                for line in infile:
                    # Skip HTML and body end tags.
                    # They will be added in the destructor.
                    if line.startswith('</body>') or line.startswith('</html>'):
                        continue
                    self.outf.write(line)


    def __del__(self):
        # Add HTML closing tags
        self.outf.write('</pre>\n'
                        '</body>\n'
                        '</html>\n')

        self.outf.close()
        shutil.move(self.outf.name, self.outfile_name)

    def write(self, line):
         self.outf.write(line)

    def writeSection(self, line):
        self.outf.write('</pre>\n'
                        '<h1>{}</h1>\n'
                        '<pre>\n'.format(line))


class ConcatFilesMain:
    def parse_command_line(self):
        parser = argparse.ArgumentParser(description='%s -- Tool to generate concatenated text files' % os.path.basename(sys.argv[0]))
        parser.add_argument('outfile', metavar='outfile',  help='Output file')
        parser.add_argument('infiles', metavar='infiles', nargs='*', help='Input files')
        parser.add_argument( '-a', '--append', action='store_const', const=True, help='Append to outfile')
        parser.add_argument( '-d', '--delimiter', action='store', dest='delimiter', help='Delimiter between files (use {} to print filename; ignored with -H)')
        parser.add_argument( '-T', '--traverse-directory', action='store', dest='traverse_dir', help='Recursively traverse through directory (instead of infile)')
        parser.add_argument( '-H', '--html', action='store_const', const='html', help='Generate HTML output instead of text')
        parser.add_argument(       '--exclude', action='store', dest='exclude', help='Exclude file patterns (space separated)')

        return parser.parse_args()


    def __init__(self):
        self.args = self.parse_command_line()


    def write_outfile(self, outfile, append, filenames):
        writer = None

        if self.args.html:
            writer = HTMLWriter(outfile, append)
        else:
            writer = TextWriter(outfile, append, self.args.delimiter)

        print('outfile: %s' % outfile)
        print('cwd: %s' % os.getcwd())
        for fname in filenames:
            # Avoid printing absolute pathnames
            if os.path.isabs(fname):
                fn_str = os.path.basename(fname)
            else:
                fn_str = fname

            writer.writeSection(fn_str)

            print('%s' % fname)

            # Some files may be broken. We first check whether we can
            # decode the file in utf-8 before writing line by line.
            # On error, we simply open with latin-1 encoding.
            enc = 'utf-8'
            try:
                with open(fname, 'rb') as infile:
                    for line in infile:
                        line.decode()
            except UnicodeDecodeError:
                enc = 'latin1'

            with open(fname, 'r', encoding=enc) as infile:
                for line in infile:
                    writer.write(line)


    def main(self):
        outfile = os.path.abspath(self.args.outfile)

        filenames = []
        cwd = os.getcwd()
        if self.args.traverse_dir:
            if not os.path.isdir(self.args.traverse_dir):
                print('Invalid argument: %s is not a directory' % self.args.traverse_dir)
                sys.exit(-1)

            os.chdir(self.args.traverse_dir)
            for dpath,dnames,fnames in os.walk(top='.', onerror=None, followlinks=False):
                for fname in sorted(fnames):

                    # Normalize to forward slashes and strip leading ./ or .\
                    dpath_norm = dpath.replace('\\', '/')
                    if dpath_norm.startswith('./'):
                        dpath_norm = dpath_norm[2:] # strip ./
                    if dpath_norm and dpath_norm != '.':
                        fname = '/'.join([dpath_norm, fname])
                    # Skip if any pattern that is defined in --exclude matches
                    # the filename, e.g., *.h or *.c
                    if self.args.exclude:
                        if any([fnmatch.fnmatch(fname, pattern) for pattern in self.args.exclude.split()]):
                            print('  skipped %s' % fname)
                            continue
                    filenames.append(fname)

        else:
            filenames = map(glob.glob, (x for x in self.args.infiles))
            filenames = [item for items in filenames for item in items]

        self.write_outfile(outfile, self.args.append, filenames)
        os.chdir(cwd)


def run():
    try:
        concat_files = ConcatFilesMain()
        concat_files.main()
    except Exception as e:
        import traceback
        print('failed', e)
        print('Exception stack', traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    run()

