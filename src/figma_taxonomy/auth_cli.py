"""Explicit CLI entry points for the optional local OAuth session."""

from __future__ import annotations

import json
import os

import click

from figma_taxonomy import oauth


@click.group()
def auth() -> None:
    """Log in to Figma with your own OAuth app; store credentials in the OS keychain."""


@auth.command()
@click.option("--client-id", envvar="FIGMA_OAUTH_CLIENT_ID", required=True, help="Registered Figma OAuth app client ID.")
@click.option("--port", type=click.IntRange(1024, 65535), default=8765, show_default=True, help="Port for the registered loopback callback.")
@click.option("--no-browser", is_flag=True, help="Print the authorization URL without opening a browser.")
@click.option("--timeout", type=click.IntRange(1, 600), default=180, show_default=True, help="Seconds to wait for browser authorization.")
def login(client_id: str, port: int, no_browser: bool, timeout: int) -> None:
    """Authorize file_content:read and save one local OAuth session."""
    secret = os.environ.get("FIGMA_OAUTH_CLIENT_SECRET") or click.prompt("OAuth client secret", hide_input=True)
    try:
        oauth.login(client_id, secret, port=port, open_browser=not no_browser, notify=click.echo, timeout=timeout)
    except (ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from None
    click.echo("OAuth session saved. Set FIGMA_TOKEN_TYPE=oauth and unset FIGMA_TOKEN to use it.")


@auth.command()
def status() -> None:
    """Show local login/expiry metadata without printing tokens or making requests."""
    try:
        result = oauth.status()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from None
    result["managed_session_selected"] = os.environ.get("FIGMA_TOKEN_TYPE", "pat").lower() == "oauth" and not os.environ.get("FIGMA_TOKEN")
    click.echo(json.dumps(result, indent=2))


@auth.command()
def refresh() -> None:
    """Refresh and securely save the managed session, without printing its token."""
    try:
        oauth.access_token(force_refresh=True)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from None
    click.echo("Saved OAuth session refreshed.")


@auth.command()
def logout() -> None:
    """Remove saved local credentials; revoke app authorization separately in Figma."""
    try:
        oauth.logout()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from None
    click.echo("Local OAuth session removed. Remote app authorization and environment tokens are unchanged.")
