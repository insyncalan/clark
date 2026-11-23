"""The camera-details sentence names the picture button; its words are one constant, pinned to the label in the page."""
import os
import re
import unittest

from clark.section_kinds.textimage import ADD_PICTURE_BUTTON, CAMERA_DETAILS

JSX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "clark", "page", "src", "edit", "templates", "pictureEdit.jsx")


class PictureButtonWords(unittest.TestCase):
    def test_the_sentence_is_built_from_the_button_words(self):
        self.assertIn("with " + ADD_PICTURE_BUTTON + ", which removes them.", CAMERA_DETAILS)
        self.assertTrue(CAMERA_DETAILS.startswith("That image still carries details from the camera"))

    def test_the_button_in_the_page_says_the_same_words(self):
        with open(JSX, encoding="utf-8") as f:
            jsx = f.read()
        labels = re.findall(r'\{pic \? "Change picture" : "([^"]+)"\}', jsx)
        self.assertEqual(labels, [ADD_PICTURE_BUTTON])


if __name__ == "__main__":
    unittest.main()
