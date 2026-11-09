"""Safe Markdown rendering for entry bodies (N9)."""

import re

import pytest
from markupsafe import Markup

from benchledger.web.deps import templates
from benchledger.web.markdown import render_markdown

# An opening tag (a real "<", not "&lt;") with an event-handler attribute.
ON_ATTRIBUTE = re.compile(r"<[a-z][^>]*\son\w+\s*=", re.IGNORECASE)


def render(text: str) -> str:
    return str(render_markdown(text))


# ---- what must never get through ----


def test_script_tags_are_not_rendered():
    html = render("Before <script>alert(1)</script> after")
    assert "<script" not in html
    assert "&lt;script&gt;" in html  # shown as text, so the reader sees what was typed


def test_script_block_is_not_rendered():
    html = render("<script>\nalert(document.cookie)\n</script>")
    assert "<script" not in html


@pytest.mark.parametrize(
    "text",
    [
        '<img src=x onerror="alert(1)">',
        '<p onclick="alert(1)">hi</p>',
        '<a href="https://example.com" onmouseover="alert(1)">x</a>',
        "<svg onload=alert(1)>",
    ],
)
def test_event_handlers_are_stripped(text):
    html = render(text)
    # No real tag may carry an on...= attribute. The typed text may still be shown,
    # escaped (as &lt;img ... onerror=...&gt;), which is harmless.
    assert not ON_ATTRIBUTE.search(html), html
    for tag in ("<img", "<p onclick", "<a href", "<svg"):
        assert tag not in html


@pytest.mark.parametrize(
    "text",
    [
        "[click](javascript:alert(1))",
        "[click](JaVaScRiPt:alert(1))",
        "[click](javascript&#58;alert(1))",
        "[click]( javascript:alert(1) )",
        "[click](vbscript:msgbox(1))",
        "[click](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)",
        "<javascript:alert(1)>",
        "[ref]\n\n[ref]: javascript:alert(1)",
    ],
)
def test_dangerous_links_are_stripped(text):
    html = render(text)
    assert 'href="javascript' not in html.lower()
    assert 'href="vbscript' not in html.lower()
    assert 'href="data:' not in html.lower()


def test_dangerous_link_check_in_the_cleaner_alone():
    # Even if markdown-it let one through, nh3 removes the href.
    from benchledger.web.markdown import _clean

    assert "javascript" not in _clean('<a href="javascript:alert(1)">x</a>')
    assert "onerror" not in _clean('<img src="x" onerror="alert(1)">')
    assert "<script" not in _clean("<script>alert(1)</script>")


def test_style_attributes_cannot_carry_anything_but_alignment():
    html = render("| a |\n|:-:|\n| b |")
    assert "text-align" in html
    from benchledger.web.markdown import _clean

    cleaned = _clean('<td style="background:url(javascript:alert(1)); text-align:left">x</td>')
    assert "background" not in cleaned and "javascript" not in cleaned


def test_images_render_as_a_link_not_an_image():
    html = render("![scope **trace**](https://example.com/scope.png)")
    assert "<img" not in html
    assert '<a href="https://example.com/scope.png"' in html
    assert "image: scope trace" in html


def test_image_with_a_dangerous_url_loses_its_href():
    html = render('![x](javascript:alert(1) "t")')
    # markdown-it refuses the URL, so the whole thing is shown as plain text.
    assert "<a" not in html and 'href="javascript' not in html.lower()


def test_more_link_tricks_through_the_cleaner():
    from benchledger.web.markdown import _clean

    assert "javascript" not in _clean('<a href="jav&#x09;ascript:alert(1)">x</a>').lower()
    assert "javascript" not in _clean('<a href="&#106;avascript:alert(1)">x</a>').lower()
    # (A <th> must sit in a table, or the HTML parser drops it.)
    cleaned = _clean('<table><tr><th style="position:fixed; text-align:center">h</th></tr></table>')
    assert "position" not in cleaned and "text-align" in cleaned


def test_dangerous_link_inside_a_table_cell():
    html = render("| link |\n| --- |\n| [x](javascript:alert(1)) |")
    assert 'href="javascript' not in html.lower()
    assert "<td>" in html


def test_relative_links_are_allowed_for_links_inside_the_app():
    assert 'href="/projects/adr1399"' in render("[ADR1399](/projects/adr1399)")


# ---- what must survive ----


def test_ordinary_markdown_renders():
    html = render(
        "## Warm-up\n\n"
        "Output settled to **7.054 802 V ± 0.6 µV** after *40 min*.\n\n"
        "- NPLC 100\n- autozero on\n\n"
        "`σ = 0.25 ppm`\n\n"
        "> From the datasheet\n\n"
        "~~wrong range~~"
    )
    for fragment in (
        "<h2>Warm-up</h2>",
        "<strong>7.054 802 V ± 0.6 µV</strong>",
        "<em>40 min</em>",
        "<li>NPLC 100</li>",
        "<code>σ = 0.25 ppm</code>",
        "<blockquote>",
        "<s>wrong range</s>",
    ):
        assert fragment in html


def test_safe_links_keep_href_and_get_rel():
    html = render("[datasheet](https://www.analog.com/adr1399)")
    assert 'href="https://www.analog.com/adr1399"' in html
    assert 'rel="noopener noreferrer nofollow"' in html


def test_angle_brackets_in_measurements_survive_as_text():
    html = render("Zin > 10 GΩ and noise < 1 ppm")
    assert "&gt; 10 GΩ" in html and "&lt; 1 ppm" in html


def test_tables_render():
    html = render("| Run | σ (ppm) |\n| --- | --- |\n| Oct 31 | 0.25 |")
    assert "<table>" in html and "<td>0.25</td>" in html


def test_empty_body_renders_nothing():
    assert render("") == ""
    assert render(None) == ""


def test_jinja_filter_does_not_double_escape():
    out = templates.env.from_string("{{ body | markdown }}").render(body="**bold** & <i>")
    assert "<strong>bold</strong>" in out
    assert "&amp;" in out and "&lt;i&gt;" in out
    assert isinstance(render_markdown("x"), Markup)
