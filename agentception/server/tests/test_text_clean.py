"""Markdown flattening shared by the Reducto adapter and the JD fetcher."""

from server.tools.text_clean import strip_markdown


def test_removes_images_and_unwraps_links():
    md = "![banner](http://cdn/x.png) See [the docs](https://example.com/docs) now"
    assert strip_markdown(md) == "See the docs now"


def test_keep_urls_retains_the_target():
    md = "Profile: [GitHub](https://github.com/arun)"
    assert strip_markdown(md, keep_urls=True) == "Profile: GitHub https://github.com/arun"


def test_strips_inline_html_and_emphasis():
    assert strip_markdown("<b>Senior</b> **AI** __Engineer__") == "Senior AI Engineer"


def test_heading_callback_receives_level_and_text():
    md = "# Arun Kumar\n\n## Professional Summary\n\nSome text"
    out = strip_markdown(md, heading=lambda level, text: text if level == 1 else text.upper())
    assert "Arun Kumar" in out
    assert "PROFESSIONAL SUMMARY" in out


def test_bullets_are_rewritten_with_the_requested_prefix():
    assert strip_markdown("- one\n* two\n+ three", bullet="• ") == "• one\n• two\n• three"


def test_drop_blank_lines_removes_them_entirely():
    assert strip_markdown("a\n\n\n\nb", drop_blank_lines=True) == "a\nb"


def test_blank_line_runs_collapse_when_not_dropping():
    assert strip_markdown("a\n\n\n\nb") == "a\n\nb"


def test_max_chars_truncates():
    assert strip_markdown("abcdefghij", max_chars=4) == "abcd"
