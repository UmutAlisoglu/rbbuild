# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

class License:
    def __init__(
        self,
        *,
        expression:      str  = None,
        id:              str  = None,
        name:            str  = None,
        acknowledgement: str  = None,
        text:            dict = None,
        url:             str  = None,
        properties:      dict = None,
        licensing:       dict = None,
    ):
        self.expression      = expression
        self.id              = id
        self.name            = name
        self.acknowledgement = acknowledgement
        self.text            = text
        self.url             = url
        self.properties      = properties
        self.licensing       = licensing
        if expression is not None:
            if id or name or text or url or properties or licensing:
                raise SyntaxError(f'License: "expression" mode: only "acknowledgement" is allowed alongside "expression": {expression}')
        else:
            if properties is not None and type(properties) is not dict:
                raise SyntaxError(f'License.properties: Invalid type {type(properties)}. Expected dictionary value: {properties}')
            if licensing is not None and type(licensing) is not dict:
                raise SyntaxError(f'License.licensing: Invalid type {type(licensing)}. Expected dictionary value: {licensing}')
            if not (bool(id) ^ bool(name)):
                raise SyntaxError('License: Either "id" or "name" must be defined, not both')


    def __eq__(self, other) -> bool:
        if not isinstance(other, License):
            return NotImplemented
        return (self.expression == other.expression and
                self.id == other.id and
                self.name == other.name and
                self.acknowledgement == other.acknowledgement and
                self.url == other.url)

    def __hash__(self) -> int:
        return hash((self.expression, self.id, self.name, self.acknowledgement, self.url))


    def __str__(self) -> str:
        if self.expression:
            return self.expression
        if self.id:
            return self.id
        if self.name:
            return self.name
        # last resort
        if self.text:
            return self.text


    def to_dict(self) -> dict:
        if self.expression is not None:
            d = {'expression': self.expression}
            if self.acknowledgement is not None:
                d['acknowledgement'] = self.acknowledgement
            return d
        # Build the license dict from all set fields
        d = {}
        for key in ['id', 'name', 'acknowledgement', 'text', 'url', 'properties', 'licensing']:
            value = getattr(self, key)
            if value is not None:
                d[key] = value
        return {'license': d}


    # Coerce a raw licenses value into list[License] | None.
    # Accepts: None, a bare SPDX expression string, or a list of str/dict/License objects.
    # A dict with a 'license' key uses CycloneDX wrapping; without is treated as keyword args.
    @classmethod
    def coerce(cls, value) -> list:
        if not value:
            return None

        if type(value) is str:
            return [cls(expression=value)]

        if type(value) is not list:
            raise SyntaxError(f'License.coerce: Invalid type "{type(value)}". Expected str or list')

        licenses = []
        expression_mode = False
        for item in value:
            if type(item) is str:
                item = cls(expression=item)
                expression_mode = True

            elif type(item) is dict:
                try:
                    if 'license' in item:
                        item = cls(**item['license'])
                    else:
                        item = cls(**item)
                except TypeError as e:
                    raise SyntaxError(f'License.coerce: {e}') from e

            elif not isinstance(item, cls):
                raise SyntaxError(f'License.coerce: Invalid type "{type(item)}". Expected str, dict, or License: {str(item)}')

            if item.expression:
                expression_mode = True

            licenses.append(item)

        if expression_mode and len(licenses) != 1:
            raise SyntaxError('License.coerce: Only one item must be declared with "expression" licenses')

        return licenses

