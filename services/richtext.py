import html
import re
from html.parser import HTMLParser
from urllib.parse import urlparse


ALLOWED_TAGS = {"p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li", "a"}


def safe_link(value):
    value = (value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value
    if value.startswith("/") and not value.startswith("//"):
        return value
    return ""


class RichTextSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            return
        if tag == "br":
            self.output.append("<br>")
            return
        attributes = []
        if tag == "a":
            href = safe_link(dict(attrs).get("href", ""))
            if not href:
                return
            attributes = [f'href="{html.escape(href, quote=True)}"', 'data-service-preview="true"']
            if urlparse(href).scheme in {"http", "https"}:
                attributes.extend(['target="_blank"', 'rel="noopener noreferrer"'])
        self.output.append(f"<{tag}{(' ' + ' '.join(attributes)) if attributes else ''}>")

    def handle_endtag(self, tag):
        if tag in ALLOWED_TAGS and tag != "br":
            self.output.append(f"</{tag}>")

    def handle_data(self, data):
        self.output.append(html.escape(data))
        self.text.append(data)


def sanitize_rich_text(value):
    parser = RichTextSanitizer()
    parser.feed(value or "")
    parser.close()
    return "".join(parser.output).strip(), " ".join(parser.text).strip()


def word_count(value):
    _, text = sanitize_rich_text(value)
    return len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))
