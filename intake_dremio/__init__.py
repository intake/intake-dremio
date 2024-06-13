import intake # noqa

from .intake_dremio import DremioSource # noqa
from .dremio_cat import DremioCatalog # noqa

from . import _version
__version__ = _version.get_versions()['version']
