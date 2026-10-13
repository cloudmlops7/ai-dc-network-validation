import subprocess


def ping_host(destination):
    return subprocess.run(
        [
            "docker", "exec", "clab-firstlab-h1",
            "ping", "-c", "2", "-W", "2", destination
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_valid_destination_is_reachable():
    result = ping_host("10.10.10.2")
    assert result.returncode == 0, (
        f"Connectivity failed: {result.stdout}\n{result.stderr}"
    )


def test_unassigned_destination_is_unreachable():
    result = ping_host("10.10.10.254")
    assert result.returncode != 0, (
        "Unexpectedly received a successful ping to 10.10.10.254"
    )
