import ipaddress
import socket
import urllib.parse
import httpx
from django.conf import settings

# Blocked IP ranges: private, loopback, link-local, multicast, reserved
DISALLOWED_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),        # Loopback IPv4
    ipaddress.ip_network('10.0.0.0/8'),         # Private class A
    ipaddress.ip_network('172.16.0.0/12'),      # Private class B
    ipaddress.ip_network('192.168.0.0/16'),     # Private class C
    ipaddress.ip_network('169.254.0.0/16'),     # Link-local / AWS & cloud metadata
    ipaddress.ip_network('0.0.0.0/8'),          # Current network
    ipaddress.ip_network('224.0.0.0/4'),        # Multicast
    ipaddress.ip_network('240.0.0.0/4'),        # Reserved
    ipaddress.ip_network('::1/128'),            # Loopback IPv6
    ipaddress.ip_network('fc00::/7'),           # Unique local IPv6
    ipaddress.ip_network('fe80::/10'),          # Link-local IPv6
]


class SSRFValidationError(Exception):
    """Raised when a URL targets a prohibited destination or uses an invalid scheme."""
    pass


def is_ip_allowed(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        for net in DISALLOWED_NETWORKS:
            if ip in net:
                return False
        return True
    except ValueError:
        return False


def validate_url_safe(url: str) -> str:
    """
    Validates scheme and resolves hostname to ensure it does not resolve
    to any loopback, internal, or cloud-metadata address.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise SSRFValidationError(f"Invalid scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("URL lacks a valid hostname.")

    # Disallow known internal keywords
    lowered_host = hostname.lower()
    if lowered_host in ('localhost', 'metadata.google.internal', 'instance-data'):
        raise SSRFValidationError(f"Prohibited host name: {hostname}")

    try:
        # Resolve all DNS A and AAAA records
        addr_info = socket.getaddrinfo(hostname, None)
        for info in addr_info:
            ip_str = info[4][0]
            if not is_ip_allowed(ip_str):
                raise SSRFValidationError(f"Host '{hostname}' resolved to disallowed IP address: {ip_str}")
    except socket.gaierror as e:
        raise SSRFValidationError(f"Could not resolve host '{hostname}': {str(e)}")

    return url


def safe_fetch_url(
    url: str,
    timeout: float = getattr(settings, 'REQUEST_TIMEOUT_SECONDS', 10.0),
    max_bytes: int = getattr(settings, 'MAX_FETCH_SIZE_BYTES', 524288),
    headers: dict = None
) -> dict:
    """
    Safely fetches the given URL with SSRF protection, redirection safety,
    timeouts, and maximum byte size enforcement.
    Returns dict: {'status_code': int, 'content': str, 'url': str}
    """
    current_url = validate_url_safe(url)
    default_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.5',
    }
    if headers:
        default_headers.update(headers)

    max_redirects = 3
    redirect_count = 0

    with httpx.Client(timeout=timeout, verify=True, follow_redirects=False) as client:
        while True:
            response = client.get(current_url, headers=default_headers)

            if response.is_redirect:
                redirect_count += 1
                if redirect_count > max_redirects:
                    raise SSRFValidationError("Exceeded maximum redirects (3).")
                location = response.headers.get("Location")
                if not location:
                    raise SSRFValidationError("Redirect response missing Location header.")
                next_url = urllib.parse.urljoin(current_url, location)
                current_url = validate_url_safe(next_url)
                continue

            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise ValueError(f"Content-Length {content_length} exceeds max allowed {max_bytes} bytes.")

            body = response.text[:max_bytes]
            return {
                'status_code': response.status_code,
                'content': body,
                'final_url': str(response.url)
            }
