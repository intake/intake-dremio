from intake.source import base
from pyarrow import flight

from . import __version__


class HttpDremioClientAuthHandler(flight.ClientAuthHandler):

    def __init__(self, username, password):
        super(flight.ClientAuthHandler, self).__init__()
        self.basic_auth = flight.BasicAuth(username, password)
        self.token = None

    def authenticate(self, outgoing, incoming):
        auth = self.basic_auth.serialize()
        outgoing.write(auth)
        self.token = incoming.read()

    def get_token(self):
        return self.token


class DremioClientAuthMiddleware(flight.ClientMiddleware):
    """
    A ClientMiddleware that extracts the bearer token from
    the authorization header returned by the Dremio
    Flight Server Endpoint.

    Parameters
    ----------
    factory : ClientHeaderAuthMiddlewareFactory
        The factory to set call credentials if an
        authorization header with bearer token is
        returned by the Dremio server.
    """

    def __init__(self, factory):
        self.factory = factory

    def received_headers(self, headers):
        auth_header_key = 'authorization'
        authorization_header = []
        for key in headers:
          if key.lower() == auth_header_key:
            authorization_header = headers.get(auth_header_key)
        self.factory.set_call_credential([
            b'authorization', authorization_header[0].encode("utf-8")])


class DremioClientAuthMiddlewareFactory(flight.ClientMiddlewareFactory):
    """A factory that creates DremioClientAuthMiddleware(s)."""

    def __init__(self):
        self.call_credential = []

    def start_call(self, info):
        return DremioClientAuthMiddleware(self)

    def set_call_credential(self, call_credential):
        self.call_credential = call_credential


def process_uri(uri, tls=False, user=None, password=None):
    """
    Extracts hostname, protocol, user and passworrd from URI

    Parameters
    ----------
    uri: str or None
        Connection string in the form username:password@hostname:port
    tls: boolean
        Whether TLS is enabled
    username: str or None
        Username if not supplied as part of the URI
    password: str or None
        Password if not supplied as part of the URI
    """
    if '://' in uri:
        protocol, uri = uri.split('://')
    else:
        protocol = 'grpc+tls' if tls else 'grpc+tcp'
    if '@' in uri:
        if user or password:
            raise ValueError(
                "Dremio URI must not include username and password "
                "if they were supplied explicitly."
            )
        userinfo, hostname = uri.split('@')
        user, password = userinfo.split(':')
    elif not (user and password):
        raise ValueError(
            "Dremio URI must include username and password "
            "or they must be provided explicitly."
        )
    else:
        hostname = uri
    return protocol, hostname, user, password


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
    username: str or None
        Username if not supplied as part of the URI
    password: str or None
        Password if not supplied as part of the URI
    tls: boolean
        Enable encrypted connection
    cert: str
        Path to trusted certificates for encrypted connection
    connect_timeout: float or None
        A timeout for the auth connect call, in seconds. None means
        that the timeout defaults to an implementation-specific value.
    request_timeout: float or None
        A timeout for the request call, in seconds. None means that
        the timeout defaults to an implementation-specific value.
    """
    name = 'dremio'
    version = __version__
    container = 'dataframe'
    partition_access = True

    def __init__(self, uri, sql_expr, username=None, password=None,
                 tls=False, cert=None, metadata={}, connect_timeout=None,
                 request_timeout=None):
        self._init_args = {
            'uri': uri,
            'sql_expr': sql_expr,
            'username': username,
            'password': password,
            'tls': tls,
            'cert': cert,
            'metadata': metadata,
            'connect_timeout': connect_timeout,
            'request_timeout': request_timeout
        }
        self._uri = uri
        self._tls = tls
        self._connect_timeout = connect_timeout
        self._request_timeout = request_timeout
        self._protocol, self._hostname, self._user, self._password = process_uri(
            uri, tls=tls, user=username, password=password
        )
        if tls and 'tls' not in self._protocol:
            raise ValueError(f"TLS was enabled but protocol {self._protocol} "
                             "does not supported encrypted connection.")
        if cert is not None and tls:
            with open(cert, "rb") as root_certs:
                self._certs = root_certs.read()
        elif tls:
            raise ValueError('Trusted certificates must be provided to establish a TLS connection')
        else:
            self._certs = None
        self._sql_expr = sql_expr
        self._dataframe = None
        super(DremioSource, self).__init__(metadata=metadata)

    def _get_reader(self):
        client_auth_middleware = DremioClientAuthMiddlewareFactory()
        connection_args = {'middleware': [client_auth_middleware]}
        if self._tls:
            connection_args["tls_root_certs"] = self._certs
        client = flight.FlightClient(
            f'{self._protocol}://{self._hostname}',
            **connection_args
        )
        auth_options = flight.FlightCallOptions(timeout=self._connect_timeout)
        try:
            bearer_token = client.authenticate_basic_token(self._user, self._password)
            headers = [bearer_token]
        except Exception as e:
            if self._tls:
                raise e
            handler = HttpDremioClientAuthHandler(self._user, self._password)
            client.authenticate(handler, options=auth_options)
            headers = []
        flight_desc = flight.FlightDescriptor.for_command(self._sql_expr)
        options = flight.FlightCallOptions(headers=headers, timeout=self._request_timeout)
        flight_info = client.get_flight_info(flight_desc, options)
        reader = client.do_get(flight_info.endpoints[0].ticket, options)
        return reader

    def _load(self):
        self._dataframe = self._get_reader().read_pandas()

    def arrow_schema(self):
        return self._get_reader().schema

    def _get_schema(self):
        if self._dataframe is None:
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
