# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from typing import Dict


class ComponentSpecifier:
    def __init__( self,
                  components: Dict[str, str],
                  suffixes: Dict[str, str],
                  build_only: bool,
                  traverse: bool ):

        self._items = {}   # {(<component>, <suffix>): {<key>: <value>}}

        if components and suffixes:
            keys = [(component, suffix) for component in components
                                        for suffix in suffixes ]
        elif components:
            keys = [(component, None) for component in components]
        elif suffixes:
            keys = [(None, suffix) for suffix in suffixes]
        else:
            keys = [(None, None)]

        for key in keys:
            attrs = {
                'build_only': build_only,
                'traverse': traverse,
            }
            self._items[key] = attrs


    @property
    def items(self) -> Dict[str, Dict[str, object]]:
        return self._items


    # Check restrictions for component
    def check(self, component: str, suffix: str, attr: str):
        for key in [ (component, suffix),
                     (component, None),
                     (None, suffix),
                     (None, None) ]:
            if key in self.items:
                if attr is not None:
                    return self.items[key].get(attr)
                else:
                    return True

        return None
