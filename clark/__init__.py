"""A stand-in so that `python3 -m clark`, run from the top folder of the repo, works with no PYTHONPATH and no install step.

The code lives in src/clark/ only. This folder holds no code of its own: its __main__.py hands over to the real one.

It sets sys.dont_write_bytecode here, the first thing to run, so that starting clark leaves no __pycache__ folders in
clark's own folder: one on OneDrive is not kept busy syncing them (#57). Only this file's own cache can still be written,
because Python writes it before the file runs.
"""
import sys

sys.dont_write_bytecode = True
