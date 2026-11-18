"""Entry point frozen by PyInstaller (a script, so `autoinput` is imported as a package).

In a packaged app sys.executable is AutoInput itself, so anything that re-executes the
interpreter (multiprocessing helpers, `python -c ...`) would start another GUI. Divert those
invocations before anything else is imported.
"""

import multiprocessing
import sys

# Interpreter-style flags that only a re-executed helper process would ever receive.
_INTERPRETER_FLAGS = {"-c", "-m", "-B", "-s", "-S", "-E", "-I", "-O", "-OO", "-u", "-W", "-X"}

if __name__ == "__main__":
    multiprocessing.freeze_support()  # handles multiprocessing workers / resource tracker
    if _INTERPRETER_FLAGS.intersection(sys.argv[1:]) or "--multiprocessing-fork" in sys.argv:
        sys.exit(0)  # unknown helper re-exec: never open a window for it

    from autoinput.ui.app import main

    main()
