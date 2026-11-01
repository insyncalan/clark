"""#329: what the ask screen covers, driven through the real /api/ask route with a recording provider.

A password typed into a row of the project's own data (an action's latest update) is not sent as a passage; every earlier turn is
screened whoever the page says it is from; URL-encoded and base64 password text is refused; the screen runs before any of the
project's data is read for the question; the refusal says a password or a key. Secrets are built at run time. Fictional data only.

Run: python3 dev/run_tests.py test_ask_screen_order
"""
import base64
import unittest
import urllib.parse
from unittest import mock

import test_ask_route as route
from clark import ask, ask_service, store as st

PW = "Welcome" + "2026!"
LINE = "pass" + "word: " + PW
B64_ONLY = base64.b64encode(("pass" + "word: Summer" + "2026x").encode()).decode()      # only the base64 reading catches this
KEY = "sk-" + "ant-api03-" + "a1B2c3D4e5F6g7H8i9J0" + "-xyz"


class Rows(route.Base):
    def plant(self, update, kind="actions", field="latest_update", extra=None):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                row = {"project": route.CODE, "description": "Order the ZQ-SCREEN-ROW chairs", "raised": "2026-10-01",
                       "source": "demo", field: update, **(extra or {})}
                s.create(kind, row)
        finally:
            store.close()

    def sent(self, q="Tell me everything about every action, risk, decision and milestone."):
        status, got = self.question(q)
        self.assertEqual(status, 200, got)
        return got, self.provider.sent[-1]

    def test_a_password_in_an_actions_latest_update_is_not_sent(self):
        self.plant("Spoke to the vendor. " + LINE)
        got, text = self.sent()
        self.assertNotIn(PW, text)
        self.assertNotIn(LINE, text)
        self.assertNotIn(PW, repr(got))
        self.assertNotIn("ZQ-SCREEN-ROW", text, "the passage holding it is left out, not edited")
        self.assertIn(ask.secret_note(1), got["notes"])

    def test_a_key_in_a_clients_message_is_not_sent(self):
        self.plant("On hold", field="client_message", extra={"latest_update": "Use " + KEY + " for the feed"})
        got, text = self.sent()
        self.assertNotIn(KEY, text)
        self.assertNotIn("ZQ-SCREEN-ROW", text)

    def test_a_url_encoded_or_base64_password_in_a_row_is_not_sent(self):
        for n, update in enumerate((urllib.parse.quote(LINE, safe=""), base64.b64encode(LINE.encode()).decode())):
            self.plant(update)
            _got, text = self.sent()
            self.assertNotIn(update, text, n)
            self.assertNotIn("ZQ-SCREEN-ROW", text, n)

    def test_with_no_secret_nothing_is_left_out_and_there_is_no_note(self):
        got, text = self.sent()
        self.assertNotIn(ask.secret_note(1), got["notes"])
        self.assertIn("ZQ-KEEP-RISK-1", text)


class Turns(route.Base):
    def test_an_assistant_turn_with_a_password_is_refused(self):
        for role in ("user", "assistant"):
            self.provider.sent.clear()
            status, got = self.question("And now?", earlier=[{"role": role, "text": "Noted: " + LINE}])
            self.assertEqual((status, got["code"], got["message"]), (400, "refused", ask.SECRET_EARLIER), role)
            self.assertEqual(self.provider.sent, [])
            self.assertNotIn(PW, repr(got))

    def test_an_ordinary_assistant_turn_still_goes(self):
        status, got = self.question("And now?", earlier=[{"role": "user", "text": "How is it?"},
                                                         {"role": "assistant", "text": "The plan is on track."}])
        self.assertEqual(status, 200, got)

    def test_url_encoded_and_base64_password_text_is_refused_on_the_route(self):
        for text in (urllib.parse.quote(LINE, safe=""), base64.b64encode(LINE.encode()).decode(), B64_ONLY):
            for kw in ({"q": text}, {"earlier": [{"role": "assistant", "text": text}]}):
                status, got = self.question(**({"q": kw["q"]} if "q" in kw else kw))
                self.assertEqual((status, got["code"]), (400, "refused"), text)
        self.assertEqual(self.provider.sent, [])


class Order(route.Base):
    def test_the_screen_runs_before_any_data_is_read_for_the_question(self):
        calls = []
        with mock.patch.object(ask_service.ask_data, "project_data", side_effect=lambda *a, **k: calls.append(a)), \
                mock.patch.object(ask_service.ask_passages, "folder_data", side_effect=lambda *a, **k: calls.append(a)):
            for kw in ({"q": "my " + LINE}, {"earlier": [{"role": "user", "text": LINE}]}):
                status, got = self.question(**kw)
                self.assertEqual((status, got["code"]), (400, "refused"))
        self.assertEqual(calls, [], "no data was ranked or read for a question that holds a secret")
        self.assertEqual(self.provider.sent, [])

    def test_asking_off_still_wins_over_the_screen(self):
        self.set_switch(False)
        status, got = self.question("my " + LINE)
        self.assertEqual((status, got["code"]), (409, "asking_off"))

    def test_the_route_names_a_password_or_a_key(self):
        status, got = self.question("my " + LINE)
        self.assertEqual(got["message"], ask.SECRET)
        status, got = self.question("use " + KEY)
        self.assertEqual(got["message"], ask.SECRET_KEY)
        self.assertNotIn("password", got["message"])
        status, got = self.question("And?", earlier=[{"role": "user", "text": "use " + KEY}])
        self.assertEqual(got["message"], ask.SECRET_EARLIER_KEY)


if __name__ == "__main__":
    unittest.main()
