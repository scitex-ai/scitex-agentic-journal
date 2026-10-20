"""``scitex-agentic-journal gui`` command — standalone GUI launcher.

Canonical SDK shape (``scitex_sdk.app.embed.serve_gui`` +
``run_standalone``), mirroring what ``scitex-sdk app init`` scaffolds
so this package behaves like every other SDK GUI app: binds exactly
``--port`` or fails loud, refuses a second instance of its own GUI
unless ``--force`` is given.

Wired into the root CLI group via :func:`register_gui_command`,
matching the pattern of the sibling ``_cli/_submit``, ``_cli/_review``,
``_cli/_decide``, ``_cli/_publish``, ``_cli/_hub_manifest``
subcommands.
"""

from __future__ import annotations

import click


def register_gui_command(main_group: click.Group) -> None:
    """Attach the ``gui`` subcommand to ``main_group``."""

    @main_group.command(name="gui")
    @click.option(
        "--port",
        "-p",
        default=8050,
        show_default=True,
        help="Server port (binds exactly this port or fails loud).",
    )
    @click.option(
        "--host",
        "-h",
        default="127.0.0.1",
        show_default=True,
        help="Host to bind.",
    )
    @click.option(
        "--no-browser",
        is_flag=True,
        default=False,
        help="Don't open a browser tab automatically.",
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
    def gui_cmd(port: int, host: str, no_browser: bool, force: bool) -> None:
        """Launch the standalone GUI with the workspace shell.

        Same UX as scitex-hub (Django + sidebar + file tree +
        AI panel), no server required.

        Example:

        \b
            $ scitex-agentic-journal gui
            $ scitex-agentic-journal gui --port 8051 --no-browser
            $ scitex-agentic-journal gui --force
        """
        import functools

        from scitex_sdk.app.embed import run_standalone, serve_gui

        raise SystemExit(
            serve_gui(
                "scitex-agentic-journal",
                ".",
                port,
                host,
                force,
                functools.partial(
                    run_standalone,
                    app_module="scitex_agentic_journal._django",
                    port=port,
                    host=host,
                    open_browser=not no_browser,
                ),
            )
        )


__all__ = ["register_gui_command"]
