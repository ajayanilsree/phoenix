import ipaddress
import socket
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.utils import timezone

from .models import ServiceLinkPreview
from .richtext import safe_link


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.title = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key in {"og:title", "og:description", "og:image", "description"}:
                self.meta[key] = (attrs.get("content") or "").strip()
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)


def _public_destination(url):
    url = safe_link(url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "metadata.google.internal"} or hostname.endswith(".local"):
        return None
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except (OSError, ValueError):
        return None
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return None
    return url


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _public_destination(newurl):
            raise URLError("Unsafe redirect destination")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_preview(url):
    public_url = _public_destination(url)
    parsed = urlparse(public_url or "")
    domain = parsed.netloc
    preview = {"url": public_url or url, "domain": domain, "title": domain, "description": "", "image_url": ""}
    if not public_url:
        return preview
    try:
        request = Request(public_url, headers={"User-Agent": "PhoenixInteriorHubLinkPreview/1.0", "Accept": "text/html"})
        with build_opener(SafeRedirectHandler).open(request, timeout=4) as response:
            content_type = (response.headers.get_content_type() or "").lower()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                return preview
            final_url = response.geturl()
            if not _public_destination(final_url):
                return preview
            raw = response.read(512 * 1024)
        parser = MetadataParser()
        parser.feed(raw.decode("utf-8", errors="replace"))
        preview["title"] = parser.meta.get("og:title") or "".join(parser.title).strip() or domain
        preview["description"] = parser.meta.get("og:description") or parser.meta.get("description", "")
        image = parser.meta.get("og:image", "")
        image_url = urljoin(final_url, image) if image else ""
        preview["image_url"] = image_url if image_url and _public_destination(image_url) else ""
    except (OSError, ValueError, HTTPError, URLError, socket.timeout):
        pass
    return preview


def cache_preview(url):
    if not safe_link(url):
        return None
    preview = fetch_preview(url)
    return ServiceLinkPreview.objects.update_or_create(
        url=preview["url"],
        defaults={**preview, "fetched_at": timezone.now()},
    )[0]
