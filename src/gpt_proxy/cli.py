"""Typer CLI for GPT Proxy."""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
import uvicorn

app = typer.Typer(
    name="gpt-proxy",
    help="ChatGPT reverse proxy - Use ChatGPT without API keys!",
)
console = Console()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
):
    """Start the proxy server."""
    console.print("[green]Starting ChatGPT Reverse Proxy...[/green]")
    console.print(f"[cyan]Server: http://{host}:{port}[/cyan]")
    console.print(f"[cyan]Docs: http://{host}:{port}/docs[/cyan]")
    console.print("")
    console.print("[yellow]How to use:[/yellow]")
    console.print("1. Login to chat.openai.com")
    console.print("2. Get session token from browser cookies")
    console.print("3. POST to /auth/login with session token")
    console.print("4. Use returned session_id as Bearer token")
    console.print("")

    uvicorn.run(
        "gpt_proxy.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def help_token():
    """Show how to get ChatGPT session token."""
    console.print("[bold green]How to get ChatGPT session token:[/bold green]")
    console.print("")
    console.print("[bold]Method 1: Browser DevTools[/bold]")
    console.print("1. Go to https://chat.openai.com and login")
    console.print("2. Press F12 to open DevTools")
    console.print("3. Go to Application > Cookies > chat.openai.com")
    console.print("4. Find '__Secure-next-auth.session-token'")
    console.print("5. Copy its value")
    console.print("")
    console.print("[bold]Method 2: Browser Console[/bold]")
    console.print("Run this in browser console on chat.openai.com:")
    console.print("")
    console.print("[cyan]document.cookie.split('; ').find(c => c.startsWith('__Secure-next-auth.session-token='))?.split('=')[1][/cyan]")
    console.print("")
    console.print("[yellow]Note: Session tokens expire periodically. Get a fresh one if login fails.[/yellow]")


@app.command()
def version():
    """Show version information."""
    from gpt_proxy import __version__
    console.print(f"[green]GPT Proxy v{__version__}[/green]")


if __name__ == "__main__":
    app()
