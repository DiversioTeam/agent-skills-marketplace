"""The visual-explainer page checker: real-shaped pages that fail and pass, every rule, and the templates.

The rules and their names match Courage's internal-share gate (DiversioTeam/courage src/readable-pages.ts). The
fixtures are two invented pages in the shape of real ones (an ads report and a PR re-review), and the same pages
rewritten to the standard.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).parents[1] / "plugins" / "visual-explainer" / "skills" / "visual-explainer"
SPEC = importlib.util.spec_from_file_location("visual_explainer_check_page_test", SKILL / "scripts" / "check_page.py")
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)
FIXTURES = Path(__file__).parent / "fixtures" / "readable-pages"

STYLE = (":root{--bg:#f6f6f3;--surface:#ffffff;--text:#1d1d1f;--muted:#5f6368}"
         "@media (prefers-color-scheme: dark){:root{--bg:#121316;--surface:#1b1c20;--text:#ececee;--muted:#a2a6ad}}"
         "body{font:16px/1.6 system-ui}")
LEAD = '<section class="summary"><p>Both fixes are verified; nothing for you to do.</p></section>'


def page(body: str, title: str = "Retest", head: str = "") -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, '
            f'initial-scale=1"><title>{title}</title><style>{STYLE}</style>{head}</head><body><main>{body}</main></body></html>')


def rules(html: str) -> list[str]:
    return sorted({rule for rule, _ in checker.check_page(html)})


class CheckPageTests(unittest.TestCase):
    def test_published_ads_report_fails_for_buried_action_ids_no_visual_no_nav_and_a_wide_table(self) -> None:
        html = (FIXTURES / "ads-before.html").read_text(encoding="utf-8")
        self.assertEqual(rules(html), ["ids", "navigation", "next_step", "type", "visuals"])
        messages = "\n".join(message for _, message in checker.check_page(html))
        self.assertIn("512904417730", messages)
        self.assertIn("four or more columns", messages)

    def test_published_review_fails_for_hashes_and_a_machine_path(self) -> None:
        html = (FIXTURES / "review-before.html").read_text(encoding="utf-8")
        self.assertEqual(rules(html), ["ids", "next_step"])
        messages = "\n".join(message for _, message in checker.check_page(html))
        self.assertIn("4 × a full commit hash", messages)
        self.assertIn("a machine path (/home/runner/work/billing/billing)", messages)

    def test_rewritten_pages_pass(self) -> None:
        for name in ("ads-after.html", "review-after.html"):
            self.assertEqual(checker.check_page((FIXTURES / name).read_text(encoding="utf-8")), [], name)

    def test_each_rule_catches_its_page_shape(self) -> None:
        sections = "".join(f'<h2 id="s{i}">Part {i}</h2><p>Short.</p>' for i in range(5))
        wide_table = '<div class="table-wrap"><table><tr><td>a</td><td>1</td><td>2</td><td>3</td></tr></table></div>'
        cases = [
            ("self_contained", page(LEAD, head='<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">')),
            ("basics", "<p>Both fixes are verified; nothing for you to do.</p>"),
            ("dark_mode", page(LEAD).replace("@media (prefers-color-scheme: dark)", "@media (min-width: 1px)")),
            ("answer_first", page('<h2 id="a">Details</h2><p>Some detail.</p>')),
            ("next_step", page('<section class="summary"><p>The count moved by one.</p></section>')),
            ("ids", page(LEAD + "<p>Built at 8c41f07a9d2e6b5c3f1e0d9a8b7c6d5e4f3a2b1c in /workspace/app.</p>")),
            ("navigation", page(LEAD + sections)),
            ("navigation", page(LEAD + '<nav class="toc"><a href="#a">A</a><a href="#b">B</a><a href="#c">C</a></nav>'
                                '<h2 id="a">A</h2><p>x</p><h2 id="a">B</h2><p>y</p>')),
            ("wall_of_text", page(LEAD + "<p>" + "word " * 130 + "</p>")),
            ("visuals", page(LEAD + '<pre class="mermaid">flowchart LR\n A --> B</pre>')),
            ("type", page(LEAD + "<style>.x{font-size:10px}</style>")),
            ("type", page(LEAD + wide_table)),
            ("contrast", page(LEAD + "<style>.faint{color:#999999;background:#ffffff}</style>")),
            ("empty", page(LEAD + '<h2 id="a">Risks</h2><h2 id="b">Evidence</h2><p>Logs.</p>')),
        ]
        for rule, html in cases:
            with self.subTest(rule=rule):
                self.assertIn(rule, rules(html))

    def test_ids_in_folded_evidence_and_stacked_wide_tables_are_fine(self) -> None:
        sha = "8c41f07a9d2e6b5c3f1e0d9a8b7c6d5e4f3a2b1c"
        stacked = ('<div class="table-wrap"><table class="stack"><tr><td>a</td><td data-label="One">1</td><td data-label="Two">2</td>'
                   '<td data-label="Three">3</td></tr></table></div>')
        cards = "<style>@media (max-width: 600px) { table.stack tr, table.stack td { display: block; } }</style>"
        html = page(LEAD + f'<details class="evidence"><summary>Evidence</summary><p>Head {sha}.</p></details>' + stacked, head=cards)
        self.assertEqual(checker.check_page(html), [])

    def test_the_skill_templates_meet_the_standard(self) -> None:
        for name in ("architecture.html", "data-table.html", "diagram.html"):
            with self.subTest(template=name):
                self.assertEqual(checker.check_page((SKILL / "templates" / name).read_text(encoding="utf-8")), [])


class ReviewFindingTests(unittest.TestCase):
    """Cases from the review of the first version: each failed or crashed before its fix."""

    def test_identical_sections_are_separate_nodes(self) -> None:
        twin = '<section><h2 id="{id}">Status</h2>{body}</section>'
        html = page(LEAD + twin.format(id="a", body="<p>Fine.</p>") + twin.format(id="b", body=""))
        self.assertIn("empty", rules(html), "the empty second section is found, not mistaken for the first")
        self.assertNotIn("empty", rules(page(LEAD + twin.format(id="a", body="<p>Fine.</p>") + twin.format(id="b", body="<p>Fine.</p>"))))

    def test_optional_end_tags_are_read_like_a_browser(self) -> None:
        wide = page(LEAD + '<div class="table-wrap"><table><tr><td>a<td>b<td>c<td>d</table></div>')
        self.assertIn("four or more columns", " ".join(message for _, message in checker.check_page(wide)))
        long_list = page(LEAD + "<ul>" + "<li>item" * 1000 + "</ul>")
        self.assertEqual(checker.check_page(long_list), [], "a thousand unclosed items are siblings, not a thousand levels deep")

    def test_srcset_and_svg_image_references_are_external_loads(self) -> None:
        for html in ('<img src="data:image/png;base64,AA==" srcset="https://cdn.example/a.png 2x" alt="a">',
                     '<svg viewBox="0 0 10 10"><image href="https://cdn.example/b.png"></image></svg>'):
            with self.subTest(html=html):
                self.assertIn("self_contained", rules(page(LEAD + html)))
        self.assertNotIn("self_contained", rules(page(LEAD + '<svg viewBox="0 0 10 10"><image href="data:image/png;base64,AA=="></image></svg>')))

    def test_video_posters_objects_and_image_sets_are_external_loads(self) -> None:
        embedded = "data:image/png;base64,AA=="
        cases = [('<video poster="poster.jpg" controls></video>', f'<video poster="{embedded}" controls></video>'),
                 ('<object data="figure.svg" type="image/svg+xml"></object>',
                  f'<object data="{embedded}" type="image/png"></object>'),
                 ('<div style="background-image: image-set(\'figure.png\' 1x)"></div>',
                  f'<div style="background-image: image-set(\'{embedded}\' 1x)"></div>')]
        for linked, inline in cases:
            with self.subTest(html=linked):
                self.assertIn("self_contained", rules(page(LEAD + linked)))
                self.assertNotIn("self_contained", rules(page(LEAD + inline)))
        sheet = '<style>.hero { background: image-set("hero.png" type("image/png") 1x) }</style>'
        self.assertIn("self_contained", rules(page(LEAD, head=sheet)))

    def test_a_dark_first_page_has_its_light_overrides_checked(self) -> None:
        dark_first = ("<style>:root{--bg:#0f1729;--surface:#162040;--text:#e8e4d8;--accent:#d4a73a}"
                      "@media (prefers-color-scheme: light){:root{--bg:#faf8f2;--surface:#ffffff;--text:#1a1814;"
                      "--accent:#b8860b}}</style>")
        messages = " ".join(message for _, message in checker.check_page(page(LEAD, head=dark_first)))
        self.assertIn("In the light theme --accent on --bg is 3.1:1", messages)
        literal = "<style>@media (prefers-color-scheme: light) { .label { color: #b8860b; background: #faf8f2 } }</style>"
        messages = " ".join(message for _, message in checker.check_page(page(LEAD, head=literal)))
        self.assertIn("(light mode) sets #b8860b on #faf8f2 (3.1:1)", messages)

    def test_section_nav_covers_every_section(self) -> None:
        sections = "".join(f'<h2 id="s{i}">Part {i}</h2><p>Short.</p>' for i in range(5))
        partial = '<nav class="toc">' + "".join(f'<a href="#s{i}">Part {i}</a>' for i in range(3)) + "</nav>"
        messages = " ".join(message for _, message in checker.check_page(page(LEAD + partial + sections)))
        self.assertIn("leaves out 'Part 3', 'Part 4'", messages)
        full = '<nav class="toc">' + "".join(f'<a href="#s{i}">Part {i}</a>' for i in range(5)) + "</nav>"
        self.assertNotIn("navigation", rules(page(LEAD + full + sections)))

    def test_nav_links_may_point_at_the_enclosing_section(self) -> None:
        sections = "".join(f'<section id="s{i}"><h2>Part {i}</h2><p>Short.</p></section>' for i in range(5))
        full = '<nav class="toc">' + "".join(f'<a href="#s{i}">Part {i}</a>' for i in range(5)) + "</nav>"
        self.assertNotIn("navigation", rules(page(LEAD + full + sections)))
        partial = '<nav class="toc">' + "".join(f'<a href="#s{i}">Part {i}</a>' for i in range(4)) + "</nav>"
        messages = " ".join(message for _, message in checker.check_page(page(LEAD + partial + sections)))
        self.assertIn("leaves out 'Part 4'", messages)
        # A section id that wraps two headings doesn't stand for either of them.
        shared = ('<section id="both"><h2>Part 0</h2><p>Short.</p><h2>Part 1</h2><p>Short.</p></section>'
                  + "".join(f'<section id="s{i}"><h2>Part {i}</h2><p>Short.</p></section>' for i in range(2, 5)))
        nav = '<nav class="toc"><a href="#both">Both</a>' + "".join(f'<a href="#s{i}">Part {i}</a>' for i in range(2, 5)) + "</nav>"
        self.assertIn("navigation", rules(page(LEAD + nav + shared)))

    def test_mermaid_source_shown_as_text_is_caught(self) -> None:
        self.assertIn("visuals", rules(page(LEAD + "<pre>flowchart TD\n A --&gt; B</pre>")))
        self.assertIn("visuals", rules(page(LEAD + "<pre>sequenceDiagram\n A->>B: hi</pre>")))
        self.assertNotIn("visuals", rules(page(LEAD + "<p>The flowchart TD style is not used here.</p>")))

    def test_mermaid_source_in_any_visible_block_is_caught_but_not_in_hidden_ones(self) -> None:
        self.assertIn("visuals", rules(page(LEAD + "<blockquote><p>Draft below.</p>\nflowchart TD\n  A --&gt; B</blockquote>")))
        self.assertIn("visuals", rules(page(LEAD + "<blockquote>\nflowchart TD\n  A --&gt; B\n</blockquote>")))
        self.assertIn("visuals", rules(page(LEAD + "<section><p>Draft below.</p><p>graph LR A --&gt; B</p></section>")))
        self.assertNotIn("visuals", rules(page(LEAD + "<template><pre>flowchart TD\n A --&gt; B</pre></template>")))
        self.assertNotIn("visuals", rules(page(LEAD + "<div hidden><pre>flowchart TD\n A --&gt; B</pre></div>")))

    def test_assets_inside_an_iframe_srcdoc_are_external_loads(self) -> None:
        linked = '<iframe title="Chart" srcdoc="&lt;img alt=&quot;Chart&quot; src=chart.png&gt;"></iframe>'
        self.assertIn("iframe srcdoc: img chart.png", " ".join(message for _, message in checker.check_page(page(LEAD + linked))))
        styled = '<iframe title="Chart" srcdoc="&lt;style&gt;p{background:url(bg.png)}&lt;/style&gt;&lt;p&gt;Hi&lt;/p&gt;"></iframe>'
        self.assertIn("self_contained", rules(page(LEAD + styled)))
        embedded = '<iframe title="Chart" srcdoc="&lt;img alt=&quot;Chart&quot; src=&quot;data:image/png;base64,AA==&quot;&gt;"></iframe>'
        self.assertNotIn("self_contained", rules(page(LEAD + embedded)))

    def test_inline_font_sizes_count(self) -> None:
        messages = " ".join(message for _, message in checker.check_page(page(LEAD + '<p style="font-size:9px">Decision details</p>')))
        self.assertIn("as small as 9px", messages)
        self.assertIn("Body text is 9px", messages)
        self.assertIn("Body text is 13px", " ".join(m for _, m in checker.check_page(page(LEAD + '<p style="font-size: 13px">Notes</p>'))))
        self.assertNotIn("type", rules(page(LEAD + '<span style="font-size: 13px">Caption</span>')), "13px is fine outside body text")
        self.assertNotIn("type", rules(page(LEAD + '<p style="font-size:16px">Decision details</p>')))

    def test_a_hidden_summary_does_not_answer_first(self) -> None:
        body = ('<section class="summary"{}><p>Both fixes are verified; nothing for you to do.</p></section>'
                '<h2 id="m">Measurements</h2><p>Median load time fell from 2.4 seconds to 1.1 seconds.</p>')
        self.assertIn("answer_first", rules(page(body.format(" hidden"))))
        self.assertEqual(rules(page(body.format(""))), [])
        self.assertIn("answer_first", rules(page('<div hidden><p>Both fixes are verified; nothing for you to do.</p></div>'
                                                 '<h2 id="m">Measurements</h2><p>Load time fell.</p>')), "the fallback lead skips hidden text too")

    def test_svg_font_size_attributes_count_for_the_floor(self) -> None:
        svg = '<figure><svg viewBox="0 0 200 40" role="img" aria-label="Label"><text x="0" y="20" font-size="{}">Label</text></svg></figure>'
        self.assertIn("as small as 9px", " ".join(m for _, m in checker.check_page(page(LEAD + svg.format("9")))))
        self.assertIn("type", rules(page(LEAD + svg.format("11px"))))
        self.assertNotIn("type", rules(page(LEAD + svg.format("12"))))

    def test_css_comments_are_not_read_as_rules(self) -> None:
        self.assertIn("type", rules(page(LEAD, head="<style>body{font-size:9px}</style>")))
        self.assertNotIn("type", rules(page(LEAD, head="<style>/* Old body{font-size:9px} */</style>")))
        self.assertNotIn("type", rules(page(LEAD + '<p style="/* was font-size:9px */ font-size:16px">Decision details</p>')))
        quoted = '<style>.note::before { content: "/* not a comment */"; } body{font-size:9px}</style>'
        self.assertIn("type", rules(page(LEAD, head=quoted)), "a /* inside a string does not start a comment")

    def test_inline_emphasis_in_prose_is_not_diagram_source(self) -> None:
        self.assertNotIn("visuals", rules(page(LEAD + "<p>The <strong>flowchart TD</strong> syntax is optional.</p>")))
        self.assertIn("visuals", rules(page(LEAD + "<div><p>Draft.</p><p><strong>flowchart TD</strong> A --&gt; B</p></div>")))

    def test_every_srcset_candidate_is_checked(self) -> None:
        gif = "data:image/gif;base64,R0lGODlhAQABAIAAAAUEBA=="
        adjacent = f'<img alt="Chart" src="{gif}" srcset="{gif} 1x,chart-2x.png 2x">'
        self.assertIn("image chart-2x.png", " ".join(m for _, m in checker.check_page(page(LEAD + adjacent))))
        self.assertNotIn("self_contained", rules(page(LEAD + f'<img alt="Chart" src="{gif}" srcset="{gif} 1x,{gif} 2x">')))
        self.assertEqual(checker.srcset_urls(f"{gif} 1x,chart-2x.png 2x, wide.png 640w"), [gif, "chart-2x.png", "wide.png"])

    def test_the_body_text_minimum_looks_at_the_element_a_selector_targets(self) -> None:
        self.assertNotIn("type", rules(page(LEAD, head="<style>main .caption { font-size: 13px }</style>")))
        self.assertIn("Body text is 13px", " ".join(m for _, m in checker.check_page(page(LEAD, head="<style>main p { font-size: 13px }</style>"))))
        self.assertIn("Body text is 14px",
                      " ".join(m for _, m in checker.check_page(page(LEAD, head="<style>.note, body > p.lede { font-size: 14px }</style>"))))

    def test_a_long_page_links_each_of_its_sections_even_when_there_are_fewer_than_three(self) -> None:
        long = f"<ul>{'<li>' + 'word ' * 100 + '</li>' * 1}</ul>" * 13
        two = f'<h2 id="a">First</h2>{long}<h2 id="b">Second</h2><p>End.</p>'
        self.assertNotIn("navigation", rules(page(LEAD + '<nav class="toc"><a href="#a">First</a><a href="#b">Second</a></nav>' + two)))
        self.assertIn("navigation", rules(page(LEAD + '<nav class="toc"><a href="#a">First</a></nav>' + two)))
        self.assertIn("no sections. Split it into sections", " ".join(m for _, m in checker.check_page(page(LEAD + long))))

    def test_a_summary_whose_answer_is_hidden_does_not_answer_first(self) -> None:
        hidden = '<section class="summary"><p hidden>Both fixes are verified; nothing for you to do.</p></section><h2 id="m">Results</h2><p>Load fell.</p>'
        self.assertIn("answer_first", rules(page(hidden)))
        self.assertEqual(rules(page(hidden.replace(" hidden", ""))), [])

    def test_a_commented_out_inline_width_is_not_read(self) -> None:
        self.assertIn("type", rules(page(LEAD + '<div style="width: 900px">Wide</div>')))
        self.assertNotIn("type", rules(page(LEAD + '<div style="/* width: 900px; */ max-width: 100%">Wide</div>')))

    def test_a_source_line_break_inside_a_sentence_is_not_a_new_line(self) -> None:
        self.assertNotIn("visuals", rules(page(LEAD + "<p>The diagram uses the\n<strong>flowchart TD</strong> layout from the guide.</p>")))
        self.assertIn("visuals", rules(page(LEAD + "<pre>Draft:\nflowchart TD\n A --&gt; B</pre>")), "inside pre, source lines are lines")

    def test_font_sizes_inside_media_rules_count(self) -> None:
        phone = "<style>@media (max-width: 600px) { body { font-size: 9px } }</style>"
        messages = " ".join(message for _, message in checker.check_page(page(LEAD, head=phone)))
        self.assertIn("Body text is 9px", messages)
        self.assertIn("as small as 9px", messages)
        readable = "<style>@media (max-width: 600px) { body { font-size: 16px } }</style>"
        self.assertNotIn("type", rules(page(LEAD, head=readable)))

    def test_encoded_fragments_land_on_their_section(self) -> None:
        sections = '<h2 id="cafés">Cafés</h2><p>a</p>' + "".join(f'<h2 id="s{i}">Part {i}</h2><p>b</p>' for i in range(4))
        nav = '<nav class="toc"><a href="#caf%C3%A9s">Cafés</a>' + "".join(f'<a href="#s{i}">Part {i}</a>' for i in range(4)) + "</nav>"
        self.assertNotIn("navigation", rules(page(LEAD + nav + sections)))

    def test_stacking_needs_the_phone_rule_not_just_the_class(self) -> None:
        stacked = ('<div class="table-wrap"><table class="stack"><tr><td>a</td><td data-label="One">1</td><td data-label="Two">2</td>'
                   '<td data-label="Three">3</td></tr></table></div>')
        self.assertIn("type", rules(page(LEAD + stacked)), "no narrow-screen rule, so nothing stacks")
        cards = "<style>@media (max-width: 600px) { table.stack td { display: block; } }</style>"
        self.assertNotIn("type", rules(page(LEAD + stacked, head=cards)))

    def test_dark_mode_rules_are_checked_for_literal_colour_pairs(self) -> None:
        unreadable = "<style>@media (prefers-color-scheme: dark) { body { color: #222; background: #222 } }</style>"
        messages = " ".join(message for _, message in checker.check_page(page(LEAD, head=unreadable)))
        self.assertIn("(dark mode) sets #222 on #222 (1.0:1)", messages)

    def test_the_slide_deck_passes_the_slide_rules(self) -> None:
        deck = (SKILL / "templates" / "slide-deck.html").read_text(encoding="utf-8")
        self.assertEqual(checker.check_page(deck, "slides"), [])
        self.assertEqual(sorted({rule for rule, _ in checker.check_page(deck.replace("</body>", '<pre class="mermaid">x</pre></body>'), "slides")}), ["visuals"])

if __name__ == "__main__":
    unittest.main()
