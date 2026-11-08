import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

SITE = "https://infoliontech.neocities.org/"
SITEMAP = SITE + "sitemap.xml"
KNOWN_FILE = Path("known_urls.json")
FEED_FILE = Path("feed.xml")
FEED_URL = "https://raw.githubusercontent.com/infoliontech/infolion-rss/main/feed.xml"

# Only the original Portuguese article pages are included.
EXCLUDED_PATHS = {"/", "/solucoes", "/es", "/en", "/ru"}
LANG_PREFIXES = ("/es/", "/en/", "/ru/")

class PageMeta(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = False
        self.title_text = []
        self.description = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "meta" and attrs.get("name", "").lower() == "description":
            self.description = attrs.get("content", "").strip()
        if tag.lower() == "title":
            self.title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.title = False

    def handle_data(self, data):
        if self.title:
            self.title_text.append(data)

def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "InfoLionRSSBot/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()

def article_urls():
    root = ET.fromstring(fetch(SITEMAP))
    urls = []
    for node in root.findall(".//{*}loc"):
        url = (node.text or "").strip()
        if not url.startswith(SITE):
            continue
        path = url[len(SITE.rstrip("/")):]
        if path in EXCLUDED_PATHS or path.startswith(LANG_PREFIXES):
            continue
        if path and path != "/" and not path.endswith("/"):
            urls.append(url)
    return sorted(set(urls))

def load_known():
    if KNOWN_FILE.exists():
        return set(json.loads(KNOWN_FILE.read_text(encoding="utf-8")))
    return set()

def load_feed():
    if FEED_FILE.exists():
        try:
            return ET.fromstring(FEED_FILE.read_bytes())
        except ET.ParseError:
            pass
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "InfoLion Tech"
    ET.SubElement(channel, "link").text = SITE
    ET.SubElement(channel, "description").text = "Novos tutoriais e artigos do InfoLion Tech."
    ET.SubElement(channel, "language").text = "pt-BR"
    return rss

def main():
    current = set(article_urls())
    known = load_known()
    new_urls = sorted(current - known)
    rss = load_feed()
    channel = rss.find("channel")

    for url in new_urls:
        try:
            page = fetch(url).decode("utf-8", errors="replace")
            parser = PageMeta()
            parser.feed(page)
            title = " ".join("".join(parser.title_text).split()) or url.rstrip("/").split("/")[-1]
            description = parser.description or "Confira o novo artigo no InfoLion Tech."
            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = title
            ET.SubElement(item, "link").text = url
            ET.SubElement(item, "guid", isPermaLink="true").text = url
            ET.SubElement(item, "description").text = description
            ET.SubElement(item, "pubDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
            print(f"Novo artigo adicionado ao RSS: {title}")
        except Exception as exc:
            print(f"Falha ao ler {url}: {exc}")

    KNOWN_FILE.write_text(json.dumps(sorted(current), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ET.indent(rss, space="  ")
    FEED_FILE.write_bytes(ET.tostring(rss, encoding="utf-8", xml_declaration=True))
    print(f"RSS atualizado. Novos artigos: {len(new_urls)}. Feed: {FEED_URL}")

if __name__ == "__main__":
    main()
