"""Safe failure injection helpers for Containerlab nodes."""

import subprocess


def run_command(command):
    """Run a command and return its stdout."""
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\n"
            f"{result.stderr.strip()}"
        )

    return result.stdout.strip()


def set_interface(container, interface, state):
    """Set a container interface administratively up or down."""
    if state not in {"up", "down"}:
        raise ValueError("state must be 'up' or 'down'")

    return run_command([
        "docker",
        "exec",
        container,
        "ip",
        "link",
        "set",
        interface,
        state,
    ])


class InterfaceFailure:
    """Temporarily fail an interface and restore it automatically."""

    def __init__(self, container, interface):
        self.container = container
        self.interface = interface

    def __enter__(self):
        set_interface(
            self.container,
            self.interface,
            "down",
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        set_interface(
            self.container,
            self.interface,
            "up",
        )
        return False
