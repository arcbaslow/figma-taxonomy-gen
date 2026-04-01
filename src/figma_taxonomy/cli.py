"""CLI entrypoint for figma-taxonomy-gen."""

from __future__ import annotations

from pathlib import Path

import click

from figma_taxonomy.config import load_config
from figma_taxonomy.extractor import extract_elements
from figma_taxonomy.figma_client import fetch_file, load_fixture
from figma_taxonomy.taxonomy_engine import generate_taxonomy


@click.group()
@click.version_option()
def main():
    """Extract interactive UI elements from Figma designs and generate Amplitude event taxonomies."""
    pass


@main.command()
@click.argument("figma_url", required=False)
@click.option("--fixture", type=click.Path(exists=True, path_type=Path), help="Use a local JSON fixture instead of Figma API")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True, path_type=Path), help="Path to taxonomy.config.yaml")
@click.option("--output", "-o", "output_dir", type=click.Path(path_type=Path), default="./output", help="Output directory")
@click.option("--format", "-f", "formats", default="excel,csv,json,markdown", help="Comma-separated output formats")
@click.option("--page", help="Extract only a specific page by name")
@click.option("--no-cache", is_flag=True, help="Skip Figma API cache")
def extract(figma_url, fixture, config_path, output_dir, formats, page, no_cache):
    """Extract taxonomy from a Figma file.

    Pass a Figma URL to fetch from the API, or use --fixture with a local JSON file.
    """
    if not figma_url and not fixture:
        raise click.UsageError("Provide a Figma URL or use --fixture with a local JSON file.")

    config = load_config(config_path)

    if fixture:
        click.echo(f"Loading fixture: {fixture}")
        figma_file = load_fixture(fixture)
    else:
        click.echo(f"Fetching Figma file: {figma_url}")
        figma_file = fetch_file(figma_url, no_cache=no_cache)

    if page:
        config.figma.exclude_pages = []
        document = figma_file.get("document", figma_file)
        matching = [
            child for child in document.get("children", [])
            if child.get("name") == page
        ]
        if not matching:
            available = [c.get("name") for c in document.get("children", [])]
            raise click.ClickException(f"Page '{page}' not found. Available: {available}")
        figma_file = {"document": {"children": matching}}

    click.echo("Extracting interactive elements...")
    elements = extract_elements(figma_file, config)
    click.echo(f"Found {len(elements)} interactive elements")

    click.echo("Generating taxonomy...")
    events = generate_taxonomy(elements, config)
    click.echo(f"Generated {len(events)} events")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    format_list = [f.strip() for f in formats.split(",")]

    if "excel" in format_list:
        from figma_taxonomy.output.excel import write_excel
        path = output_dir / "taxonomy.xlsx"
        write_excel(events, config, path)
        click.echo(f"  Excel:    {path}")

    if "csv" in format_list:
        from figma_taxonomy.output.amplitude_csv import write_csv
        path = output_dir / "taxonomy.csv"
        write_csv(events, config, path)
        click.echo(f"  CSV:      {path}")

    if "json" in format_list:
        from figma_taxonomy.output.json_schema import write_json
        path = output_dir / "taxonomy.json"
        write_json(events, config, path)
        click.echo(f"  JSON:     {path}")

    if "markdown" in format_list:
        from figma_taxonomy.output.markdown import write_markdown
        path = output_dir / "taxonomy.md"
        write_markdown(events, config, path)
        click.echo(f"  Markdown: {path}")

    click.echo(f"\nDone! {len(events)} events written to {output_dir}/")
