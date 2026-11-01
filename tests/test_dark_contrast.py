"""#108, #186: the dark-mode brand colour (a light violet) keeps its button text readable (WCAG AA) and stays visible on dark surfaces.

Run: python3 dev/run_tests.py test_dark_contrast

Computed from the committed tokens (and the built page), never hard-coded ratios.
"""
import re
import unittest

from _paths import ROOT

TOKENS = ROOT / "src" / "clark" / "brand" / "tokens.css"
PAGE = ROOT / "src" / "clark" / "page" / "page.html"


def dark_blocks(css):
    """Every dark token block: the data-theme=dark one and the one inside the prefers-color-scheme media query.

    Each is {name: '#RRGGBB'}. A page can carry more than one copy, so tests must check them all.
    """
    blocks = re.findall(r":root\[data-theme=(?:dark|auto)\]\s*\{(.*?)\n\s*\}", css, re.S)
    return [{n: v.upper() for n, v in re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", b)} for b in blocks]


def dark_tokens(css):
    """The first dark block (kept for the single-value checks); see dark_blocks for all of them."""
    return dark_blocks(css)[0]


def luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def blend(top, bottom, alpha):
    """The colour of `top` drawn at `alpha` over `bottom`, as '#RRGGBB'."""
    return "#" + "".join("%02X" % round(int(top[i:i + 2], 16) * alpha + int(bottom[i:i + 2], 16) * (1 - alpha)) for i in (1, 3, 5))


# ---- reading the shipped CSS (#431) ------------------------------------------------------------------------------------------------------------------
# The section control's colours are read from the CSS the page ships, never written into the test: the light token block, then each rule the
# control uses, with var() followed through the tokens. A change to a token or a rule moves what the test sees.

CONTROL_FLOOR = 3.0      # WCAG 1.4.11: a control's icon against what it sits on
SHELL = ROOT / "src" / "clark" / "page" / "shell.css"
VIEW_PAGE = ROOT / "src" / "clark" / "page" / "page-view.html"


def shipped_css(path):
    """The CSS in a file, comments removed: a page's own <style> block, or a .css file as it is."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".html":
        text = re.search(r"<style[^>]*>(.*?)</style>", text, re.S).group(1)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def css_rules(css):
    """Every rule as (conditions, selectors, {property: value}); conditions are the enclosing @media/@supports preludes, outermost first."""
    rules, stack, start = [], [], 0
    for i, ch in enumerate(css):
        if ch == "{":
            stack.append(css[start:i].strip())
            start = i + 1
        elif ch == "}":
            body = css[start:i]
            if body.strip() and not body.rstrip().endswith("}"):
                prelude = stack[-1]
                declarations = {}
                for name, value in re.findall(r"(?:^|;)\s*([\w-]+)\s*:\s*([^;]+)", body):
                    declarations[name.strip()] = value.strip()
                if not prelude.startswith("@"):
                    rules.append((tuple(stack[:-1]), [x.strip() for x in prelude.split(",")], declarations))
            stack.pop()
            start = i + 1
    return rules


def light_tokens(rules):
    """The light theme's custom properties: every plain `:root { ... }` block, later ones over earlier."""
    tokens = {}
    for conditions, selectors, declarations in rules:
        if not conditions and selectors == [":root"]:
            tokens.update({k: v for k, v in declarations.items() if k.startswith("--")})
    return tokens


def resolve(value, tokens):
    """A value with every var(--name, fallback) replaced by the token's value (or the fallback), followed through chains."""
    for _ in range(20):
        match = re.search(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*(?:\([^()]*\)[^()]*)*))?\)", value)
        if not match:
            return value.strip()
        name, fallback = match.group(1), match.group(2)
        found = tokens.get(name, fallback)
        if found is None:
            raise AssertionError("%s has no value and no fallback, in %r" % (name, value))
        value = value[:match.start()] + found.strip() + value[match.end():]
    raise AssertionError("var() chain does not end: %r" % value)


def last_declared(rules, selector, prop, conditions=()):
    """The value `prop` has in the last rule that lists exactly `selector` (not its :hover or other states), under exactly these conditions."""
    found = None
    for rule_conditions, selectors, declarations in rules:
        if rule_conditions == tuple(conditions) and selector in selectors and prop in declarations:
            found = declarations[prop]
    return found


def to_hex(colour, what):
    colour = colour.strip().upper()
    if re.fullmatch(r"#[0-9A-F]{3}", colour):
        colour = "#" + "".join(c * 2 for c in colour[1:])
    assert re.fullmatch(r"#[0-9A-F]{6}", colour), "%s is %r: this test reads #RGB or #RRGGBB" % (what, colour)
    return colour


def section_control_at_900_px_in_light(css):
    """What the section control shows at rest at 900 px in Edit in light, from the CSS given (see shipped_css).

    Returns (alpha, {icon name: its colour}, {what it sits on: colour}). The icons are the grip (.handle) and the + (.plus); the control paints no
    background of its own, so it sits on the card (.frame, --surface) inside the page (body).
    """
    rules = css_rules(css)
    tokens = light_tokens(rules)
    opacity = last_declared(rules, ".sec-ctl", "opacity")
    assert opacity, "no .sec-ctl rule sets its opacity"
    narrow = (last_declared(rules, "#report[data-mode=\"edit\"] .sec > .sec-ctl", "--sh-rest", ("@media (max-width: 900px)",))
              or last_declared(rules, "#report[data-mode=\"edit\"] .sec.slot-right > .sec-ctl", "--sh-rest", ("@media (max-width: 900px)",)))
    assert narrow, "no 900 px rule sets --sh-rest on the section control"
    scope = dict(tokens, **{"--sh-rest": resolve(narrow, tokens)})
    alpha = float(resolve(opacity, scope))
    icons = {}
    for icon in (".handle", ".plus"):
        colour = last_declared(rules, icon, "color")
        assert colour, "no rule sets the colour of %s" % icon
        icons[icon] = to_hex(resolve(colour, tokens), "the colour of " + icon)
        own = last_declared(rules, icon, "background") or last_declared(rules, icon, "background-color")
        assert own in (None, "transparent", "none"), "%s now paints a background (%r); this test needs to read it" % (icon, own)
    card = last_declared(rules, ".frame", "background") or last_declared(rules, ".frame", "background-color")
    ground = last_declared(rules, "body", "background") or last_declared(rules, "body", "background-color")
    assert card and ground, "the card (.frame) and the page (body) must each set a background"
    behind = {"the card": to_hex(resolve(card, tokens), "the card's background"), "the page": to_hex(resolve(ground, tokens), "the page's background")}
    return alpha, icons, behind


