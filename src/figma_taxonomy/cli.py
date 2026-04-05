"""CLI entrypoint for figma-taxonomy-gen."""

from __future__ import annotations

from pathlib import Path

import click

import json
import os

from figma_taxonomy.config import load_config
from figma_taxonomy.extractor import extract_elements
from figma_taxonomy.figma_client import fetch_file, load_fixture
from figma_taxonomy.taxonomy_engine import generate_taxonomy
from figma_taxonomy.validate import diff_taxonomies, diff_taxonomy_dicts


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
@click.option("--ai", "use_ai", is_flag=True, help="Enrich events with Claude-suggested properties")
@click.option("--yes", "-y", "assume_yes", is_flag=True, help="Skip cost-estimate confirmation prompt")
def extract(figma_url, fixture, config_path, output_dir, formats, page, no_cache, use_ai, assume_yes):
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

    if use_ai or config.ai.enabled:
        events = _run_enrichment(events, config, assume_yes)

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


@main.command()
@click.argument("taxonomy_path", type=click.Path(exists=True, path_type=Path))
@click.option("--figma", "figma_url", help="Figma file URL to validate against")
@click.option("--fixture", type=click.Path(exists=True, path_type=Path), help="Local JSON fixture instead of Figma API")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True, path_type=Path), help="Path to taxonomy.config.yaml")
@click.option("--no-cache", is_flag=True, help="Skip Figma API cache")
@click.option("--exit-code", is_flag=True, help="Exit non-zero if drift is detected (for CI)")
def validate(taxonomy_path, figma_url, fixture, config_path, no_cache, exit_code):
    """Check an existing taxonomy JSON for drift against the current Figma file."""
    if not figma_url and not fixture:
        raise click.UsageError("Provide --figma URL or --fixture with a local JSON file.")

    config = load_config(config_path)

    stored = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
    existing_events = stored.get("events", {})

    if fixture:
        figma_file = load_fixture(fixture)
    else:
        figma_file = fetch_file(figma_url, no_cache=no_cache)

    elements = extract_elements(figma_file, config)
    current_events = generate_taxonomy(elements, config)

    report = diff_taxonomies(existing_events, current_events)

    if report.is_clean():
        click.echo(click.style("No drift detected.", fg="green"))
        return

    click.echo(click.style("Drift detected:", fg="yellow", bold=True))
    if report.added:
        click.echo(f"\n  Added ({len(report.added)}):")
        for event in report.added:
            click.echo(f"    + {event.event_name}  (node {event.source_node_id})")
    if report.removed:
        click.echo(f"\n  Removed ({len(report.removed)}):")
        for name in report.removed:
            click.echo(f"    - {name}")
    if report.renamed:
        click.echo(f"\n  Renamed ({len(report.renamed)}):")
        for old, new in report.renamed:
            click.echo(f"    {old} -> {new}")
    if report.property_changes:
        click.echo(f"\n  Property changes ({len(report.property_changes)}):")
        for change in report.property_changes:
            click.echo(f"    {change['event_name']}:")
            for prop in change["added"]:
                click.echo(f"      + {prop}")
            for prop in change["removed"]:
                click.echo(f"      - {prop}")

    if exit_code:
        raise SystemExit(1)


