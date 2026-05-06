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
    timeout: int = typer.Option(300, "--timeout", "-t", help="Login timeout in seconds"),
):
    """Login via browser - opens a window for ChatGPT login."""
    import httpx

    console.print("[green]Opening browser for ChatGPT login...[/green]")
    console.print("[yellow]Please login in the browser window.[/yellow]")
    console.print("[cyan]Waiting for response (this may take a while)...[/cyan]")

    try:
        with httpx.Client(timeout=timeout + 60) as client:
            response = client.post(
                "http://localhost:8000/auth/login/browser",
                params={"timeout": timeout},
            )

            if response.status_code == 200:
                data = response.json()
                console.print(f"[green]Login successful![/green]")
                console.print(f"[cyan]Email: {data['user_email']}[/cyan]")
                console.print(f"[cyan]Session ID: {data['session_id']}[/cyan]")
                console.print("")
                console.print("[yellow]Use this session_id as Bearer token:[/yellow]")
                console.print(f"[white]Authorization: Bearer {data['session_id']}[/white]")
            elif response.status_code == 401:
                error_detail = "Unknown error"
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", str(error_data))
                except Exception:
                    error_detail = response.text or "Unknown error"

                console.print(f"[red]Login failed: {error_detail}[/red]")
                console.print("")
                console.print("[yellow]Troubleshooting tips:[/yellow]")
                if "cloudflare" in error_detail.lower():
                    console.print("  [red]Cloudflare challenge detected[/red]")
                    console.print("  - Try logging in via browser first, then retry")
                    console.print("  - Consider using a different IP or waiting")
                elif "timeout" in error_detail.lower():
                    console.print("  [red]Login took too long[/red]")
                    console.print("  - Try increasing timeout: gpt-proxy login --timeout 600")
                elif "proxy" in error_detail.lower() or "connection" in error_detail.lower():
                    console.print("  [red]Connection/Proxy issue[/red]")
                    console.print("  - Check your proxy settings in .env (BROWSER_PROXY)")
                    console.print("  - Verify the proxy URL is correct and accessible")
                else:
                    console.print("  [red]Possible causes:[/red]")
                    console.print("  - Your session may have expired")
                    console.print("  - Try clearing browser profile: rm -rf ./browser_profile")
                    console.print("  - Ensure you can access chat.openai.com in your browser")
            else:
                console.print(f"[red]Login failed with status {response.status_code}[/red]")
                console.print(f"[dim]{response.text[:200] if response.text else 'No response body'}[/dim]")

    except httpx.ConnectError:
        console.print("[red]Error: Could not connect to server.[/red]")
        console.print("[yellow]Make sure the server is running: gpt-proxy serve[/yellow]")
    except httpx.TimeoutException:
        console.print("[red]Error: Request timed out.[/red]")
        console.print("[yellow]Try increasing timeout: gpt-proxy login --timeout 600[/yellow]")
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        console.print("[yellow]Check server logs for more details.[/yellow]")


if __name__ == "__main__":
    app()
