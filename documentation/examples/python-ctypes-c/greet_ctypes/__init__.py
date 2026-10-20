# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import ctypes

from pathlib import Path


def _load_library() -> ctypes.CDLL:
    for path in Path(__file__).parent.glob('*greet.*'):
        if path.suffix in ('.so', '.dll', '.dylib'):
            return ctypes.CDLL(str(path))
    raise ImportError('Shared library greet not found. Was the wheel built with rbbuild -sbp?')


_lib = _load_library()
_lib.greet_add.argtypes = [ctypes.c_int, ctypes.c_int]
_lib.greet_add.restype = ctypes.c_int
_lib.greet_hello.restype = ctypes.c_char_p


def add(a: int, b: int) -> int:
    return _lib.greet_add(a, b)


def hello() -> str:
    return _lib.greet_hello().decode()