@main.command()
@click.argument("taxonomy_path", type=click.Path(exists=True, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Print what would be pushed without calling the API")
@click.option("--base-url", default="https://amplitude.com", help="Amplitude base URL")
def push(taxonomy_path, dry_run, base_url):
    """Push a taxonomy JSON to Amplitude's Taxonomy API (Enterprise only)."""
    from figma_taxonomy.amplitude_push import make_client, push_taxonomy
    from figma_taxonomy.validate import _events_from_dict

    api_key = os.environ.get("AMPLITUDE_API_KEY")
    secret_key = os.environ.get("AMPLITUDE_SECRET_KEY")
    if not dry_run and not (api_key and secret_key):
        raise click.ClickException(
            "AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY must be set for non-dry-run pushes."
        )

    stored = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
    events = _events_from_dict(stored.get("events", {}))
    click.echo(f"Loaded {len(events)} events from {taxonomy_path}")

    client = make_client(api_key or "dry", secret_key or "dry", base_url=base_url)
    try:
        result = push_taxonomy(events, client=client, dry_run=dry_run)
    finally:
        client.close()

    if dry_run:
        categories = sorted({e.flow for e in events if e.flow})
        properties = sorted({p.name for e in events for p in e.properties})
        click.echo(f"\nDry run - would push:")
        click.echo(f"  {len(categories)} categories: {categories}")
        click.echo(f"  {len(properties)} properties")
        click.echo(f"  {len(events)} events")
        return

    click.echo(f"\nCreated: {len(result.events_created)} events, "
               f"{len(result.properties_created)} properties, "
               f"{len(result.categories_created)} categories")
    if result.events_skipped:
        click.echo(f"Skipped (already exist): {len(result.events_skipped)}")
    if result.errors:
        click.echo(click.style(f"\n{len(result.errors)} error(s):", fg="red"))
        for err in result.errors[:10]:
            click.echo(f"  {err}")
        raise SystemExit(1)


@main.command(name="diff")
@click.argument("old_path", type=click.Path(exists=True, path_type=Path))
@click.argument("new_path", type=click.Path(exists=True, path_type=Path))
@click.option("--exit-code", is_flag=True, help="Exit non-zero if any differences found")
def diff_cmd(old_path, new_path, exit_code):
    """Diff two taxonomy JSON files (e.g., before/after a design change)."""
    old = json.loads(Path(old_path).read_text(encoding="utf-8")).get("events", {})
    new = json.loads(Path(new_path).read_text(encoding="utf-8")).get("events", {})

    report = diff_taxonomy_dicts(old, new)

    if report.is_clean():
        click.echo(click.style("Taxonomies match.", fg="green"))
        return

    click.echo(click.style("Differences:", fg="yellow", bold=True))
    if report.added:
        click.echo(f"\n  Added ({len(report.added)}):")
        for event in report.added:
            click.echo(f"    + {event.event_name}")
    if report.removed:
        click.echo(f"\n  Removed ({len(report.removed)}):")
        for name in report.removed:
            click.echo(f"    - {name}")
    if report.renamed:
        click.echo(f"\n  Renamed ({len(report.renamed)}):")
        for old_name, new_name in report.renamed:
            click.echo(f"    {old_name} -> {new_name}")
    if report.property_changes:
        click.echo(f"\n  Property changes ({len(report.property_changes)}):")
        for change in report.property_changes:
            click.echo(f"    {change['event_name']}:")
            for prop in change["added"]:
                click.echo(f"      + {prop}")
            for prop in change["removed"]:
                click.echo(f"      - {prop}")

    if exit_code:
        raise SystemExit(1)


def _run_enrichment(events, config, assume_yes: bool):
    from figma_taxonomy.ai_enricher import (
        build_prompt,
        enrich_events,
        estimate_cost,
        group_events_by_flow,
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise click.ClickException(
            "ANTHROPIC_API_KEY is not set. Export it or disable --ai."
        )

    try:
        import anthropic
    except ImportError:
        raise click.ClickException(
            "anthropic package not installed. Install with: uv pip install 'figma-taxonomy-gen[ai]'"
        )

    grouped = group_events_by_flow(events)
    prompts = [
        build_prompt(flow, flow_events, app_type=config.app.type, app_name=config.app.name)
        for flow, flow_events in grouped.items()
    ]
    estimate = estimate_cost(prompts, model=config.ai.model)
    click.echo(
        f"\nAI enrichment: {estimate['num_calls']} call(s), "
        f"~{estimate['est_input_tokens']} input tokens, "
        f"est. cost ${estimate['est_cost_usd']:.4f} ({estimate['model']})"
    )
    if not assume_yes and not click.confirm("Proceed?", default=True):
        click.echo("Skipping enrichment.")
        return events

    client = anthropic.Anthropic(api_key=api_key)
    click.echo("Calling Claude for property suggestions...")
    enriched = enrich_events(
        events, config, client=client,
        model=config.ai.model, max_tokens=config.ai.max_tokens,
    )
    new_prop_count = sum(len(e.properties) for e in enriched) - sum(len(e.properties) for e in events)
    click.echo(f"Enrichment added {max(new_prop_count, 0)} new properties across {len(enriched)} events.")
    return enriched
