"""Row 1572 AP5 (row 1295 AP13): the whole slash command editor page works in light and in dark, at 1400 and 900.

Run: python3 dev/run_tests.py test_slash_themes_1295
In each of the four combinations the list, the fields, the live preview, Test it, the placeholders popup and the AI check card are on the page, nothing scrolls sideways, and every
label's text colour has a contrast ratio of at least 4.5 to 1 against the colour behind it. Chrome is required: fails, never skips."""
from test_server import chrome
from test_slash_editor_1295 import Base, EDITOR, EditorStates

CONTRAST = r"""(()=>{const lum=(c)=>{const m=c.match(/[\d.]+/g).map(Number).slice(0,3).map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4);});return .2126*m[0]+.7152*m[1]+.0722*m[2];};
  const els=[...document.querySelectorAll('#slash-page label, #slash-page .slash-lab, #slash-page h1, #slash-page h3, #slash-page .muted, #slash-page .slash-pickers button, #slash-page .btn')].filter(e=>e.offsetHeight>0&&e.textContent.trim()&&!e.disabled);
  const r=els.map(el=>{let bg=null;for(let e=el;e&&!bg;e=e.parentElement){const c=getComputedStyle(e).backgroundColor;if(!/rgba\(.*, 0\)|transparent/.test(c))bg=c;}
    const a=lum(getComputedStyle(el).color),b=lum(bg||'rgb(255,255,255)');return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);});return r.length?Math.min(...r):0;})()"""


# Row 1572: when the lowest label is below 4.5, say WHICH element it is, its colour and the colour behind it (a hand run on a Mac read 2.318, the light muted colour on the dark page, and the log named nothing).
WHO = CONTRAST.replace("const r=els.map", "const bgs=[];const r=els.map").replace("const a=lum", "bgs.push(bg);const a=lum").replace("return r.length?Math.min(...r):0;", "const i=r.indexOf(Math.min(...r));return els.length?[els[i].tagName+'.'+els[i].className+'#'+els[i].id, getComputedStyle(els[i]).color, 'behind '+bgs[i], r[i].toFixed(2), document.documentElement.dataset.theme||'', getComputedStyle(document.body).color]:[];")


class SlashThemes(Base):
    def test_the_editor_reads_in_light_and_dark_at_1400_and_900(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    js = EditorStates.open_at(self, cdp, width, dark, EDITOR + "&new=1")
                    self.until(js, "!!document.querySelector('.slash-edit-card')", "the card")
                    self.click(js, "#slash-help")
                    self.until(js, "!!document.querySelector('#slash-pop')", "the placeholders popup")
                    for sel in (".slash-side button", "#sl-name", "#sl-menu", "#sl-text", ".slash-preview", "#slash-test", "#slash-check", "#slash-ai", "#slash-pop"):
                        self.assertTrue(js(f"!!document.querySelector({sel!r}) && document.querySelector({sel!r}).offsetHeight > 0"), sel)
                    self.assertTrue(js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                    # the dark tokens are set by script and read at once: wait until no colour is still changing (document.getAnimations is empty)
                    self.until(js, "document.getAnimations().length === 0", "no colour is still changing", 10)
                    self.assertGreaterEqual(js(CONTRAST), 4.5, "the lowest label contrast; element, its colour, the colour behind it, ratio, theme, body colour: %r" % (js(WHO),))

    # Row 1572: the buttons change colour at once with the theme (no colour fade to read mid-way) and keep the press movement's fade (transform), Classic
    def test_the_buttons_have_no_colour_fade_and_keep_the_transform_fade_at_1400_and_900(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    js = EditorStates.open_at(self, cdp, width, dark, EDITOR + "&new=1")
                    self.until(js, "!!document.querySelector('#slash-cancel')", "the Cancel button")
                    got = js("[...document.querySelectorAll('#slash-page button')].map(b => b.id + '/' + b.className + ':' + getComputedStyle(b).transitionProperty)")
                    self.assertTrue(got, "the page has buttons")
                    for g in got:
                        self.assertTrue(g.endswith(":transform"), f"{width} dark={dark}: only transform may fade: {g!r} in {got!r}")
