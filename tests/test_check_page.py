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

    def test_section_nav_covers_every_section(self) -> None:
        sections = "".join(f'<h2 id="s{i}">Part {i}</h2><p>Short.</p>' for i in range(5))
        partial = '<nav class="toc">' + "".join(f'<a href="#s{i}">Part {i}</a>' for i in range(3)) + "</nav>"
        messages = " ".join(message for _, message in checker.check_page(page(LEAD + partial + sections)))
        self.assertIn("leaves out 'Part 3', 'Part 4'", messages)
        full = '<nav class="toc">' + "".join(f'<a href="#s{i}">Part {i}</a>' for i in range(5)) + "</nav>"
        self.assertNotIn("navigation", rules(page(LEAD + full + sections)))

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
