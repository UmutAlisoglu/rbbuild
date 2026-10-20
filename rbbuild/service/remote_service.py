# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from abc import ABCMeta
from enum import Enum
from typing import Dict, Tuple

from rbbuild.librbb.term import term


class AuthMethod(Enum):
    NONE = 0
    BASIC = 1
    BEARER_TOKEN = 2


    # Reads 'auth-method' of a [profile.services.<name>] table; none if undefined.
    @classmethod
    def from_config(cls, service_config: dict, service_name: str) -> 'AuthMethod':
        value = service_config.get('auth-method', 'none')
        try:
            return cls[str(value).upper().replace('-', '_')]
        except KeyError:
            valid = ', '.join(m.name.lower().replace('_', '-') for m in cls)
            raise SyntaxError(
                f'[profile.services.{service_name}]: invalid auth-method "{value}" (valid: {valid})'
            ) from None


# In our context, a RemoteService is always a REST service.
# This abstract class defines the interfaces that must be implemented
# by a remote service
class RemoteService(metaclass=ABCMeta):
    def __init__(
        self,
        url: str,
        auth_method: AuthMethod,
        user: str,
        credentials: str,
    ):
        self.url: str = url
        self.headers: Dict[str, str] = {}
        self.auth: Tuple[str, str] = None

        auth_err_msg = f'{term.bright_white(self.__class__.__name__)}: missing auth credentials: '
        if url:
            auth_err_msg += term.cyan(url)

        if auth_method == AuthMethod.BEARER_TOKEN:
            if user:
                self.auth = (user, credentials)
                if not user and not credentials:
                    raise RuntimeError(auth_err_msg)
            else:
                self.headers = {'Authorization' : f'Bearer {credentials}'}
                if not credentials:
                    raise RuntimeError(auth_err_msg)
        elif auth_method == AuthMethod.BASIC:
            self.auth = (user, credentials)
            if not user and not credentials:
                raise RuntimeError(auth_err_msg)
        elif auth_method == AuthMethod.NONE:
            pass
        else:
            raise TypeError(f'Invalid authentication method {auth_method}')

