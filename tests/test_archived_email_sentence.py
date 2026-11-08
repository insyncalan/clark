"""One sentence for an archived project in the Draft email: the draft refusal and the "I sent it" refusal share it."""
import unittest

from clark import draft_email_feed, store


class ArchivedEmailSentence(unittest.TestCase):
    def test_one_shared_sentence(self):
        self.assertTrue(hasattr(store, "EMAIL_PROJECT_ARCHIVED"))
        self.assertEqual(draft_email_feed.ARCHIVED, store.EMAIL_PROJECT_ARCHIVED)

    def test_sent_refusal_is_that_sentence_plus_nothing_saved(self):
        src = open(store.__file__, encoding="utf-8").read()
        self.assertIn('f"{EMAIL_PROJECT_ARCHIVED} Nothing was saved."', src)
        self.assertEqual(src.count("no email can be drafted for it"), 1)

    def test_draft_feed_has_no_second_copy(self):
        src = open(draft_email_feed.__file__, encoding="utf-8").read()
        self.assertNotIn("no email can be drafted for it", src)


if __name__ == "__main__":
    unittest.main()
