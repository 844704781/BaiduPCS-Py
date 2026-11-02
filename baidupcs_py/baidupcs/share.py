"""Read share metadata without executing page JavaScript."""

from html.parser import HTMLParser
import json
import re

from .errors import BaiduPCSShareParseError


class _ShareScripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self._kind = None
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self._kind = dict(attrs).get("type", "").strip().lower()
            self._parts = []

    def handle_data(self, data):
        if self._kind is not None:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._kind is not None:
            self.scripts.append((self._kind, "".join(self._parts)))
            self._kind = None
            self._parts = []


def parse_shared_page(html: str):
    """Support JSON script tags and legacy initializers, including multiline JSON.

    Ignore unrelated JSON scripts. Keep nonzero share errors for assert_ok;
    successfully extracting JSON must not turn an error page into a valid share.
    """
    parser = _ShareScripts()
    parser.feed(html)
    parser.close()
    decoder = json.JSONDecoder()
    error_data = None
    for kind, text in parser.scripts:
        if kind != "application/json":
            continue
        try:
            data = json.loads(text)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        if any(key in data for key in ("file_list", "shareid", "share_uk", "share_page_type")):
            return data
        if data.get("errno", data.get("error_code")) not in (None, 0, "0"):
            error_data = data

    for _, text in parser.scripts:
        for match in re.finditer(r"\b(?:yunData\.setData|locals\.mset)\s*\(\s*", text):
            try:
                data, _ = decoder.raw_decode(text, match.end())
            except ValueError:
                continue
            if isinstance(data, dict):
                return data
    if error_data is not None:
        return error_data
    raise BaiduPCSShareParseError()
