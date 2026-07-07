from app.shared.clock import Clock, SystemClock


def wire_clock() -> Clock:
    """Wire the system clock."""
    return SystemClock()
