"""``scitex-agentic-journal gui`` group — standalone GUI lifecycle.

Canonical SDK shape (doctrine 19_gui-commands.md §12): one ``gui``
group with exactly four verbs — ``open`` (browser-launching,
auto-serves when not running), ``serve`` (foreground headless
server), ``status``, ``stop``.

Lifecycle bookkeeping (pid/port/host state file, liveness,
idempotent stop, port-holder identification) is delegated to
``scitex_sdk.app.embed`` rather than reimplemented here — the same
shared primitive scholar/writer/figrecipe converge on.

``serve`` is the foreground headless server (no ``--no-browser``
flag — browser-launching is exclusively ``open``'s job). ``open``
auto-serves in a detached background process when nothing is
running, then opens the browser. Default port 8050 preserves the
existing standalone bind; a future 3130X overflow assignment
(31301 is next free after live-paper 31300) happens leaf-by-leaf
per the scitex-dev GUI registry and must not ride along silently.

Wired into the root CLI group via :func:`register_gui_command`,
matching the pattern of the sibling ``_cli/_submit``, ``_cli/_review``,
``_cli/_decide``, ``_cli/_publish``, ``_cli/_hub_manifest``
subcommands.
"""

from __future__ import annotations

import functools
import subprocess
import sys
import time
import webbrowser

import click

PACKAGE = "scitex-agentic-journal"
DEFAULT_PORT = 8050
DEFAULT_HOST = "127.0.0.1"


def _embed():
    """Return ``scitex_sdk.app.embed``, or exit with an actionable message."""
    try:
        from scitex_sdk.app import embed
    except ImportError:
        click.secho(
            "scitex-sdk is not installed — the GUI lifecycle "
            "(serve/status/stop) is delegated to it. Install it with: "
            "pip install 'scitex-sdk>=0.3.9'",
            fg="red",
            err=True,
        )
        sys.exit(1)
    return embed


@click.group(name="gui")
def gui() -> None:
    """Browser-based GUI: open, serve, status, stop.

    Example:

      $ scitex-agentic-journal gui open
      $ scitex-agentic-journal gui serve --port 8050
      $ scitex-agentic-journal gui status
      $ scitex-agentic-journal gui stop -y
    """


@gui.command(name="open")
@click.option(
    "--port",
    "-p",
    default=DEFAULT_PORT,
    show_default=True,
    type=int,
    help="Server port (binds exactly this port or fails loud).",
)
@click.option(
    "--host",
    "-h",
    default=DEFAULT_HOST,
    show_default=True,
    help="Host to bind.",
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="Don't open a browser tab automatically.",
)
def gui_open(port: int, host: str, no_browser: bool) -> None:
    """Open the GUI in a browser, auto-serving when not running.

    Example:

      $ scitex-agentic-journal gui open
      $ scitex-agentic-journal gui open --port 8051 --no-browser
    """
    embed = _embed()
    current = embed.gui_status(PACKAGE)
    if current.get("running"):
        click.echo(f"Already running at {current['url']} — opening browser.")
        if not no_browser:
            webbrowser.open(current["url"])
        return

    holder = embed.gui_port_holder(port, PACKAGE)
    if holder.in_use:
        if holder.ours:
            click.secho(
                f"{host}:{port} is held by an ORPHANED {PACKAGE} GUI (pid "
                f"{holder.pid}) — it died without clearing its state file, "
                "so `gui status` cannot see it. Reclaim it with:\n"
                f"  {PACKAGE} gui serve --force",
                fg="red",
                err=True,
            )
        elif holder.ours is False:
            click.secho(
                f"Refusing to start: {host}:{port} is held by a different "
                f"process (pid {holder.pid}, {holder.name}). Free it, or pass "
                "--port to use another one. Not opening the browser.",
                fg="red",
                err=True,
            )
        else:
            click.secho(
                f"Refusing to start: {host}:{port} is in use, but /proc could "
                "not be read, so whether it is ours is UNKNOWN — not "
                "guessing, and not opening the browser. Pass --port to use "
                "another one.",
                fg="red",
                err=True,
            )
        sys.exit(1)

    click.echo(f"Starting {PACKAGE} GUI server on {host}:{port}...")
    from scitex_sdk.app import _gui_runtime as _gr

    state_path = _gr.state_path(PACKAGE)
    log_path = state_path.with_name("gui-serve.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "scitex_agentic_journal",
        "gui",
        "serve",
        "--port",
        str(port),
        "--host",
        host,
    ]
    with open(log_path, "wb") as log_file:
        subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    url = f"http://{host}:{port}"
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if embed.gui_status(PACKAGE).get("running"):
            if not no_browser:
                webbrowser.open(url)
            click.echo(f"{PACKAGE} GUI running at {url}")
            return
        time.sleep(0.2)

    click.secho(
        f"Server did not come up within 10s — not opening the browser. "
        f"Last output from {log_path}:",
        fg="red",
        err=True,
    )
    try:
        click.echo(log_path.read_text()[-2000:], err=True)
    except OSError:
        pass
    sys.exit(1)


