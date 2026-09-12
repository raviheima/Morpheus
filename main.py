#!/usr/bin/env python3
"""
Morpheus - Interactive CLI
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text

from database import init_db
from services.case_service import CaseService
from services.evidence_service import EvidenceService

app = typer.Typer(
    name="morpheus",
    help="Morpheus - Lightweight Unified Digital Forensics Tool",
    add_completion=True,
    invoke_without_command=True,   # ← this makes the interactive mode the default
)

console = Console()


def print_header():
    console.print(
        Panel.fit(
            "[bold cyan]Morpheus[/bold cyan] v0.1.0-poc\n"
            "[dim]Unified Digital Forensics Tool[/dim]",
            border_style="cyan",
        )
    )


def interactive_menu():
    """Main interactive loop"""
    while True:
        console.print()
        console.print("[bold]Main Menu[/bold]")
        console.print("─" * 40)
        console.print("1. Create new case")
        console.print("2. List all cases")
        console.print("3. Add evidence to a case")
        console.print("4. List evidence of a case")
        console.print("5. Show case details")
        console.print("6. View Chain of Custody")
        console.print("7. Export Case to JSON")
        console.print("0. Exit")
        console.print("─" * 40)

        choice = Prompt.ask("Select an option", choices=["0", "1", "2", "3", "4", "5", "6","7"], default="0")

        if choice == "0":
            console.print("\n[green]Goodbye.[/green]")
            break
        elif choice == "1":
            create_case_interactive()
        elif choice == "2":
            list_cases_cmd()
        elif choice == "3":
            add_evidence_interactive()
        elif choice == "4":
            list_evidence_interactive()
        elif choice == "5":
            show_case_details_interactive()
        elif choice == "6":
            view_custody_interactive()
        elif choice == "7":
             export_case_interactive()


def create_case_interactive():
    console.print("\n[bold cyan]Create New Case[/bold cyan]")
    case_name = Prompt.ask("Case name")
    examiner_name = Prompt.ask("Examiner name")
    examiner_email = Prompt.ask("Examiner email (optional)", default="")
    organisation = Prompt.ask("Organisation (e.g. FBI)", default="")
    description = Prompt.ask("Description (optional)", default="")

    try:
        case = CaseService.create_case(
            case_name=case_name,
            examiner_name=examiner_name,
            examiner_email=examiner_email or None,
            organisation=organisation or None,
            description=description or None,
        )
        console.print(
            Panel.fit(
                f"[bold green]Case created successfully![/bold green]\n\n"
                f"[cyan]Case Number:[/cyan]   {case.case_number}\n"
                f"[cyan]Case Name:[/cyan]     {case.case_name}\n"
                f"[cyan]Examiner:[/cyan]      {case.examiner_name}\n"
                f"[cyan]Organisation:[/cyan]  {case.organisation or '—'}",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


def add_evidence_interactive():
    console.print("\n[bold cyan]Add Evidence[/bold cyan]")
    case_number = Prompt.ask("Case number")
    file_path = Prompt.ask("Full path to the file")
    collected_by = Prompt.ask("Collected by")
    notes = Prompt.ask("Notes (optional)", default="")

    try:
        evidence = EvidenceService.add_evidence(
            case_number=case_number,
            file_path=file_path,
            collected_by=collected_by,
            notes=notes or None,
        )
        console.print(
            Panel.fit(
                f"[bold green]Evidence added![/bold green]\n\n"
                f"[cyan]Filename:[/cyan] {evidence.original_filename}\n"
                f"[cyan]SHA-256:[/cyan]  {evidence.sha256_hash}\n"
                f"[cyan]Size:[/cyan]     {evidence.file_size:,} bytes",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


def list_evidence_interactive():
    case_number = Prompt.ask("Case number")
    try:
        items = EvidenceService.list_evidence(case_number)
        if not items:
            console.print(f"[yellow]No evidence found for {case_number}[/yellow]")
            return

        table = Table(title=f"Evidence – {case_number}", header_style="bold cyan")
        table.add_column("ID", style="dim")
        table.add_column("Filename")
        table.add_column("Size")
        table.add_column("SHA-256", style="green")
        table.add_column("Collected By")
        table.add_column("MD5-SUM")


        for item in items:
            table.add_row(
                str(item.id),
                item.original_filename,
                f"{item.file_size:,}",
                item.sha256_hash[:16] + "…",
                item.collected_by,
                item.md5_hash,
            )
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


def list_cases_cmd():
    cases = CaseService.list_cases()
    if not cases:
        console.print("[yellow]No cases found.[/yellow]")
        return

    table = Table(title="Morpheus Cases", header_style="bold cyan")
    table.add_column("Case Number", style="cyan")
    table.add_column("Case Name")
    table.add_column("Examiner")
    table.add_column("Organisation")
    table.add_column("Status")
    table.add_column("Created At")

    for c in cases:
        table.add_row(
            c.case_number,
            c.case_name,
            c.examiner_name,
            c.organisation or "—",
            c.status,
            c.created_at.strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)

def show_case_details_interactive():
    console.print("\n[bold cyan]Show Case Details[/bold cyan]")
    case_number = Prompt.ask("Case number")

    result = CaseService.get_case_details(case_number)
    if not result:
        console.print(f"[bold red]Case not found:[/bold red] {case_number}")
        return

    case, evidence_count = result

    console.print(
        Panel.fit(
            f"[bold]Case Number:[/bold]   {case.case_number}\n"
            f"[bold]Case Name:[/bold]     {case.case_name}\n"
            f"[bold]Examiner:[/bold]      {case.examiner_name}\n"
            f"[bold]Email:[/bold]         {case.examiner_email or '—'}\n"
            f"[bold]Organisation:[/bold]  {case.organisation or '—'}\n"
            f"[bold]Status:[/bold]        {case.status}\n"
            f"[bold]Created:[/bold]       {case.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"[bold]Evidence items:[/bold] {evidence_count}\n\n"
            f"[bold]Description:[/bold]\n{case.description or '—'}",
            title="Case Details",
            border_style="cyan",
        )
    )


def view_custody_interactive():
    console.print("\n[bold cyan]Chain of Custody[/bold cyan]")
    case_number = Prompt.ask("Case number")

    result = CaseService.get_custody_timeline(case_number)
    if not result:
        console.print(f"[bold red]Case not found:[/bold red] {case_number}")
        return

    case, logs = result

    if not logs:
        console.print("[yellow]No custody records found.[/yellow]")
        return

    table = Table(
        title=f"Chain of Custody – {case.case_number}",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Timestamp", style="dim")
    table.add_column("Action")
    table.add_column("Actor")
    table.add_column("Details")

    for log in logs:
        details = log.details or "—"
        # Make it prettier if it's JSON
        if details.startswith("{"):
            try:
                import json
                parsed = json.loads(details)
                details = ", ".join(f"{k}: {v}" for k, v in parsed.items())
            except Exception:
                pass

        table.add_row(
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            log.action,
            log.actor,
            details[:80] + ("…" if len(details) > 80 else ""),
        )

    console.print(table)

#export case function

def export_case_interactive():
    console.print("\n[bold cyan]Export Case to JSON[/bold cyan]")
    case_number = Prompt.ask("Case number")

    try:
        data = CaseService.export_case_to_json(case_number)

        # Default filename
        default_filename = f"{case_number}.json"
        filename = Prompt.ask("Output filename", default=default_filename)

        import json
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        console.print(
            Panel.fit(
                f"[bold green]Case exported successfully![/bold green]\n\n"
                f"[cyan]File:[/cyan] {filename}\n"
                f"[cyan]Evidence items:[/cyan] {len(data['evidence'])}\n"
                f"[cyan]Custody records:[/cyan] {len(data['chain_of_custody'])}",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")

@app.callback()
def main(ctx: typer.Context):
    """Morpheus Interactive CLI"""
    init_db()

    # If no subcommand was given → start interactive mode
    if ctx.invoked_subcommand is None:
        print_header()
        interactive_menu()


# Keep the old commands available for scripting
@app.command("create-case")
def create_case_cmd(
    case_name: str = typer.Option(..., "--name", "-n"),
    examiner_name: str = typer.Option(..., "--examiner", "-e"),
    examiner_email: str = typer.Option(None, "--email"),
    organisation: str = typer.Option(None, "--org", "-o"),
    description: str = typer.Option(None, "--desc", "-d"),
):
    """Create a case (non-interactive)"""
    case = CaseService.create_case(
        case_name=case_name,
        examiner_name=examiner_name,
        examiner_email=examiner_email,
        organisation=organisation,
        description=description,
    )
    console.print(f"[green]Created:[/green] {case.case_number}")


@app.command("list-cases")
def list_cases():
    list_cases_cmd()


if __name__ == "__main__":
    app()
