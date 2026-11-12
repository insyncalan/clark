"""#918: one headless Chrome for a whole test class, a fresh browser context (a clean profile: its own storage, cache and cookies) for each use.

A test file that opened `chrome()` for every test and every subtest paid about half a second to start and stop a browser about a hundred
times. `SharedChrome` starts it once (`start()` in setUpClass, `stop()` in tearDownClass) and `page()` gives each use what `chrome()` gave:
a pipe whose only page is a new one, in a new browser context that is thrown away afterwards, so nothing one test stored reaches the next.
`page_target(cdp)` (the first page the pipe lists) and every `cdp.call` / `cdp.js` work as before.
"""
import contextlib

from test_server import chrome


class _Own:
    """The shared pipe seen from one use: the same calls, but Target.getTargets lists only this use's page."""

    def __init__(self, pipe, target):
        self._pipe, self._target = pipe, target

    def call(self, method, params=None, session=None):
        out = self._pipe.call(method, params, session)
        if method == "Target.getTargets":
            out = {**out, "targetInfos": [t for t in out["targetInfos"] if t["targetId"] == self._target]}
        return out

    def js(self, expr, session):
        return self._pipe.js(expr, session)

    @property
    def events(self):
        return self._pipe.events

    def __getattr__(self, name):
        return getattr(self._pipe, name)


class SharedChrome:
    def __init__(self):
        self._stack = None
        self._pipe = None

    def start(self):
        self._stack = contextlib.ExitStack()
        self._pipe = self._stack.enter_context(chrome())

    def stop(self):
        stack, self._stack, self._pipe = self._stack, None, None
        if stack:
            stack.close()

    @contextlib.contextmanager
    def page(self):
        pipe = self._pipe
        assert pipe is not None, "SharedChrome.start() was not called (setUpClass)"
        context = pipe.call("Target.createBrowserContext")["browserContextId"]
        try:
            target = pipe.call("Target.createTarget", {"url": "about:blank", "browserContextId": context})["targetId"]
            yield _Own(pipe, target)
        finally:
            try:
                pipe.call("Target.disposeBrowserContext", {"browserContextId": context})
            except RuntimeError:
                pass               # Chrome already closed it
