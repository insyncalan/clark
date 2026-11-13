import json, os, unittest
P = os.path.join(os.path.dirname(__file__), "..", "src", "clark", "page", "src", "help", "helpContent.json")


class T(unittest.TestCase):
    def setUp(self):
        self.t = open(P, encoding="utf-8").read()

    def test_spacing_not_alone(self):
        self.assertNotIn("which is yours alone", self.t)
        self.assertIn("used on the published report too; Appearance, below, is yours alone", self.t)

    def test_mode_keys_gantt(self):
        self.assertNotIn("Works on the Dashboard only", self.t)
        self.assertEqual(self.t.count("Dashboard and the Gantt page only"), 2)


if __name__ == "__main__":
    unittest.main()
