# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import re
from typing import Callable

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


# Assigned to one of term's per-channel stream slots (term.stream_error,
# term.stream_warning, ...). Forwards every write() unchanged to `fallback`,
# while assembling complete lines and handing them to on_message() tagged
# with this channel's exact severity.
class ChannelStream:

    def __init__(self, severity: str, fallback, on_message: Callable[[str, str], None]):
        self._severity = severity
        self._fallback = fallback
        self._on_message = on_message
        self._buffer = ''


    def write(self, text: str) -> int:
        n = self._fallback.write(text)
        self._buffer += text
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            # Skip blank lines and in-place progress redraws ('\r...').
            if line.strip() and not line.startswith('\r'):
                self._on_message(self._severity, _ANSI_RE.sub('', line))
        return n


    def flush(self):
        self._fallback.flush()


    def isatty(self) -> bool:
        return self._fallback.isatty()


# Channels whose messages are mirrored.
CHANNELS = ('error', 'warning', 'info', 'debug')


# Redirects each of term's channels through its own ChannelStream, so
# on_message(severity, text) is called for every complete line written on
# any channel. Safe to call more than once - a channel already wrapped is left alone.
def install(on_message: Callable[[str, str], None]):
    from rbbuild.librbb.term import term

    for channel in CHANNELS:
        attr = f'stream_{channel}'
        if isinstance(getattr(term, attr), ChannelStream):
            continue
        setattr(term, attr, ChannelStream(channel, getattr(term, attr), on_message))

