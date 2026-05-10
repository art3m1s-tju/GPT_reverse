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


@app.command()
def login(
    token: Optional[str] = typer.Option(
        None,
        "--token",
        help="ChatGPT session token (__Secure-next-auth.session-token). If omitted, you'll be prompted.",
    ),
    server: str = typer.Option(
        "http://localhost:8000", "--server", "-s", help="Proxy server URL"
    ),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Request timeout in seconds"),
):
    """Login by submitting a ChatGPT session token.

    How to get the token:
      1. Open https://chatgpt.com in your normal browser and login.
      2. F12 -> Application -> Cookies -> chatgpt.com
      3. Copy the value of '__Secure-next-auth.session-token'.
      4. Run: gpt-proxy login --token <value>   (or run with no flag to be prompted)
    """
    import httpx

    if not token:
        console.print("[yellow]Paste your ChatGPT session token (input hidden):[/yellow]")
        token = typer.prompt("session_token", hide_input=True)

    token = token.strip()
    if not token:
        console.print("[red]Empty token. Aborting.[/red]")
        raise typer.Exit(code=1)

    console.print("[cyan]Submitting token to proxy server...[/cyan]")

    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.post(
                f"{server.rstrip('/')}/auth/login",
                json={"session_token": token},
            )

            if response.status_code == 200:
                data = response.json()
                console.print("[green]Login successful![/green]")
                console.print(f"[cyan]Email: {data['user_email']}[/cyan]")
                console.print(f"[cyan]Session ID: {data['session_id']}[/cyan]")
                console.print("")
                console.print("[yellow]Use this session_id as Bearer token:[/yellow]")
                console.print(f"[white]Authorization: Bearer {data['session_id']}[/white]")
                return

            error_detail = "Unknown error"
            try:
                error_data = response.json()
                error_detail = error_data.get("detail", str(error_data))
            except Exception:
                error_detail = response.text or "Unknown error"

            console.print(
                f"[red]Login failed (status {response.status_code}): {error_detail}[/red]"
            )
            if response.status_code == 401:
                console.print("")
                console.print("[yellow]Common causes:[/yellow]")
                console.print("  - Token expired or copied incompletely (it's long — make sure you got all of it)")
                console.print("  - Wrong cookie copied; the right one is '__Secure-next-auth.session-token'")
                console.print("  - Server can't reach chatgpt.com (check BROWSER_PROXY in .env)")

    except httpx.ConnectError:
        console.print("[red]Error: Could not connect to server.[/red]")
        console.print("[yellow]Start it first: gpt-proxy serve[/yellow]")
    except httpx.TimeoutException:
        console.print("[red]Error: Request timed out.[/red]")
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")


if __name__ == "__main__":
    app()
