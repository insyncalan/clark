# Design note: #212b Rating section, guarded change to `changes.py`

Decision D-12 and FR-40: the status picker's Rating section sets a risk's or issue's impact and likelihood. This note covers the one guarded file the build touches, `src/clark/changes.py`. Review of the build: Full.

## What the change does
- The `raid` update allow-list takes `impact` and `likelihood`. Before this, it took neither.
- `priority` is still refused as input (`NO_RAID_PRIORITY`). It is not in the allow-list. It is added to `ITEM_SHOWN` for `raid`, so the reply says the priority the store worked out.
- Null is refused for both fields: they join `ITEM_NOT_NULL`.
- A value that is not High, Medium or Low is refused in its own sentence (`NOT_A_RATING`), checked against the store's own allowed list.
- Kinds are limited to risk and issue (`RATING_NOT_THIS_KIND`). A closed or cancelled item is refused (`RATING_NOT_OPEN`); a request that sets the status to Open at the same time is judged on the new status.

## Why
The owner decided the Rating section sets impact and likelihood. The store works out priority from those two, so the page never sends it. Saying it back keeps the page's colour true to what the store holds.

## What could go wrong, and the test
- Priority taken as input, or a reply without it: `tests/test_changes.py` `test_a_risks_new_impact_and_likelihood_say_back_the_priority_worked_out`.
- A rating cleared, or not High, Medium or Low, or refused in the wrong words: `test_a_rating_is_refused_in_its_own_words_and_never_cleared`.
- A rating on an action, a decision, a Closed or Cancelled item: `test_only_an_open_risk_or_issue_takes_a_rating`.
- The page's rules and picker: `tests/test_inline_edits.py` `test_rating_rules`, `test_rating_from_the_status_picker_sets_impact_and_likelihood_with_one_undo`, `test_a_rating_pick_redraws_the_colour_from_the_reply_and_undo_puts_it_back`.

## What is not changed
The store writer (`store.py`), the schema, and the publish allow-list. Nothing new reaches the published page. No new route and no new kind.

## Undo
One Undo step puts back impact, likelihood and priority together (asserted in the first test above, "Undo puts all three back").
