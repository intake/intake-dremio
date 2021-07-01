from intake.catalog.base import Catalog
from intake.catalog.local import LocalCatalogEntry
from pyarrow import flight

from . import __version__
from .intake_dremio import DremioSource, DremioClientAuthMiddlewareFactory, HttpDremioClientAuthHandler


class DremioCatalog(Catalog):
    
    name = 'dremio_cat'

    __version__ = __version__
    
    _sql_expr = 'select * from INFORMATION_SCHEMA."TABLES"'

    def __init__(self, uri, tls=False, cert=None, **kwargs):
        self._tls = tls
        self._certs = cert
        self._uri = uri
        if '://' in uri:
            self._protocol, uri = uri.split('://')
            if tls and 'tls' not in self._protocol:
                raise ValueError(f"TLS was enabled but protocol {self._protocol}"
                                 "does not supported encrypted connection.")
        else:
            self._protocol = 'grpc+tls' if tls else 'grpc+tcp'
        userinfo, hostname = uri.split('@')
        self._hostname = hostname
        self._user, self._password = userinfo.split(':')
        super(DremioCatalog, self).__init__(**kwargs)

    def _load(self):
        client_auth_middleware = DremioClientAuthMiddlewareFactory()
        connection_args = {'middleware': [client_auth_middleware]}
        if self._tls:
            connection_args["tls_root_certs"] = self._certs
        client = flight.FlightClient(
            f'{self._protocol}://{self._hostname}',
            **connection_args
        )
        try:
            bearer_token = client.authenticate_basic_token(self._user, self._password)
            headers = [bearer_token]
        except Exception as e:
            if self._tls:
                raise e
            client.authenticate(HttpDremioClientAuthHandler(self._user, self._password))
            headers = []
        flight_desc = flight.FlightDescriptor.for_command(self._sql_expr)
        options = flight.FlightCallOptions(headers=headers)
        flight_info = client.get_flight_info(flight_desc, options)
        reader = client.do_get(flight_info.endpoints[0].ticket, options)
        self._dataframe = reader.read_pandas()
        for _, row in self._dataframe.iterrows():
            self._create_entry(row)

    def _create_entry(self, row):
        name = f'{row.TABLE_SCHEMA}."{row.TABLE_NAME}"'
        description = f'Dremio {row.TABLE_TYPE} {name} from {self._hostname}'
        args = {
            'uri': self._uri,
            'sql_expr': f'select * from {name}'
        }
        e = LocalCatalogEntry(name, description, 'dremio', True,
                              args, {}, {}, {}, "", getenv=False,
                              getshell=False)
        e._plugin = [DremioSource]
        self._entries[name] = e
