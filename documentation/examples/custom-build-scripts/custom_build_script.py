#!/usr/bin/env python

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import os
from pathlib import Path

outfile = Path(os.environ['RBB_BUILD_PATH']) / 'my_component'


print(f'Hello world: {os.environ["RBB_BUILD_PATH"]}')
with open(outfile, 'w') as fd:
    print(f'Hello world: {os.environ["RBB_BUILD_PATH"]}', file=fd)



