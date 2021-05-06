from intake.source import base
from pyarrow.flight import BasicAuth, ClientAuthHandler
from pyarrow import flight

from . import __version__


class HttpDremioClientAuthHandler(ClientAuthHandler):
    def __init__(self, username, password):
        super(ClientAuthHandler, self).__init__()
        self.basic_auth = BasicAuth(username, password)
        self.token = None

    def authenticate(self, outgoing, incoming):
        auth = self.basic_auth.serialize()
        outgoing.write(auth)
        self.token = incoming.read()

    def get_token(self):
        return self.token


class DremioSource(base.DataSource):
    """
    One-shot SQL to dataframe reader (no partitioning)
    Caches entire dataframe in memory.
    Parameters
    ----------
    uri: str or None
        Connection string in the form username:password@hostname:port
    sql_expr: str
        Query expression to pass to the DB backend
    """
    name = 'dremio'
    version = __version__
    container = 'dataframe'
    partition_access = True

    def __init__(self, uri, sql_expr, metadata={}):
        self._init_args = {
            'uri': uri,
            'sql_expr': sql_expr,
            'metadata': metadata,
        }

        self._uri = uri
        if '://' in uri:
            self._protocol, uri = uri.split('://')
        else:
            self._protocol = 'grpc+tcp'
        userinfo, hostname = uri.split('@')
        self._hostname = hostname
        self._user, self._password = userinfo.split(':')
        self._sql_expr = sql_expr
        self._dataframe = None

        super(DremioSource, self).__init__(metadata=metadata)

    def _load(self):
        client = flight.FlightClient(f'{self._protocol}://{self._hostname}')
        client.authenticate(HttpDremioClientAuthHandler(self._user, self._password))
        info = client.get_flight_info(flight.FlightDescriptor.for_command(self._sql_expr))
        reader = client.do_get(info.endpoints[0].ticket)
        self._dataframe = reader.read_pandas()

    def _get_schema(self):
        if self._dataframe is None:
            # TODO: could do read_sql with chunksize to get likely schema from
            # first few records, rather than loading the whole thing
            self._load()
        return base.Schema(datashape=None,
                           dtype=self._dataframe.dtypes,
                           shape=self._dataframe.shape,
                           npartitions=1,
                           extra_metadata={})

    def _get_partition(self, _):
        if self._dataframe is None:
            self._load_metadata()
        return self._dataframe

    def read(self):
        return self._get_partition(None)

    def _close(self):
        self._dataframe = None