class SectionControlAtRest(unittest.TestCase):
    def test_in_light_at_900_px_the_icons_are_at_least_3_to_1_on_the_card_and_on_the_page(self):
        """#431: the real colours, read from the CSS each file ships (the built pages, and tokens.css with shell.css as the source), drawn at the
        opacity the 900 px rule gives, are at least 3:1 (WCAG 1.4.11) on the card and on the page, and keep #285's 4.5:1 on the card."""
        pages = ROOT / "src" / "clark" / "page"
        for label, css in (("page.html", shipped_css(pages / "page.html")), ("page-view.html", shipped_css(VIEW_PAGE)),
                           ("tokens.css + shell.css", shipped_css(TOKENS) + "\n" + shipped_css(SHELL))):
            with self.subTest(label):
                self.check_light(*section_control_at_900_px_in_light(css))

    def check_light(self, alpha, icons, behind):
        for icon, colour in icons.items():
            for place, backdrop in behind.items():
                shown = ratio(blend(colour, backdrop, alpha), backdrop)
                self.assertGreaterEqual(shown, CONTROL_FLOOR, "%s %s on %s at %s" % (icon, colour, place, alpha))
            self.assertGreaterEqual(ratio(blend(colour, behind["the card"], alpha), behind["the card"]), 4.5, "%s on the card, text level" % icon)

    def test_in_dark_at_900_px_the_icon_reads_at_text_level_contrast(self):
        """#285: in each dark block the --text-muted icon at --sh-rest-narrow (.75) on the card (--surface) is at least 4.5:1."""
        css = TOKENS.read_text(encoding="utf-8")
        dark = re.findall(r"--sh-rest-narrow:\s*([.\d]+)", css)
        self.assertEqual(len(dark), 3, "light, dark and following a dark computer")
        for block, a in zip(dark_blocks(css), dark[1:]):
            self.assertGreaterEqual(ratio(blend(block["--text-muted"], block["--surface"], float(a)), block["--surface"]), 4.5, "dark")

    def test_the_shell_reads_the_token_at_900_px_and_below(self):
        shell = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        self.assertRegex(shell, r"@media \(max-width: 900px\)[^\n]*--sh-rest: var\(--sh-rest-narrow")


class DarkBrandBlue(unittest.TestCase):
    def test_every_dark_block_is_read_and_has_the_new_blue(self):
        for label, path in (("tokens", TOKENS), ("page", PAGE)):
            blocks = dark_blocks(path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(blocks), 2, label)
            for block in blocks:
                self.assertEqual(block["--brand-blue"], "#8F7BFF", label)
                self.assertEqual(block["--status-blue"], "#8F7BFF", label)

    def test_offline_page_uses_the_new_blue(self):
        text = (ROOT / "src" / "clark" / "app" / "offline.html").read_text(encoding="utf-8")
        self.assertNotIn("5B7BF5", text.upper())

    def test_border_use_is_visible_on_surface_and_on_grey_200(self):
        """The light violet is well over 3:1 on the dark surface and on grey-200 (#108's limit, a blue under 3:1 there, no longer applies)."""
        for block in dark_blocks(TOKENS.read_text(encoding="utf-8")):
            self.assertGreaterEqual(ratio(block["--brand-blue"], block["--surface"]), 3.0)
            self.assertGreaterEqual(ratio(block["--brand-blue"], block["--grey-200"]), 3.0)

    def setUp(self):
        self.dark = dark_tokens(TOKENS.read_text(encoding="utf-8"))

    def test_button_text_on_the_brand_colour_passes_aa(self):
        """In dark mode the text on the brand colour is the dark --text-on-brand (white is under 3:1 on the light violet)."""
        for block in dark_blocks(TOKENS.read_text(encoding="utf-8")):
            self.assertGreaterEqual(ratio(block["--text-on-brand"], block["--brand-blue"]), 4.5)
            self.assertLess(ratio("#FFFFFF", block["--brand-blue"]), 4.5, "white would not do, which is why the token is dark here")

    def test_blue_as_ring_or_border_stays_visible_on_dark_surfaces(self):
        for name in ("--surface", "--grey-50", "--grey-100"):
            self.assertGreaterEqual(ratio(self.dark["--brand-blue"], self.dark[name]), 3.0, name)

    def test_link_and_pill_text_colour_is_unchanged(self):
        self.assertEqual(self.dark["--status-blue-text"], "#B7A9FF")

    def test_built_page_carries_the_same_dark_blue(self):
        pages = dark_blocks(PAGE.read_text(encoding="utf-8"))
        want = dark_blocks(TOKENS.read_text(encoding="utf-8"))
        self.assertEqual(len(pages), len(want))
        for page, tok in zip(pages, want):
            for name in ("--brand-blue", "--status-blue", "--status-blue-text"):
                self.assertEqual(page[name], tok[name], name)


if __name__ == "__main__":
    unittest.main()
