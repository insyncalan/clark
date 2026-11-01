"""The server's routes as the tests expect them, in one place (#426).

A new route is added to src/clark/server.py and to the two lists below, and nowhere else in the tests: test_server.py and
test_publish_route.py both compare the server's route tables with these lists, and test_tpl_all_published.py reads the POST
list for the routes that change things. The lists stay written out (not read from the server) on purpose: a route that
appears or disappears without this file being changed fails the comparison, so an unplanned route never goes unseen.
"""
# Each route says which piece of work added it.
GET_ROUTES = (
    "/api/activity", "/api/ai/status", "/api/ask-enabled", "/api/ask-folders", "/api/ask/status", "/api/backups", "/api/data", "/api/diagnostics",
    "/api/export", "/api/milestones", "/api/movement", "/api/people", "/api/profile", "/api/projects", "/api/publication",
    "/api/use-cases",
)     # #147: export; #136: movement; #180: profile; #47: asking; #42: activity

POST_ROUTES = (
    "/api/ai/stop", "/api/ai/suggest", "/api/ask", "/api/ask-enabled", "/api/ask-folders", "/api/ask/change/apply", "/api/ask/change/dry", "/api/ask/stop",
    "/api/backups/preview", "/api/backups/restore", "/api/change", "/api/client-folder", "/api/draft-email",
    "/api/draft-email/sent", "/api/logging", "/api/logging/open-folder", "/api/page-error", "/api/people", "/api/people/undo",
    "/api/preview", "/api/profile", "/api/publish", "/api/section-file", "/api/section-image", "/api/sneak/read", "/api/undo",
    "/api/word-export", "/api/word-import",
)     # #43, #111, #147, #180, #50, #47, #47e, #42, #96, #72 (the AI suggestion, its Stop and its status), and #48 (the two Word ones)


def unplanned(server):
    """What differs between the server's route tables and the lists above, as a dict (empty when they agree): the routes the
    server has that no list names ("extra") and the listed routes the server no longer has ("missing"), for GET and for POST."""
    out = {}
    for method, listed, table in (("GET", GET_ROUTES, server.GET_ROUTES), ("POST", POST_ROUTES, server.POST_ROUTES)):
        extra, missing = sorted(set(table) - set(listed)), sorted(set(listed) - set(table))
        if extra or missing:
            out[method] = {"extra": extra, "missing": missing}
    return out
