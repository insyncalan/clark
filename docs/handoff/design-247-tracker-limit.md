# Design for #247: the tracker and the change route's size limit

**Finding.** The ticket describes a 16 KB change-route limit. On main the limit is `server.CHANGE_BODY_LIMIT`
(2 x 64 KB + 4 KB = 132 KB, #96), for every change. The widest request the tracker checker accepts (47 lines, 10 groups,
every text at its longest, four-byte letters sent as `\u` escapes, the body escaped twice) is about 95 KB, so a valid tracker
always reaches the checker and one line over the cap is answered with the checker's own words
(`TRACKER_TOO_MANY_LINES`). The generic reply appears only over 132 KB.

**Design.** No tracker-only limit and no code change to the route: a second, larger limit chosen by peeking at the kind would
add a door that a non-tracker request could try to use, for no gain. The one limit stays and a test ties it to the checker:
the widest tracker request, measured over the real route in six kinds of letter, must be at least 4 KB under
`CHANGE_BODY_LIMIT`. If the checker's caps ever grow past that, the test fails and the limit is revisited in one place.

**Tests** (`tests/test_tracker_route.py`, real route and real store): a tracker at the cap saves in every kind of letter;
one line over gets the checker's words and writes nothing; over the route limit gets the general words; a 17 KB non-tracker
change is the store's to refuse; the small routes' limits are unchanged; six concurrent writers leave one whole body and
the cap is never passed; sequentially the last write wins.
