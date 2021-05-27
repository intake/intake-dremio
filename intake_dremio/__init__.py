from ._version import get_versions

__version__ = get_versions()['version']

del get_versions

import intake # noqa

from .intake_dremio import DremioSource # noqa
from .dremio_cat import DremioCatalog # noqa
