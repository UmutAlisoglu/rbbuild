<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# Instructions for AI coding assistants

These rules apply to all code contributions. See [CONTRIBUTING.md](CONTRIBUTING.md)
for the complete contribution guide.

## Code style

- Follow PEP 8 as far as possible. Keep lines to 80 characters or fewer where
  reasonable.
- Use `#` comments. Do not use docstrings (`"""..."""`).
- Put a comment above the `def` or `class` it describes, not inside the body.
- Comment only what the code cannot show on its own (workarounds, ticket
  references, platform quirks). Do not restate what the code does.
- Use two blank lines between methods.
- Do not include style changes to existing code in unrelated changes.
- Do not leave dead or commented-out code behind.

## Testing

- rbbuild default venv should be used as documented under `~/.cache/rbbuild`.
- Run the full test suite: `pytest` without a path argument, or both
  `test/unit` and `test/integration`. `testpaths` in `pyproject.toml` covers
  both directories, and a change is only verified if both pass.
  `rbbuild -T` is preferred over calling `pytest` directly because it
  also runs coverage tests.
- Run `rbbuild --sca` to check the changed code. Do not call `ruff check`
  directly: the quality configuration is only applied by `rbbuild --sca`.
- Add or update tests for every functional change.

## Dependencies and files

- Do not add third-party source code to the repository. Declare a dependency in
  `pyproject.toml` instead, and check that its license is compatible.
- Add only source and other text files. Avoid binary files.
