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
                    self.assertGreaterEqual(js(CONTRAST), 4.5, "the lowest label contrast")
