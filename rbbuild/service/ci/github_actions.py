#!/usr/bin/env python

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import os
from typing import Optional

from .manager import CIService


class GitHubActions(CIService):
    def job_url(self) -> Optional[str]:
        server = os.environ.get('GITHUB_SERVER_URL')
        repo   = os.environ.get('GITHUB_REPOSITORY')
        run_id = os.environ.get('GITHUB_RUN_ID')
        if server and repo and run_id:
            return f'{server}/{repo}/actions/runs/{run_id}'
        return None
