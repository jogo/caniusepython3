# Copyright 2014 Google Inc. All rights reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import unicode_literals

import packaging.utils
import requests

import concurrent.futures
import datetime
import json
import logging
import multiprocessing
import pkgutil
import re

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache



try:
    CPU_COUNT = max(2, multiprocessing.cpu_count())
except NotImplementedError:  #pragma: no cover
    CPU_COUNT = 2

PROJECT_NAME = re.compile(r'[\w.-]+')

SUPPORTS_PY3 = 1
UPGRADE_FOR_PY3 = 2
NO_PY3_SUPPORT = 3
INTERNAL_UNKNOWN = 4


def just_name(supposed_name):
    """Strip off any versioning or restrictions metadata from a project name."""
    return PROJECT_NAME.match(supposed_name).group(0).lower()


def manual_overrides():
    """Read the overrides file.

    Read the overrides from cache, if available. Otherwise, an attempt is made
    to read the file as it currently stands on GitHub, and then only if that
    fails is the included file used. The result is cached for one day.
    """
    return _manual_overrides(datetime.date.today())


@lru_cache(maxsize=1)
def _manual_overrides(_cache_date=None):
    """Read the overrides file.

    An attempt is made to read the file as it currently stands on GitHub, and
    then only if that fails is the included file used.
    """
    log = logging.getLogger('ciu')
    request = requests.get("https://raw.githubusercontent.com/brettcannon/"
                           "caniusepython3/master/caniusepython3/overrides.json")
    if request.status_code == 200:
        log.info("Overrides loaded from GitHub and cached")
        overrides = request.json()
    else:
        log.info("Overrides loaded from included package data and cached")
        raw_bytes = pkgutil.get_data(__name__, 'overrides.json')
        overrides = json.loads(raw_bytes.decode('utf-8'))
    return frozenset(map(packaging.utils.canonicalize_name, overrides.keys()))


class UnknownProjectException(Exception):
    pass

def _supports_py3(project_name, version=None):
    log = logging.getLogger("ciu")
    if version:
        request = requests.get("https://pypi.org/pypi/{}/{}/json".format(project_name, version))
    else:
        request = requests.get("https://pypi.org/pypi/{}/json".format(project_name))
    if request.status_code >= 400:
        log = logging.getLogger("ciu")
        log.warning("problem fetching {}, assuming internal ({})".format(
                        project_name, request.status_code))
        raise UnknownProjectException()
    response = request.json()
    return any(c.startswith("Programming Language :: Python :: 3")
               for c in response["info"]["classifiers"])


def supports_py3(project_name, version=None):
    """Check with PyPI if a project supports Python 3."""
    # TODO check current and latest version
    # 4 Possible states to return
    #   - currently supports python3
    #   - Newer version supports python 3
    #   - Doesn't support python3 at all
    #   - Internal lib, unknown

    log = logging.getLogger("ciu")
    log.info("Checking {} ...".format(project_name))
    try:
        if version:
            current = _supports_py3(project_name, version)
            latest = _supports_py3(project_name, None)
            if current is False and latest is True:
                return UPGRADE_FOR_PY3
            elif current is True:
                return SUPPORTS_PY3
            else:
                return NO_PY3_SUPPORT
        else:
            if _supports_py3(project_name, version):
                return SUPPORTS_PY3
            else:
                return NO_PY3_SUPPORT
    except UnknownProjectException:
        return INTERNAL_UNKNOWN
