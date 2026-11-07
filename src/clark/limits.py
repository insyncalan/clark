"""Limits the server and the page share. The standard library only, no imports at all: the page build reads it, and the page merge
driver rebuilds a page in a folder that holds just the build's code (dev/tools/merge_page.py, BUILD_CODE), so it must stand alone."""

ITEM_TITLE_MAX = 200      # a work item's title, at most (changes._checked_item_changes; the page gets it from the build, PeekTitle.jsx)
