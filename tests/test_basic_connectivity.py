import subprocess


def run_command(*command):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, (
        f"Command failed: {command}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    return result.stdout


def test_h1_eth1_is_up():
    output = run_command(
        "docker", "exec", "clab-firstlab-h1",
        "ip", "link", "show", "eth1"
    )
    assert "UP" in output


def test_h2_eth1_is_up():
    output = run_command(
        "docker", "exec", "clab-firstlab-h2",
        "ip", "link", "show", "eth1"
    )
    assert "UP" in output


def test_h1_to_h2_connectivity():
    run_command(
        "docker", "exec", "clab-firstlab-h1",
        "ip", "addr", "replace", "10.10.10.1/24", "dev", "eth1"
    )
    run_command(
        "docker", "exec", "clab-firstlab-h2",
        "ip", "addr", "replace", "10.10.10.2/24", "dev", "eth1"
    )

    output = run_command(
        "docker", "exec", "clab-firstlab-h1",
        "ping", "-c", "4", "-W", "2", "10.10.10.2"
    )
    assert "0% packet loss" in output
