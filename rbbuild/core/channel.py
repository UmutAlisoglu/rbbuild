# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from fnmatch import fnmatch
from git import Repo, InvalidGitRepositoryError
from typing import List


class Channel:
    def __init__(
        self,
        name: str,
        default_channel: str,
        channels_config: dict,
        source_path: str,
    ):
        # Usually, the channel name is defined when reading from manifests,
        # or when it is explicitly defined as package prefix in deps.json.
        #
        # The current git branch is matched against "branch_pattern"
        # in any channel definition. Otherwise, "default_channel" is chosen.
        if not name:
            git_branch = None
            try:
                repo = Repo(source_path)
                if repo.head.is_detached is False:
                    git_branch = repo.head.ref.name
            except InvalidGitRepositoryError:
                pass
            except Exception:
                raise

            if git_branch:
                for chname, cfg in channels_config.items():
                    for pattern in cfg.get('branch_pattern', []):
                        if fnmatch(git_branch, pattern):
                            name = chname
                            break
                    if name:
                        break

            if not name:
                name = default_channel

        cfg = channels_config.get(name)
        if not cfg:
            raise LookupError(f'Channel {name} not found')

        self.name: str                 = name
        self.type: str                 = cfg['type']
        self.remote_service: str       = cfg['remote_service']
        self.repository: str           = cfg['repository']
        self.root_path: str            = cfg.get('root_path', '')
        self.redirect_repos: List[str] = cfg.get('redirect_repos', [])
        self.project: str              = cfg.get('project') # cfg.get('project', '~' + os.environ.get('USER', ''))
        # permission level, one of: read, upload, overwrite, delete --> enum
        self.permissions: str          = cfg.get('permissions', 'delete')
        self.publish: bool             = cfg.get('publish', True)
        self.development: bool         = cfg.get('development', False)   # will append .devN to the version if True


    def __repr__(self) -> str:
        return f'Channel(name={self.name}, type={self.type}, repository={self.repository}, root_path={self.root_path}, redirect_repos={self.redirect_repos!s}, project={self.project}, permissions={self.permissions}, publish={self.publish}, development={self.development})'


    def __str__(self) -> str:
        return self.name

