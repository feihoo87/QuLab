from typing import Optional

import zmq
import zmq.asyncio
import zmq.auth
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from zmq.auth.asyncio import AsyncioAuthenticator
from zmq.auth.thread import ThreadAuthenticator


class ReloadCertificatesHandler(FileSystemEventHandler):

    def __init__(self, zmq: 'ZMQContextManager'):
        self.zmq = zmq

    def on_modified(self, event):
        self.zmq.reload_certificates()


class ZMQContextManager:
    """
    A context manager for managing ZeroMQ sockets with asynchronous support.
    It handles the creation, connection, binding, and security configuration of
    the sockets and ensures proper resource cleanup.

    The context manager can be used as a synchronous context manager or an
    asynchronous context manager. When used as an asynchronous context manager,
    the socket is created with an asyncio context and can be used with the
    `await` keyword.

    The security settings for the socket can be configured using the secret key
    and public key parameters. If the secret key is provided, the socket is
    configured to use ZeroMQ curve encryption. The public key of the server can
    also be provided for client sockets to connect to a server with curve
    encryption. You can also provide the paths to the secret key and public key
    files, and the public key of the server to load the keys from files. The
    keys can be reloaded automatically when the files are modified by setting
    the `public_keys_location` parameter.

    To generate a secret key and public key pair, you can use the following
    commands:
    
        ```bash
        # Generate a secret key and public key pair
        python -c "import zmq.auth; zmq.auth.create_certificates('.', 'filename')"
        ```

    Attributes:
        socket_type: zmq.SocketType
            The type of the socket to create (e.g., zmq.REP).
        bind: str, optional
            The address to bind the socket to.
        connect: str, optional
            The address to connect the socket to.
        secret_key_file: str, optional
            The path to the secret key file for ZeroMQ curve encryption.
        server_public_key_file: str, optional
            The path to the public key file for the server in ZeroMQ curve
            encryption.
        public_keys_location: str, optional
            The location to store the public keys for ZeroMQ curve encryption.
        secret_key: bytes, optional
            The secret key for ZeroMQ curve encryption.
        public_key: bytes, optional
            The public key for ZeroMQ curve encryption.
        server_public_key: bytes, optional
            The public key for the server in ZeroMQ curve encryption.

    Methods:
        _create_socket: zmq.Socket
            Creates and configures a ZeroMQ socket.
        _close_socket: None
            Closes the ZeroMQ socket and the context, and stops the authenticator
            if it was started.

    Examples:
        Create a REP socket and bind it to an address:

        >>> async with ZMQContextManager(zmq.REP, bind='tcp://*:5555') as socket:
        ...     while True:
        ...         message = await socket.recv()
        ...         await socket.send(message)

        Create a REQ socket and connect it to an address:

        >>> with ZMQContextManager(zmq.REQ, connect='tcp://localhost:5555') as socket:
        ...     socket.send(b'Hello')
        ...     message = socket.recv()
    """

    def __init__(self,
                 socket_type: zmq.SocketType,
                 bind: Optional[str] = None,
                 connect: Optional[str] = None,
                 secret_key_file: Optional[str] = None,
                 server_public_key_file: Optional[str] = None,
                 public_keys_location: Optional[str] = None,
                 secret_key: Optional[bytes] = None,
                 public_key: Optional[bytes] = None,
                 server_public_key: Optional[bytes] = None,
                 socket: Optional[zmq.Socket] = None,
                 timeout: Optional[float] = None):
        self.socket_type = socket_type
        if bind is None and connect is None:
            raise ValueError("Either 'bind' or 'connect' must be specified.")
        if bind is not None and connect is not None:
            raise ValueError("Both 'bind' and 'connect' cannot be specified.")
        self.bind = bind
        self.connect = connect
        self.secret_key = secret_key
        self.public_key = public_key
        self.server_public_key = server_public_key
        self.timeout = timeout

        if secret_key_file:
            self.public_key, self.secret_key = zmq.auth.load_certificate(
                secret_key_file)

        if (self.secret_key is not None and self.public_key is None
                or self.secret_key is None and self.public_key is not None):
            raise ValueError(
                "Both secret key and public key must be specified.")

        if server_public_key_file:
            self.server_public_key = zmq.auth.load_certificate(
                server_public_key_file)[0]

        self.public_keys_location = public_keys_location

        self.observer = None
        self.auth = None
        self.context = None
        self.socket = None
        self._external_socket = None
        try:
            if not socket.closed:
                self._external_socket = socket
        except:
            pass

    def _create_socket(self, asyncio=False) -> zmq.Socket:
        """
        Creates and configures a ZeroMQ socket. Sets up security if required,
        and binds or connects the socket according to the specified settings.

        Returns:
            zmq.Socket: The configured ZeroMQ socket.
        """
        if self._external_socket:
            return self._external_socket
        if asyncio:
            self.context = zmq.asyncio.Context()
        else:
            self.context = zmq.Context()

        self.socket = self.context.socket(self.socket_type)
        self.auth = None

        if self.bind and self.secret_key:
            if asyncio:
                self.auth = AsyncioAuthenticator(self.context)
            else:
                self.auth = ThreadAuthenticator(self.context)
            self.auth.start()
            self.reload_certificates()
            self.auto_reload_certificates()
            self.socket.curve_server = True  # must come before bind

        if self.secret_key:
            self.socket.curve_secretkey = self.secret_key
            self.socket.curve_publickey = self.public_key

        if self.bind:
            self.socket.bind(self.bind)
        if self.connect:
            if self.server_public_key:
                self.socket.curve_serverkey = self.server_public_key
            self.socket.connect(self.connect)
        if self.timeout:
            timeout_ms = int(self.timeout * 1000)
            self.socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
            self.socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
        self.socket.setsockopt(zmq.LINGER, 0)
        return self.socket

    def reload_certificates(self):
        if self.public_keys_location and self.auth:
            self.auth.configure_curve(domain='*',
                                      location=self.public_keys_location)

    def auto_reload_certificates(self):
        self.observer = Observer()
        self.observer.schedule(ReloadCertificatesHandler(self),
                               self.public_keys_location,
                               recursive=False)
        self.observer.start()

    def _close_socket(self) -> None:
        """
        Closes the ZeroMQ socket and the context, and stops the authenticator
        if it was started.
        """
        if self._external_socket:
            return
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.socket.close()
        if self.auth:
            self.auth.stop()
        self.context.term()

    def __enter__(self) -> zmq.Socket:
        return self._create_socket(asyncio=False)

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception],
                 exc_tb: Optional[type]) -> None:
        self._close_socket()

    async def __aenter__(self) -> zmq.Socket:
        return self._create_socket(asyncio=True)

    async def __aexit__(self, exc_type: Optional[type],
                        exc_val: Optional[Exception],
                        exc_tb: Optional[type]) -> None:
        self._close_socket()
