"""The first outbound call clark makes itself (#643, slice 1): one small HTTPS POST to two pinned hosts. Nothing in clark calls this yet.

Rules, each tested: only `HOSTS` (anything else is refused before a socket opens); certificates verified (ssl.create_default_context(), never
relaxed); redirects are never followed; the reply is read in chunks and refused past `max_reply`; a timeout per socket call AND an overall deadline checked between chunks (so one blocked read can run past the deadline, by at most the per-call timeout); no retry. Every failure is an
HttpsError with one fixed code. The headers (which hold the key) and the path are never logged and never put in an exception.

NO PROXY, on purpose: http.client does not read HTTPS_PROXY or the system proxy settings, so a request goes straight to the host. That is
the owner's open decision (#643): a person behind a company proxy cannot use this route until one is chosen.
"""
import http.client
import socket
import ssl
import time

HOSTS = ("api.anthropic.com", "api.openai.com")
CHUNK = 64 * 1024
TIMEOUTS = (TimeoutError, socket.timeout)     # on Python 3.9 socket.timeout is not TimeoutError; later they are the same
CODES = ("timeout", "connection", "too_big", "refused_host", "redirect")


class HttpsError(Exception):
    """A call that did not give a usable reply. `code` is one of CODES; the text is the code and nothing else."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _connect(host, timeout):
    return http.client.HTTPSConnection(host, timeout=timeout, context=ssl.create_default_context())


def post_json(host, path, headers, body_bytes, timeout=60, max_reply=4_000_000, connect=None, deadline=60, clock=time.monotonic):
    """POST `body_bytes` and return (status, reply_bytes). `connect(host, timeout)` is a seam for tests: it returns a connection-like object.
    `timeout` is per socket call; `deadline` (seconds, `clock` is a test seam) is the whole call, checked between chunks."""
    if host not in HOSTS:
        raise HttpsError("refused_host")
    conn = None
    ends = clock() + deadline
    try:
        conn = (connect or _connect)(host, timeout)
        conn.request("POST", path, body=body_bytes, headers=dict(headers))
        reply = conn.getresponse()
        status = reply.status
        if 300 <= status < 400:
            raise HttpsError("redirect")
        data = b""
        while True:
            if clock() > ends:
                raise HttpsError("timeout")
            chunk = reply.read(min(CHUNK, max_reply - len(data) + 1))     # never more than one byte past the cap
            if not chunk:
                break
            data += chunk
            if len(data) > max_reply:
                raise HttpsError("too_big")
        return status, data
    except HttpsError:
        raise
    except TIMEOUTS:
        raise HttpsError("timeout") from None
    except Exception:       # ssl errors, refused connections, resets, bad replies: one code, no text
        raise HttpsError("connection") from None
    finally:
        del headers                     # it holds the key: not left in this frame for a traceback to reach
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
