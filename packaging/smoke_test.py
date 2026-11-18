"""Contained smoke test for the packaged app — run by build.py before any installer is made.

Safety (a broken bundle once relaunched itself endlessly):
* QT_QPA_PLATFORM=offscreen, so no window can ever reach the screen;
* on macOS/Linux the app runs in its own session with RLIMIT_NPROC capped a few processes
  above the current count, so even a fork loop cannot grow;
* a watchdog polls the process count every 100 ms and kills everything on the first extra copy;
* everything started here is killed in `finally`.
"""

import contextlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = (
    ROOT / "dist" / "AutoInput.app" / "Contents" / "MacOS" / "AutoInput"
    if sys.platform == "darwin"
    else ROOT / "dist" / "AutoInput" / ("AutoInput.exe" if sys.platform == "win32" else "AutoInput")
)


def app_pids() -> list[int]:
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq AutoInput.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, check=False,
        ).stdout  # fmt: skip
        return [int(line.split('","')[1]) for line in out.splitlines() if "AutoInput.exe" in line]
    out = subprocess.run(
        ["ps", "-axo", "pid=,command="], capture_output=True, text=True, check=False
    ).stdout
    return [int(line.split(None, 1)[0]) for line in out.splitlines() if str(EXE) in line]


def kill_all() -> None:
    for pid in app_pids():
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            with contextlib.suppress(OSError):
                os.kill(pid, 9)


def _cap_processes() -> None:
    import resource

    current = len(
        subprocess.run(["ps", "-U", str(os.getuid())], capture_output=True).stdout.splitlines()
    )
    limit = current + 8
    resource.setrlimit(resource.RLIMIT_NPROC, (limit, limit))
    os.setsid()


def launch(args: list[str], env: dict[str, str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [str(EXE), *args],
        env=env,
        cwd=tempfile.gettempdir(),  # must not depend on the repo being the working directory
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=None if sys.platform == "win32" else _cap_processes,
    )


def watch(seconds: float, allowed: int) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if (count := len(app_pids())) > allowed:
            kill_all()
            raise SystemExit(
                f"✖ {count} AutoInput processes (max {allowed}): app relaunches itself"
            )
        time.sleep(0.1)


def main() -> None:
    if not EXE.exists():
        raise SystemExit(f"✖ Missing {EXE}")
    if app_pids():
        raise SystemExit("✖ Close every running AutoInput before the smoke test.")
    with tempfile.TemporaryDirectory() as data:
        env = {k: v for k, v in os.environ.items() if not k.startswith("AUTOINPUT_")}
        env |= {"QT_QPA_PLATFORM": "offscreen", "AUTOINPUT_DATA_DIR": data}
        try:
            # 1. A helper-style re-exec must exit at once without starting a GUI.
            helper = launch(["-B", "-s", "-c", "pass"], env)
            watch(3, allowed=1)
            if helper.poll() is None:
                raise SystemExit("✖ Helper invocation did not exit")

            # 2. Normal start: exactly one process, stays up, writes logs and config.
            app = launch([], env)
            watch(8, allowed=1)
            if app.poll() is not None:
                raise SystemExit(f"✖ App exited early with code {app.returncode}")
            log = Path(data) / "logs" / "autoinput.log"
            if not log.is_file() or not list((Path(data) / "profiles").glob("*.yaml")):
                raise SystemExit("✖ App did not create its log/config in the data folder")

            # 3. Second launch hands over to the running instance and exits.
            second = launch([], env)
            watch(4, allowed=2)
            if second.poll() is None:
                raise SystemExit("✖ Second instance kept running (single-instance guard broken)")
            if "Traceback" in log.read_text(encoding="utf-8"):
                raise SystemExit("✖ Errors in log:\n" + log.read_text(encoding="utf-8")[-2000:])
        finally:
            kill_all()
    print("✔ Smoke test passed: single process, no self-relaunch, config/log created")


if __name__ == "__main__":
    main()