@gui.command(name="serve")
@click.option(
    "--port",
    "-p",
    default=DEFAULT_PORT,
    show_default=True,
    type=int,
    help="Server port (binds exactly this port or fails loud).",
)
@click.option(
    "--host",
    "-h",
    default=DEFAULT_HOST,
    show_default=True,
    help="Host to bind.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help=(
        "Stop a previous instance of this app's own GUI, then serve. "
        "Never kills a process it does not own."
    ),
)
def gui_serve(port: int, host: str, force: bool) -> None:
    """Run the GUI server in the foreground (headless; Ctrl-C to stop).

    Binds exactly --port, or fails loud. Refuses a second instance
    of this app's own GUI unless --force is given.

    Example:

      $ scitex-agentic-journal gui serve
      $ scitex-agentic-journal gui serve --port 8051
      $ scitex-agentic-journal gui serve --force
    """
    from scitex_sdk.app.embed import run_standalone, serve_gui

    raise SystemExit(
        serve_gui(
            PACKAGE,
            ".",
            port,
            host,
            force,
            functools.partial(
                run_standalone,
                app_module="scitex_agentic_journal._django",
                port=port,
                host=host,
                open_browser=False,
            ),
        )
    )


@gui.command(name="status")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON output.",
)
def gui_status(as_json: bool) -> None:
    """Report whether the GUI server is running.

    Example:

      $ scitex-agentic-journal gui status
      $ scitex-agentic-journal gui status --json
    """
    import json as _json

    state = _embed().gui_status(PACKAGE)
    if as_json:
        click.echo(_json.dumps(state, indent=2))
        return
    if state.get("running"):
        click.echo(f"Running at {state['url']} (pid {state.get('pid')}).")
    else:
        click.echo("Not running.")


@gui.command(name="stop")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would happen without stopping.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Confirm stopping the server.",
)
def gui_stop(dry_run: bool, yes: bool) -> None:
    """Stop the GUI server started by ``gui serve`` / ``gui open``.

    Example:

      $ scitex-agentic-journal gui stop -y
      $ scitex-agentic-journal gui stop --dry-run
    """
    embed = _embed()
    current = embed.gui_status(PACKAGE)
    if not current.get("running"):
        click.echo("Not running.")
        return
    if dry_run:
        click.echo(
            f"DRY RUN — would stop pid {current.get('pid')} ({current.get('url')})"
        )
        return
    if not yes:
        click.secho(
            "Refusing to stop without --yes/-y (or use --dry-run to preview).",
            fg="yellow",
            err=True,
        )
        sys.exit(1)
    result = embed.gui_stop(PACKAGE)
    if result.get("stopped"):
        click.echo(f"Stopped (pid {result.get('pid')}).")
    else:
        click.secho(
            f"Failed to stop: {result.get('error')}",
            fg="red",
            err=True,
        )
        sys.exit(1)


def register_gui_command(main_group: click.Group) -> None:
    """Attach the ``gui`` group to ``main_group``."""
    main_group.add_command(gui)


__all__ = ["PACKAGE", "DEFAULT_PORT", "DEFAULT_HOST", "gui", "register_gui_command"]
