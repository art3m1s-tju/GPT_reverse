"""Typer CLI for GPT Proxy."""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
import uvicorn

from gpt_proxy.config import settings

app = typer.Typer(
    name="gpt-proxy",
    help="Local ChatGPT reverse proxy with API key management",
)
console = Console()


@app.command()
def serve(
    host: str = typer.Option(settings.app_host, "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(settings.app_port, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload for development"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of worker processes"),
):
    """Start the proxy server."""
    console.print(f"[green]Starting GPT Proxy on {host}:{port}[/green]")

    if reload:
        # Development mode with reload
        uvicorn.run(
            "gpt_proxy.main:app",
            host=host,
            port=port,
            reload=True,
        )
    else:
        # Production mode
        uvicorn.run(
            "gpt_proxy.main:app",
            host=host,
            port=port,
            workers=workers,
        )


@app.command()
def keys():
    """Manage API keys."""
    if not settings.openai_api_keys:
        console.print("[yellow]No API keys configured.[/yellow]")
        console.print("Set OPENAI_API_KEYS environment variable.")
        return

    table = Table(title="Configured API Keys")
    table.add_column("Index", style="cyan")
    table.add_column("Key (masked)", style="green")
    table.add_column("Status", style="yellow")

    for i, key in enumerate(settings.openai_api_keys):
        # Mask the key
        masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
        table.add_row(str(i), masked, "active")

    console.print(table)


@app.command()
def config():
    """Show current configuration."""
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    config_dict = settings.model_dump()
    for key, value in config_dict.items():
        # Mask sensitive values
        if "key" in key.lower() and isinstance(value, list) and value:
            value = f"{len(value)} keys configured"
        elif "key" in key.lower() and isinstance(value, str) and value:
            value = "***"
        table.add_row(key, str(value))

    console.print(table)


@app.command()
def version():
    """Show version information."""
    from gpt_proxy import __version__
    console.print(f"[green]GPT Proxy v{__version__}[/green]")


if __name__ == "__main__":
    app()
