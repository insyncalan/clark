"""Row 1556: the editor's own late focus must not take the focus back from the field a Tab moved it to.

Run: python3 dev/run_tests.py test_rich_focus_guard_1556
RichText asks tiptap to focus the editor, and tiptap runs view.focus() again in a later animation frame. The test holds that frame, opens the Who editor
of the Movement form, sends a real Tab, lets the held frame run at the moment the focus leaves the editor (before the editor's leave handler), and asserts
the focus stays on the next field and the editor closes. Made-up data only.
"""
import json

import test_movement_page as tmp
import test_b4_hostile_1005 as b4
from test_server import chrome, wait

HOLD = """(function(){
  window.__held = []; window.__real = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = function(cb){ window.__held.push(cb); return window.__held.length; };
  window.__release = function(){ var q = window.__held; window.__held = []; window.requestAnimationFrame = window.__real; q.forEach(function(cb){ cb(performance.now()); }); };
  // registered before the editor exists: runs before the editor's own leave handler and before its timer
  document.addEventListener('focusout', function(e){ if (e.target.closest && e.target.closest('.ProseMirror')) setTimeout(window.__release, 0); }, true);
})()"""


class Guard(tmp.Base):
    form, box = b4.Movement.form, b4.Movement.box

    def test_a_tab_before_the_late_focus_frame_keeps_the_focus_on_the_next_field(self):
        for width, theme in ((1400, "light"), (900, "dark")):
            with chrome() as cdp:
                p = self.form(cdp, width, theme)
                sel = json.dumps(self.box("who"))
                p.js(HOLD)
                p.js("document.getElementById('mv-who').click()")
                p.until("!!document.querySelector(%s)" % sel, "editor who")
                self.assertTrue(wait(lambda: p.js("document.hasFocus() && document.querySelector(%s).contains(document.activeElement)" % sel), 15), "caret in the editor")
                self.assertEqual(p.js("window.__held.length > 0"), True, "the editor's late focus frame is being held")
                p.key("Tab", code="Tab", vk=9)
                self.assertTrue(wait(lambda: p.js("window.__held.length === 0"), 10), "the held frame ran")
                p.js("new Promise(function(r){ requestAnimationFrame(function(){ requestAnimationFrame(r); }); })")
                self.assertTrue(wait(lambda: not p.js("!!document.querySelector(%s)" % sel), 10), "the editor closed on Tab")
                self.assertEqual(p.js("document.activeElement.id || document.activeElement.className"), "mv-reason", "the next field has the focus")
