"""POST /api/open-mail (row 1297): hand a finished mailto: link to the system's own open, so the mail app opens even when the
browser window lets no mailto: link through. Only platform.open_mail decides what may be opened; the words of a refusal are its words."""
from . import platform


class MailOpen:
    def __init__(self, opener=None):
        self.opener = opener or platform.open_mail

    def handle(self, req):
        link = req.get("link") if isinstance(req, dict) else None
        try:
            self.opener(link if isinstance(link, str) else "")
        except platform.PlatformError as e:
            return 503, {"ok": False, "code": "not_opened", "message": str(e)}
        except OSError:      # e.g. an argument list too long: the same refusal as the platform's own
            return 503, {"ok": False, "code": "not_opened", "message": f"The mail app could not be opened. {platform.TRY_AGAIN}"}
        return 200, {"ok": True}
