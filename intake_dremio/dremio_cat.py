from intake.catalog.base import Catalog
from intake.catalog.local import LocalCatalogEntry
from pyarrow import flight

from . import __version__
from .intake_dremio import DremioSource, HttpDremioClientAuthHandler


class DremioCatalog(Catalog):
    
    name = 'dremio_cat'
    __version__ = __version__
    
    _sql_expr = 'select * from INFORMATION_SCHEMA."TABLES"'

    def __init__(self, uri, **kwargs):
        self._uri = uri
        if '://' in uri:
            self._protocol, uri = uri.split('://')
        else:
            self._protocol = 'grpc+tcp'
        userinfo, hostname = uri.split('@')
        self._hostname = hostname
        self._user, self._password = userinfo.split(':')
        super(DremioCatalog, self).__init__(**kwargs)

    def _load(self):
        client = flight.FlightClient(f'{self._protocol}://{self._hostname}')
        client.authenticate(HttpDremioClientAuthHandler(self._user, self._password))
        info = client.get_flight_info(flight.FlightDescriptor.for_command(self._sql_expr))
        reader = client.do_get(info.endpoints[0].ticket)
        self._dataframe = reader.read_pandas()
        for _, row in self._dataframe.iterrows():
            self._create_entry(row)

    def _create_entry(self, row):
        name = f'{row.TABLE_SCHEMA}."{row.TABLE_NAME}"'
        description = f'Dremio table {name} from {self._hostname}'
        args = {
            'uri': self._uri,
            'sql_expr': f'select * from {name}'
        }
        e = LocalCatalogEntry(name, description, 'dremio', True,
                              args, {}, {}, {}, "", getenv=False,
                              getshell=False)
        e._plugin = [DremioSource]
        self._entries[name] = e
