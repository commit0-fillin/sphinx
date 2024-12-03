"""Simple requests package loader"""
from __future__ import annotations
import warnings
from typing import Any
from urllib.parse import urlsplit
import requests
from urllib3.exceptions import InsecureRequestWarning
import sphinx
_USER_AGENT = f'Mozilla/5.0 (X11; Linux x86_64; rv:100.0) Gecko/20100101 Firefox/100.0 Sphinx/{sphinx.__version__}'

def _get_tls_cacert(url: str, certs: str | dict[str, str] | None) -> str | bool:
    """Get additional CA cert for a specific URL."""
    if certs is None:
        return True
    elif isinstance(certs, str):
        return certs
    elif isinstance(certs, dict):
        hostname = urlsplit(url).hostname
        if hostname:
            return certs.get(hostname, True)
    return True

def get(url: str, **kwargs: Any) -> requests.Response:
    """Sends a GET request like ``requests.get()``.

    This sets up User-Agent header and TLS verification automatically.
    """
    kwargs.setdefault('allow_redirects', True)
    return _Session().request('GET', url, **kwargs)

def head(url: str, **kwargs: Any) -> requests.Response:
    """Sends a HEAD request like ``requests.head()``.

    This sets up User-Agent header and TLS verification automatically.
    """
    kwargs.setdefault('allow_redirects', False)
    return _Session().request('HEAD', url, **kwargs)

class _Session(requests.Session):

    def request(self, method: str, url: str, _user_agent: str='', _tls_info: tuple[bool, str | dict[str, str] | None]=(), **kwargs: Any) -> requests.Response:
        """Sends a request with an HTTP verb and url.

        This sets up User-Agent header and TLS verification automatically.
        """
        kwargs.setdefault('headers', {}).setdefault('User-Agent', _user_agent or _USER_AGENT)

        if _tls_info:
            verify, certs = _tls_info
            if verify:
                kwargs['verify'] = _get_tls_cacert(url, certs)
            else:
                kwargs['verify'] = False
                warnings.filterwarnings('ignore', category=InsecureRequestWarning)

        return super().request(method, url, **kwargs)
