"""One-launch loopback browser session; no persistent grant or provider key."""
import hmac
import re
import secrets
import threading
from http.cookies import CookieError, SimpleCookie
from urllib.parse import unquote, urlsplit

from .security import WorkflowError

COOKIE_NAME = 'storymotion-session'
TOKEN = re.compile(r'[A-Za-z0-9_-]{43}')


class LocalSession:
    def __init__(self):
        self._bootstrap_token = secrets.token_urlsafe(32)
        self._session_token = secrets.token_urlsafe(32)
        self._issued = False
        self._closed = False
        self._port = None
        self._lock = threading.Lock()

    def launch_url(self, port):
        with self._lock:
            base = 'http://127.0.0.1:' + str(port) + '/'
            return base if self._issued or self._closed else base + '#bootstrap=' + self._bootstrap_token

    @staticmethod
    def cookie_name(port):return COOKIE_NAME+'-'+str(port)

    def bootstrap(self, token, port):
        with self._lock:
            if (self._closed or self._issued or not isinstance(token, str) or not TOKEN.fullmatch(token)
                    or not hmac.compare_digest(token, self._bootstrap_token)):
                return None
            self._issued = True
            self._port = port
            self._bootstrap_token = None
            return self.cookie_name(port) + '=' + self._session_token + '; Path=/; HttpOnly; SameSite=Strict'

    def authenticated(self, headers, port):
        name = self.cookie_name(port)
        values = headers.get_all('Cookie', [])
        if len(values) != 1 or len(values[0]) > 4096:
            return False
        # Reject duplicate session fields instead of accepting parser overwrite.
        if sum(part.strip().split('=', 1)[0] == name for part in values[0].split(';')) != 1:
            return False
        try:
            cookies = SimpleCookie(); cookies.load(values[0])
            token = cookies[name].value if name in cookies else ''
        except CookieError:
            return False
        with self._lock:
            return bool(not self._closed and self._issued and self._port == port and TOKEN.fullmatch(token)
                        and hmac.compare_digest(token, self._session_token))

    def close(self):
        with self._lock:
            self._closed = True
            self._bootstrap_token = None
            self._session_token = None


def request_path(target):
    """Decode once and reject ambiguous separators/traversal before dispatch."""
    try:
        if not isinstance(target, str) or len(target) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in target):
            raise ValueError()
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not parsed.path.startswith('/'):
            raise ValueError()
        if re.search(r'%(?![0-9a-fA-F]{2})', parsed.path):
            raise ValueError()
        path = unquote(parsed.path, encoding='utf-8', errors='strict')
        if '%' in path or '\\' in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
            raise ValueError()
        if path != '/' and any(part in ('', '.', '..') for part in path[1:].split('/')):
            raise ValueError()
        return path
    except (ValueError, UnicodeError):
        raise WorkflowError('REQUEST_PATH_INVALID') from None
