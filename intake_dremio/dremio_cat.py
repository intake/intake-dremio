from intake.catalog.base import Catalog
from intake.catalog.local import LocalCatalogEntry

from . import __version__
from .intake_dremio import DremioSource


class DremioCatalog(Catalog):

    name = 'dremio_cat'

    __version__ = __version__

    _sql_expr = 'select * from INFORMATION_SCHEMA."TABLES"'

    def __init__(self, uri, username=None, password=None, tls=False, cert=None, **kwargs):
        self._source = DremioSource(
            uri, self._sql_expr, username=username, password=password,
            tls=tls, cert=cert
        )
        self._dataframe = None
        super(DremioCatalog, self).__init__(**kwargs)

    def _load(self):
        self._dataframe = self._source.read()
        for _, row in self._dataframe.iterrows():
            self._create_entry(row)

    def _create_entry(self, row):
        name = f'{row.TABLE_SCHEMA}."{row.TABLE_NAME}"'
        description = f'Dremio {row.TABLE_TYPE} {name} from {self._hostname}'
        args = dict(self._source._init_args, sql_expr=f'SELECT * FROM {name}')
        e = LocalCatalogEntry(name, description, 'dremio', True,
                              args, {}, {}, {}, "", getenv=False,
                              getshell=False)
        e._plugin = [DremioSource]
        self._entries[name] = e
