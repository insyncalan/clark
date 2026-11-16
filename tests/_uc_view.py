"""Test helper (row 1234): keep the Use case summary's view settings in the usecases section's body, the one place the page reads them."""
import json


def put_view(test, view):
    """Write `view` (a dict such as {"n": 4, "scroll": False, "tracker": "off"}, or None for an empty body) into the project ABC usecases section's body."""
    ref = next(r["id"] for r in test.store.read("report_sections", "ABC") if r["type"] == "usecases")
    # The store does not yet accept a body on a usecases section (store._section_rules), so the test writes the column itself; the server sends the column as it is.
    with test.store.con:
        test.store.con.execute("UPDATE report_sections SET body = ? WHERE id = ?", ("" if view is None else json.dumps(view), ref))
    return ref
