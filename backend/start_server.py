import socket

import uvicorn

# Force SO_REUSEADDR on all sockets
_orig_socket = socket.socket


def _new_socket(*args, **kwargs):
    s = _orig_socket(*args, **kwargs)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return s


socket.socket = _new_socket

uvicorn.run("main:app", host="0.0.0.0", port=8001, log_level="info")
