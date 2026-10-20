# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import sys
import os
import platform
from enum import IntEnum

class Singleton(type):
    _instances = {}

    # Override the internal class constructor to return a single object within
    # _instances if it exists. Otherwise, the __new__ class constructor from
    # the inheriting class (super) is called and the object is created.
    def __new__(class_, *args, **kwargs):
        if class_ not in class_._instances:
            class_._instances[class_] = super(Singleton, class_).__new__(class_, *args, **kwargs)
        return class_._instances[class_]


class LogLevel(IntEnum):
    ERROR   = 1
    WARNING = 2
    INFO    = 3
    DEBUG   = 4


class ColorSchemeNone:
    red    = ''
    green  = ''
    yellow = ''
    blue   = ''
    cyan   = ''
    normal = ''
    magenta = ''
    bwhite = ''
    eraseline = ''
    end    = ''


class ColorSchemeWhiteOnBlack(ColorSchemeNone):
    red       = '\033[91m'
    green     = '\033[92m'
    yellow    = '\033[93m'
    blue      = '\033[94m'
    magenta   = '\033[95m'
    cyan      = '\033[96m'
    normal    = '\033[90m'
    bwhite    = '\033[1;37m'
    eraseline = '\033[K'
    end       = '\033[0m'


class ColorSchemeBlackOnWhite(ColorSchemeNone):
    red       = '\033[31m'
    green     = '\033[32m'
    yellow    = '\033[33m'
    blue      = '\033[34m'
    magenta   = '\033[35m'
    cyan      = '\033[36m'
    normal    = '\033[37m'
    bwhite    = '\033[1;37m'
    eraseline = '\033[K'
    end       = '\033[0m'


