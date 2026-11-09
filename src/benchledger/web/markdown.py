"""Safe Markdown for entry bodies (requirement N9: user text never runs as code).

Two layers, so a mistake in one is caught by the other:

  1. markdown-it-py renders CommonMark (plus tables and ~~strikethrough~~) with raw HTML
     turned off, so typed tags such as <script> come out as visible text, and its link
     check refuses javascript:, vbscript:, file: and data: URLs.
  2. nh3 cleans the result against an allow-list: only the tags Markdown produces, no
     event handlers or style attributes, and links limited to http, https and mailto.

Images are not shown yet: an external image would load from the internet and a local one
has nowhere to live until photos and files arrive (M12). Until then `![alt](url)` renders
as a plain link labelled "image: alt", so nothing typed silently disappears.

Relative links (`/projects/adr1399`) are allowed so entries can point around the app.

The output is safe as HTML *element content* only. Never put it inside an attribute,
<textarea>, <title>, <script> or <style>; use the raw text (auto-escaped) there.
"""

from __future__ import annotations

import nh3
from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markupsafe import Markup

_md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable(
    ["table", "strikethrough"]
)


def _image_as_link(self, tokens, idx, options, env) -> str:
    token = tokens[idx]
    alt = self.renderInlineAsText(token.children or [], options, env) or "untitled"
    src = escapeHtml(str(token.attrGet("src") or ""))
    return f'<a href="{src}">image: {escapeHtml(alt)}</a>'


_md.add_render_rule("image", _image_as_link)

ALLOWED_TAGS = {
    "p", "br", "hr", "blockquote", "pre", "code",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "em", "strong", "s", "del",
    "ul", "ol", "li",
    "a",
    "table", "thead", "tbody", "tr", "th", "td",
}  # fmt: skip
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "ol": {"start"},
    "th": {"style"},  # markdown-it marks column alignment with style="text-align:…"
    "td": {"style"},
}
URL_SCHEMES = {"http", "https", "mailto"}


def _clean(html: str) -> str:
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=URL_SCHEMES,
        # Only text-align survives in the allowed style attributes.
        filter_style_properties={"text-align"},
        link_rel="noopener noreferrer nofollow",
        strip_comments=True,
    )


def render_markdown(text: str | None) -> Markup:
    """Markdown source to cleaned HTML, marked safe for Jinja so it isn't escaped twice."""
    if not text:
        return Markup("")
    return Markup(_clean(_md.render(text)))
