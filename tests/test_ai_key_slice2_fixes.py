"""#643 slice 2, small findings from the slice 1 reads: (b) post_json does not keep the headers in
its frame, (c) an Anthropic key is refused for OpenAI, (d) the deadline's limit is written down.

Run: python3 dev/run_tests.py test_ai_key_slice2_fixes
"""
import os
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import ai_https as h, ai_keychain as k
from test_ai_https import Conn, KEY as HTTPS_KEY, PATH, seam
from test_ai_keychain import CLAUDE, OPENAI


class AnAnthropicKeyIsNotAnOpenAIKey(unittest.TestCase):
    def test_it_is_refused_for_openai_with_the_prefix_code(self):
        for key in ("sk-ant-api03-" + "A1b2C3d4" * 4, "sk-ant-" + "a" * 20):
            self.assertEqual(k.valid_shape("openai", key), k.REFUSAL_CODES["wrong_prefix"])
            self.assertIn(k.valid_shape("openai", key), k.REFUSAL_CODES.values())

    def test_the_real_shapes_still_pass(self):
        self.assertIsNone(k.valid_shape("openai", OPENAI))
        self.assertIsNone(k.valid_shape("openai", "sk-" + "a" * 30))
        self.assertIsNone(k.valid_shape("claude", CLAUDE))

    def test_save_key_refuses_it_before_the_keychain_is_touched(self):
        with mock.patch.object(k, "run_security") as run, mock.patch.object(k.platform, "system", return_value=k.platform.MAC), \
                mock.patch.object(k.platform, "container_mode", return_value=False):
            with self.assertRaises(k.KeyRefused):
                k.save_key("openai", CLAUDE)
        run.assert_not_called()


class TheHeadersAreNotLeftInTheFrame(unittest.TestCase):
    def frames(self, exc):
        found, tb = [], exc.__traceback__
        while tb:
            if os.path.basename(tb.tb_frame.f_code.co_filename) == "ai_https.py":
                found.append((tb.tb_frame.f_code.co_name, dict(tb.tb_frame.f_locals)))
            tb = tb.tb_next
        return found

    def test_no_ai_https_frame_in_the_traceback_holds_the_headers(self):
        for conn in (Conn(error=OSError("x"), where="request"), Conn(error=OSError("x"), where="getresponse")):
            try:
                h.post_json("api.anthropic.com", PATH, {"x-api-key": HTTPS_KEY}, b"{}", connect=seam(conn))
            except h.HttpsError as caught:
                frames = self.frames(caught)
            self.assertTrue(frames)
            for name, local in frames:
                self.assertNotIn("headers", local, name)
                self.assertNotIn(HTTPS_KEY, repr(local), name)

    def test_a_good_call_still_sends_them(self):
        conn = Conn()
        h.post_json("api.openai.com", PATH, {"authorization": "Bearer x"}, b"{}", connect=seam(conn))
        self.assertEqual(conn.sent[3], {"authorization": "Bearer x"})

    def test_the_docstring_says_the_deadline_is_between_chunks_and_a_blocked_read_can_pass_it(self):
        self.assertIn("checked between chunks", h.__doc__)
        self.assertIn("one blocked read can run past the deadline", h.__doc__)


if __name__ == "__main__":
    unittest.main()
