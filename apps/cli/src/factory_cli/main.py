import httpx
import typer
from factory_sdk import FactoryClient

app = typer.Typer(no_args_is_help=True, help="Talk to a running factory API.")


@app.command()
def doctor() -> None:
    """Check Docker, keys, and the GitHub App configuration."""
    from factory_cli.doctor import report

    failed = False
    for name, ok, detail in report():
        typer.echo(f"{'ok' if ok else 'no'}  {name}: {detail}")
        if not ok and name in {"python", "git", "docker", "github-app", "github-oauth"}:
            failed = True
    if failed:
        raise typer.Exit(code=1)


@app.command()
def up() -> None:
    """Start compose, migrations, the worker, the API, and the console."""
    from factory_cli.up import start

    start()


requests_app = typer.Typer(no_args_is_help=True, help="Create and list requests.")
app.add_typer(requests_app, name="requests")


@app.command()
def health(api: str = typer.Option("http://127.0.0.1:43123", help="API base URL")) -> None:
    """Check that the API is up."""
    try:
        with FactoryClient(api) as client:
            payload = client.health()
    except httpx.HTTPError as exc:
        raise typer.Exit(code=1) from exc
    typer.echo(payload["status"])


@requests_app.command("create")
def create_request(
    title: str = typer.Option(..., help="Short request title"),
    body: str = typer.Option(..., help="What the factory should do"),
    target: str | None = typer.Option(None, help="Target repo, owner/name"),
    api: str = typer.Option("http://127.0.0.1:43123", help="API base URL"),
) -> None:
    """Create a request. The API starts the no-op workflow."""
    try:
        with FactoryClient(api) as client:
            created = client.create_request(title, body, target=target)
    except httpx.HTTPError as exc:
        raise typer.Exit(code=1) from exc
    typer.echo(created.id)


@requests_app.command("list")
def list_requests(
    api: str = typer.Option("http://127.0.0.1:43123", help="API base URL"),
) -> None:
    """List requests newest first."""
    try:
        with FactoryClient(api) as client:
            rows = client.list_requests()
    except httpx.HTTPError as exc:
        raise typer.Exit(code=1) from exc
    for row in rows:
        typer.echo(f"{row.id}  {row.status}  {row.title}")
