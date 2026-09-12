#!/usr/bin/env python3
"""
Morpheus - Unified Digital Forensics Tool
CLI Entry Point
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

app = typer.Typer(
    name="morpheus",
    help="Morpheus - Lightweight Unified Digital Forensics Tool",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


@app.callback()
def main():
    """
    Morpheus CLI - Artifact collection, analysis & reporting
    without storing raw evidence files.
    """
    pass


@app.command()
def version():
    """Show Morpheus version"""
    console.print(
        Panel.fit(
            "[bold cyan]Morpheus[/bold cyan] v0.1.0-poc\n"
            "[dim]Unified Digital Forensics Tool[/dim]",
            border_style="cyan",
        )
    )


@app.command()
def info():
    """Show project overview"""
    content = Text()
    content.append("Morpheus\n", style="bold cyan")
    content.append("A lightweight digital forensics tool focused on:\n\n")
    content.append("• Zero raw file storage (only hashes + encrypted metadata)\n")
    content.append("• Immutable chain of custody\n")
    content.append("• Offline-first SQLite ledger\n")
    content.append("• Clean structured reports\n")
    content.append("• Future agentic AI analysis\n")

    console.print(Panel(content, title="Project Overview", border_style="green"))


if __name__ == "__main__":
    app()
