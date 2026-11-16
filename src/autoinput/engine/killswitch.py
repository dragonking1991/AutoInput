from collections.abc import Callable

from autoinput.infra.logging import get_logger


def start_kill_switch(hotkey: str, on_trigger: Callable[[], None]) -> Callable[[], None]:
    """Global hotkey that works even when the target app has focus. Returns a stop function."""
    log = get_logger("engine")
    try:
        from pynput import keyboard
    except ImportError:
        log.warning("pynput not installed: global kill-switch disabled")
        return lambda: None

    def trigger() -> None:
        log.warning(f"Kill-switch {hotkey} pressed")
        on_trigger()

    listener = keyboard.GlobalHotKeys({hotkey: trigger})
    listener.start()
    return listener.stop
