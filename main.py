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
