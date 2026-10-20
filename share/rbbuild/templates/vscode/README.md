<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

To add rbbuild tasks in Visual Studio, the following has to be done:

1. rbbuild -g . will create a symlink from this directory to the project's
   .vscode/tasks.json

2. Add "Task Runner" Extension in Visual Studio. With this extension, a widget
   panel will appear in the left ribbon bar where common rbbuild commands will
   be clickable.

