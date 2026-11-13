"""Hunt 19, Help search: Up and Down walk the results (Up from the first returns to the box), and the "/" chip is not drawn while
single-key shortcuts are off (the key does nothing then). Real Chrome, 1400 and 900."""
import unittest

import test_help_nav_page as N
from test_help_nav_page import set_size, SIZES


class SearchKeys(N.Nav):
    def test_arrows_walk_the_results_and_up_returns_to_the_box(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            for w in SIZES:
                set_size(cdp, p, w)
                p.js("var q=document.querySelector('#hpQ'); q.focus(); q.select()")
                p.type("keys")
                p.until("document.querySelectorAll('#hpRes a.hp-r').length > 1", "results")
                p.key("ArrowDown", code="ArrowDown", vk=40)
                first = p.js("document.activeElement.dataset.hit")
                p.key("ArrowDown", code="ArrowDown", vk=40)
                second = p.js("document.activeElement.dataset.hit")
                self.assertTrue(first and second and first != second, f"{w}: Down moves to the next result")
                self.assertEqual(p.js("[...document.querySelectorAll('#hpRes a.hp-r')].indexOf(document.activeElement)"), 1)
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js("document.activeElement.dataset.hit"), first, f"{w}: Up goes back one")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js("document.activeElement.id"), "hpQ", f"{w}: Up from the first result returns to the box")

    def test_slash_chip_is_not_drawn_when_single_keys_are_off(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            for w in SIZES:
                set_size(cdp, p, w)
                self.assertEqual(p.js("!!document.querySelector('#hpQk')"), True, f"{w}: on: the chip is there")
            p.js("localStorage.setItem('clark.single-keys','off')")
            p.js("location.reload()")
            p.ready()
            from test_help_panel import full_help_from_menu
            full_help_from_menu(p)
            for w in SIZES:
                set_size(cdp, p, w)
                self.assertEqual(p.js("!!document.querySelector('#hpQk')"), False, f"{w}: off: no chip for a key that does nothing")
                self.assertEqual(p.js("document.querySelector('#hpQ').getAttribute('aria-describedby')"), None)


if __name__ == "__main__":
    unittest.main()
