"""#180, #440: the seam of GET and POST /api/profile, Settings › Profile: this person's name, alias, email, phone number and organisation,
kept in the data folder's settings.json (settings.py) and nowhere else. The page asks for them when it opens Settings or the menu,
and saves them when a box is left. The name is also the name on each change (`who()`), with the login name when none was typed;
the email is only used to tell which addresses are the person's own (`own_domains()`); the alias, phone number and organisation
are kept and shown back in Settings, and nothing else reads them. Nothing is read from the computer, the browser or the Claude
sign-in, and clark sends no mail. Standard library only, Python 3.9."""
import threading

from clark import platform, settings

KEYS = ("name", "email")                         # always sent
OPTIONAL = ("alias", "phone", "org")             # sent by the Profile card; one left out stays as it was saved
BAD = "That could not be read. Reload the page and try again. Nothing was saved."


class Profile:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.lock = threading.Lock()                 # two windows saving at once take turns; the file is replaced whole each time

    def get(self):
        """(200, {"ok": true, "name", "alias", "email", "phone", "org"}): what was saved, "" for each that was not."""
        return 200, {"ok": True, **settings.profile(self.data_dir)}

    def save(self, req):
        """Save {"name", "email"} and, optionally, "alias", "phone" and "org" (each text, any may be empty; one left out stays as saved):
        (200, {"ok": true, name, alias, email, phone, org}), or (400, a refusal in plain words ending "Nothing was saved."); a refusal
        writes nothing."""
        if (not isinstance(req, dict) or not set(KEYS) <= set(req) or not set(req) <= set(KEYS + OPTIONAL)
                or not all(isinstance(v, str) for v in req.values())):
            return 400, {"ok": False, "message": BAD, "code": "bad_request"}
        with self.lock:
            try:
                saved = settings.set_profile(self.data_dir, req["name"], req["email"], req.get("alias"), req.get("phone"), req.get("org"))
            except ValueError as e:
                return 400, {"ok": False, "message": str(e), "code": "refused"}
        return 200, {"ok": True, **saved}

    def who(self):
        """The name for `by_user`: the saved name, else the login name."""
        return settings.profile(self.data_dir)["name"] or platform.login_name()

    def own_domains(self):
        """The domain of the saved email, as a list (empty when there is none): the addresses that count as the person's own."""
        email = settings.profile(self.data_dir)["email"]
        return [email.rsplit("@", 1)[1].lower()] if email else []
