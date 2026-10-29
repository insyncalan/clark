"""Copy app.css into app-css.js, so the published page can take its look from the same rules as the editor.

Usage: python3 build_css.py   (run_selftest.py runs it first; run it after any change to app.css)
A page opened from a file cannot read its own stylesheet's rules, so publishing reads this copy instead.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    css = (HERE / "app.css").read_text(encoding="utf-8")
    (HERE / "app-css.js").write_text("/* made by build_css.py from app.css: do not edit */\nwindow.CLARK_APPCSS = " + json.dumps(css) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
