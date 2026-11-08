"""#457: an action's Latest update (the peek's field) is published only where the action itself is. Real `publish.build` and the
real change route (`changes.make_change`), no mock. The same text on a plain client-visible action appears in the published file;
on a Sensitive-labelled, report-hidden (eye off in the report), non-client-visible or archived action it never does. All rows are
fictional.

Run: python3 dev/run_tests.py test_latest_update_publish
"""
import unittest

from _demo import USER, DemoStore
from clark import changes, publish


class LatestUpdatePublished(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)

    def make(self, kind):
        """An action with a Latest update set through the real change route; returns (ref, token)."""
        token = f"zz-latest-token-{kind}"
        ref = self.demo.action(description=f"Action for {kind}")
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": ref,
                                    "changes": {"latest_update": token}, "place": "peek"})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.s.read("actions", ref=ref)["latest_update"], f"<p>{token}</p>")      # row 1005: stored as the editor's HTML
        return ref, token

    def published(self):
        return publish.build(self.s, "ABC", now="2026-10-29")["body"].decode("utf-8")

    def test_a_plain_client_visible_action_publishes_its_latest_update(self):
        ref, token = self.make("plain")
        self.assertEqual(self.s.read("actions", ref=ref)["client_visible"], 1)
        self.assertIn(token, self.published())

    def test_a_sensitive_labelled_action_does_not(self):
        ref, token = self.make("sensitive")
        with self.s.step("dashboard", USER) as st:
            st.create("item_labels", {"item_id": ref, "label": "Sensitive"})
        self.assertNotIn(token, self.published())

    def test_a_report_hidden_action_does_not(self):
        ref, token = self.make("hidden")
        with self.s.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": ref})
        self.assertNotIn(token, self.published())

    def test_a_not_client_visible_action_does_not(self):
        ref, token = self.make("eyeoff")
        with self.s.step("dashboard", USER) as st:
            st.update("actions", ref, {"client_visible": 0})
        self.assertNotIn(token, self.published())

    def test_an_archived_action_does_not(self):
        ref, token = self.make("archived")
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", ref)
        self.assertNotIn(token, self.published())

    def test_the_gates_are_the_only_difference(self):
        """One body, all five at once: only the plain action's text is in it."""
        made = {k: self.make(k) for k in ("plain", "sensitive", "hidden", "eyeoff", "archived")}
        with self.s.step("dashboard", USER) as st:
            st.create("item_labels", {"item_id": made["sensitive"][0], "label": "Sensitive"})
            st.create("report_hidden", {"project": "ABC", "item_id": made["hidden"][0]})
            st.update("actions", made["eyeoff"][0], {"client_visible": 0})
            st.archive("actions", made["archived"][0])
        body = self.published()
        self.assertIn(made["plain"][1], body)
        for k in ("sensitive", "hidden", "eyeoff", "archived"):
            self.assertNotIn(made[k][1], body, k)


if __name__ == "__main__":
    unittest.main()
