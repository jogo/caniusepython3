from __future__ import print_function
from __future__ import unicode_literals

from caniusepython3 import pypi

import distlib.metadata
import packaging.requirements
import packaging.utils

import io
import logging
import re

def get_pinned_version(req):
    for specifier in req.specifier:
        if specifier.operator == u'==':
            return specifier.version
    return None

def projects_from_requirements(requirements):
    """Extract the project dependencies from a Requirements specification."""
    log = logging.getLogger('ciu')
    valid_reqs = []
    for requirements_path in requirements:
        with io.open(requirements_path) as file:
            requirements_text = file.read()
        # Drop line continuations.
        requirements_text = re.sub(r"\\s*", "", requirements_text)
        # Drop comments.
        requirements_text = re.sub(r"#.*", "", requirements_text)
        reqs = []
        for line in requirements_text.splitlines():
            if not line:
                continue
            try:
                reqs.append(packaging.requirements.Requirement(line))
            except packaging.requirements.InvalidRequirement:
                log.warning('Skipping {0!r}: could not parse requirement'.format(line))
        for req in reqs:
            if not req.name:
                log.warning('A requirement lacks a name '
                            '(e.g. no `#egg` on a `file:` path)')
            elif req.url:
                log.warning(
                    'Skipping {0}: URL-specified projects unsupported'.format(req.name))
            else:
                pinned_version = get_pinned_version(req)
                valid_reqs.append((req.name, pinned_version))
    results = set()
    for req, pinned_version in valid_reqs:
        results.add((packaging.utils.canonicalize_name(req), pinned_version))
    return frozenset(results)


def projects_from_metadata(metadata):
    """Extract the project dependencies from a metadata spec."""
    projects = []
    for data in metadata:
        meta = distlib.metadata.Metadata(fileobj=io.StringIO(data))
        projects.extend(pypi.just_name(project) for project in meta.run_requires)
    return frozenset(map(packaging.utils.canonicalize_name, projects))
