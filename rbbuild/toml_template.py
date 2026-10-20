# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import re

from tomlkit.items import Comment, Whitespace


_HEADER_RE = re.compile(r'^#\s*\[([^\]]+)\]\s*$')


# share/rbbuild/templates/rbbuild.toml.in is entirely commented out (every
# section is a placeholder example, e.g. "# [project]" / "# name = ...").
# tomlkit parses that as plain top-level Comment items, not a real table,
# so simply assigning doc['project'] = ... once the user enters a value
# would append a brand new table at the end while leaving the commented
# example sitting above it untouched. Call this first to drop that
# example block; a no-op if section_name's header isn't found (e.g.
# base_text isn't the blank template, or the block was already removed by
# an earlier edit in the same document).
def strip_commented_placeholder(doc, section_name: str) -> None:
    body = doc.body

    start = None
    for index, (key, item) in enumerate(body):
        if key is None and isinstance(item, Comment):
            match = _HEADER_RE.match(str(item).strip())
            if match and match.group(1) == section_name:
                start = index
                break

    if start is None:
        return

    if start > 0 and body[start - 1][0] is None and isinstance(body[start - 1][1], Whitespace):
        start -= 1

    end = start
    while end + 1 < len(body):
        key, item = body[end + 1]
        if key is None and isinstance(item, Comment):
            end += 1
        else:
            break

    del body[start:end + 1]