class ColorTerm(metaclass=Singleton):

    def __init__(self):
        self.log_file      = sys.stderr
        self.out_file      = sys.stdout
        self._log_level    = LogLevel.INFO
        self.line_sep      = '-----------------------------------------------------------'
        self._init_color_codes()
        self._last_msg     = ''

        # Optional per-channel stream overrides.
        # This allows the GUI to mirror one specific channel without
        # affecting plain-CLI behavior.
        # By default, the shared log_file/out_file streams" are used
        self._streams = {
            'error':   None,
            'warning': None,
            'info':    None,
            'debug':   None,
            'stdout':  None,
        }


    # Builds a property pair for one channel: the getter returns the
    # per-channel override if one was assigned, otherwise `default_attr`
    # (the shared log_file/out_file stream); the setter assigns the override.
    def _channel_stream(channel: str, default_attr: str):
        def getter(self):
            return self._streams[channel] or getattr(self, default_attr)

        def setter(self, value):
            self._streams[channel] = value

        return property(getter, setter)

    stream_error   = _channel_stream('error',   'log_file')
    stream_warning = _channel_stream('warning', 'log_file')
    stream_info    = _channel_stream('info',    'log_file')
    stream_debug   = _channel_stream('debug',   'log_file')
    stream_stdout  = _channel_stream('stdout',  'out_file')

    del _channel_stream


    def _init_color_codes(self):
        self.color = ColorSchemeNone

        # If the program is redirected to a file, the expression below will
        # become False.
        if 'RBB_COLOR_ALWAYS_WRITE' in os.environ.keys() or self.log_file.isatty():
            if sys.platform == 'win32':
                # ANSI codes do not work on Windows 7.
                if int(platform.release()) >= 10:
                    try:
                        # Console coloring needs to be enabled. 
                        # Code copied from: https://bugs.python.org/issue29059
                        from ctypes import windll, c_int, byref
                        stdout_handle = windll.kernel32.GetStdHandle(c_int(-11))
                        mode = c_int(0)
                        windll.kernel32.GetConsoleMode(c_int(stdout_handle), byref(mode))
                        mode = c_int(mode.value | 4)
                        windll.kernel32.SetConsoleMode(c_int(stdout_handle), mode)
                    except Exception:
                        return
                else:
                    return

            self.color = ColorSchemeWhiteOnBlack
            if 'RBB_COLOR_SCHEME' in os.environ.keys():
                if os.environ['RBB_COLOR_SCHEME'] == 'BlackOnWhite':
                    self.color = ColorSchemeBlackOnWhite
                elif os.environ['RBB_COLOR_SCHEME'] == 'WhiteOnBlack':
                    self.color = ColorSchemeWhiteOnBlack
                else:
                    self.color = ColorSchemeNone


    @property
    def log_level(self) -> LogLevel:
        return self._log_level


    @log_level.setter
    def log_level(self, value: str):
        if not value:
            return

        if value.upper() not in LogLevel.__members__:
            raise SyntaxError(f'Invalid log level "{value}": accepted values: {", ".join(LogLevel.__members__.keys())}')
        level = LogLevel[value.upper()]
        self._log_level = level


    # --- Terminal colors ---

    def black(self, msg):
        return self.color.normal + msg + self.color.end


    def red(self, msg):
        return self.color.red + msg + self.color.end


    def green(self, msg):
        return self.color.green + msg + self.color.end


    def yellow(self, msg):
        return self.color.yellow + msg + self.color.end


    def blue(self, msg):
        return self.color.blue + msg + self.color.end


    def magenta(self, msg):
        return self.color.magenta + msg + self.color.end


    def cyan(self, msg):
        return self.color.cyan + msg + self.color.end


    def bright_white(self, msg):
        return self.color.bwhite + msg + self.color.end


    def erase_until_line_end(self):
        return self.color.eraseline


    ########################################################################

    def error(self, label_msg, *args, **kwargs):
        if self.log_level >= LogLevel.ERROR:
            self._last_msg = args
            print('[%s]\t' % self.red(label_msg), *args, flush=True, file=self.stream_error, **kwargs)


    def warning(self, label_msg, *args, **kwargs):
        if self.log_level >= LogLevel.WARNING:
            self._last_msg = args
            print('[%s]\t' % self.yellow(label_msg), *args, flush=True, file=self.stream_warning, **kwargs)


    def info(self, *args, **kwargs):
        if self.log_level >= LogLevel.INFO:
            self._last_msg = args
            print(*args, file=self.stream_info, **kwargs)


    def debug(self, label_msg, *args, **kwargs):
        if self.log_level >= LogLevel.DEBUG:
            self._last_msg = args
            print('[%s]\t' % self.bright_white(label_msg), *args, flush=True, file=self.stream_debug, **kwargs)


    def stdout(self, *args, **kwargs):
        self._last_msg = args
        print(*args, file=self.stream_stdout, flush=True, **kwargs)


    def print_line(self):
        print(term.line_sep, flush=True, file=self.log_file)


    def redraw_last_line(self, *extra_msg, **kwargs):
        if 'sep' not in kwargs:
            kwargs['sep'] = ''
        print( f'\r{" ".join(self._last_msg)}',
               *extra_msg,
               term.erase_until_line_end(),
               flush=True,
               file=self.log_file,
               **kwargs )


    # Default progress_cb implementation for chunked downloads/uploads
    # (see RESTHelper.download_file/upload_file). Redraws the current
    # terminal line with the bytes/megabytes transferred so far.
    def print_download_progress(self, ncur, total_len):
        if total_len > 1024 * 1024 and 'RBB_DISABLE_FETCH_PROGRESS' not in os.environ:
            # Introduce threshold for displaying megabytes instead of bytes
            if total_len > (5 * 1024 * 1024):
                current = int(ncur / (1024*1024))
                total   = int(total_len / (1024*1024))
                unit    = 'MB'
            else:
                current = ncur
                total   = total_len
                unit    = 'bytes'

            self.redraw_last_line(f' {current} / {total} {unit}', end='')


term = ColorTerm()

