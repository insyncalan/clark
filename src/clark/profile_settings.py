"""#180: the seam of GET and POST /api/profile, Settings › Profile › About you: this person's name and email, kept in the data folder's
settings.json (settings.py) and nowhere else. The page asks for both when it opens Settings or the menu, and saves them when a box is
left. The name is also the name on each change and each publication (`who()`), with the login name when none was typed; the email is
only used to tell which addresses are the person's own (`own_domains()`). Nothing is read from the computer, the browser or the Claude
sign-in, and clark sends no mail. Standard library only, Python 3.9."""
import threading

from clark import platform, settings

KEYS = ("name", "email")
OPTIONAL = ("alias",)                                # item 613: the Alias may be left out, and then the one saved is kept
FIELD_OF = {settings.NAME_BAD: "name", settings.NAME_TOO_LONG: "name", settings.EMAIL_BAD: "email",
            settings.ALIAS_BAD: "alias", settings.ALIAS_TOO_LONG: "alias"}
BAD = "That could not be read. Reload the page and try again. Nothing was saved."


class Profile:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.lock = threading.Lock()                 # two windows saving at once take turns; the file is replaced whole each time

    def get(self):
        """(200, {"ok": true, "name", "email", "alias"}): what was saved, "" for each that was not."""
        return 200, {"ok": True, **settings.profile(self.data_dir)}

    def save(self, req):
        """Save {"name", "email"} and, when it is sent, "alias" (each text, any may be empty; an Alias left out keeps the one saved):
        (200, {"ok": true, name, email, alias}), or (400, a refusal in plain words ending "Nothing was saved."); a refusal writes
        nothing."""
        if (not isinstance(req, dict) or not set(KEYS) <= set(req) <= set(KEYS + OPTIONAL)
                or not all(isinstance(req[k], str) for k in req)):
            return 400, {"ok": False, "message": BAD, "code": "bad_request"}
        with self.lock:
            try:
                saved = settings.set_profile(self.data_dir, req["name"], req["email"], req.get("alias"))
            except ValueError as e:
                reply = {"ok": False, "message": str(e), "code": "refused"}
                field = FIELD_OF.get(str(e))
                if field:
                    reply["field"] = field            # the box the refusal is about (a save carries both boxes)
                return 400, reply
        return 200, {"ok": True, **saved}

    def who(self):
        """The name for `by_user`: the saved name, else the login name."""
        return settings.profile(self.data_dir)["name"] or platform.login_name()

    def own_domains(self):
        """The domain of the saved email, as a list (empty when there is none): the addresses that count as the person's own."""
        email = settings.profile(self.data_dir)["email"]
        return [email.rsplit("@", 1)[1].lower()] if email else []
