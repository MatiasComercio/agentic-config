#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "google-api-python-client>=2.100.0",
#   "google-auth>=2.23.0",
#   "google-auth-oauthlib>=1.1.0",
#   "google-auth-httplib2>=0.1.1",
#   "typer>=0.9.0",
#   "rich>=13.0.0",
#   "pyyaml>=6.0",
# ]
# requires-python = ">=3.12"
# ///
"""Google Sheets CLI for read/write operations."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console
from rich.table import Table

# Import auth module for credential loading
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from auth import get_credentials  # noqa: E402
from utils import merge_extra  # noqa: E402

app = typer.Typer(help="Google Sheets CLI operations.")
console = Console(stderr=True)
stdout_console = Console()


def get_sheets_service(account: str | None = None):
    """Get authenticated Sheets API service."""
    creds = get_credentials(account)
    return build("sheets", "v4", credentials=creds)


@app.command()
def read(
    spreadsheet_id: Annotated[str, typer.Argument(help="Spreadsheet ID")],
    range_notation: Annotated[str, typer.Argument(help="Range (e.g., 'Sheet1!A1:D10')")],
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Read values from a spreadsheet range."""
    try:
        service = get_sheets_service(account)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_notation,
        ).execute()

        values = result.get("values", [])

        if json_output:
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "range": range_notation,
                "values": values,
                "rows": len(values),
            }))
            return

        if not values:
            console.print("[yellow]No data found.[/yellow]")
            return

        # Display as table
        table = Table(title=f"{spreadsheet_id} - {range_notation}")
        if values:
            # Use first row as headers or generate column letters
            num_cols = max((len(row) for row in values), default=1)
            for i in range(num_cols):
                table.add_column(f"Col {i+1}", overflow="fold")

            for row in values:
                # Pad row to match column count
                padded = row + [""] * (num_cols - len(row))
                table.add_row(*[str(cell) for cell in padded])

        console.print(table)
        console.print(f"\n[dim]{len(values)} rows[/dim]")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def write(
    spreadsheet_id: Annotated[str, typer.Argument(help="Spreadsheet ID")],
    range_notation: Annotated[str, typer.Argument(help="Range (e.g., 'Sheet1!A1')")],
    value: Annotated[str, typer.Argument(help="Value to write (string or JSON array)")],
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Write value(s) to a spreadsheet range."""
    try:
        # Parse value - could be single value or JSON array
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                if parsed and isinstance(parsed[0], list):
                    values = parsed  # 2D array
                else:
                    values = [parsed]  # 1D array -> single row
            else:
                values = [[str(parsed)]]
        except json.JSONDecodeError:
            values = [[value]]  # Single string value

        # Merge --extra options
        body: dict = {"values": values}
        try:
            body, api_params = merge_extra(body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        service = get_sheets_service(account)
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_notation,
            valueInputOption="USER_ENTERED",
            body=body,
            **api_params,
        ).execute()

        if json_output:
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "range": result.get("updatedRange"),
                "updated_cells": result.get("updatedCells"),
                "updated_rows": result.get("updatedRows"),
            }))
        else:
            console.print(f"[green]Updated {result.get('updatedCells')} cells[/green]")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def append(
    spreadsheet_id: Annotated[str, typer.Argument(help="Spreadsheet ID")],
    sheet_name: Annotated[str, typer.Argument(help="Sheet name")],
    values: Annotated[str, typer.Argument(help="JSON array of values to append")],
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Append row(s) to a sheet."""
    try:
        parsed = json.loads(values)
        if not isinstance(parsed, list):
            parsed = [parsed]
        if parsed and not isinstance(parsed[0], list):
            parsed = [parsed]  # Wrap single row

        # Merge --extra options
        body: dict = {"values": parsed}
        try:
            body, api_params = merge_extra(body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        service = get_sheets_service(account)
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
            **api_params,
        ).execute()

        updates = result.get("updates", {})
        if json_output:
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "updated_range": updates.get("updatedRange"),
                "updated_rows": updates.get("updatedRows"),
            }))
        else:
            console.print(f"[green]Appended {updates.get('updatedRows')} rows[/green]")

    except json.JSONDecodeError:
        console.print('[red]Invalid data format.[/red] Expected JSON array like ["val1", "val2"]')
        raise typer.Exit(1)
    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


@app.command()
def create(
    title: Annotated[str, typer.Argument(help="Spreadsheet title")],
    extra: Annotated[str | None, typer.Option("--extra", help="JSON: additional API params or body fields")] = None,
    account: Annotated[str | None, typer.Option("--account", "-a", help="Account email (default: active)")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a new spreadsheet."""
    try:
        # Merge --extra options
        body: dict = {"properties": {"title": title}}
        try:
            body, api_params = merge_extra(body, extra)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        service = get_sheets_service(account)
        spreadsheet = service.spreadsheets().create(
            body=body,
            **api_params,
        ).execute()

        spreadsheet_id = spreadsheet.get("spreadsheetId")
        url = spreadsheet.get("spreadsheetUrl")

        if json_output:
            stdout_console.print_json(json.dumps({
                "spreadsheet_id": spreadsheet_id,
                "title": title,
                "url": url,
            }))
        else:
            console.print(f"[green]Created:[/green] {title}")
            console.print(f"ID: {spreadsheet_id}")
            console.print(f"URL: {url}")

    except HttpError as e:
        console.print(f"[red]API Error:[/red] {e.reason}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
