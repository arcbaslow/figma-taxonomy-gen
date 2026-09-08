# Releasing Figma Taxonomy Gen

## Prepare

1. Start from a clean checkout of the intended release commit.
2. Update `pyproject.toml`, `src/figma_taxonomy/__init__.py` and the local package entry in `uv.lock` (run `uv lock`) together, and add a dated entry to `CHANGELOG.md`.
3. Update `docs/RELEASE_NOTES.md`, refresh affected examples/screenshots and run every check in the README. For Google Ads, include the separate webapp suite; for GA4, include coverage, format and mypy.
4. Build and inspect the artifacts. Run the documented offline example against the source you are releasing.

```bash
uv sync --extra dev --extra ai --extra mcp
uv run pytest -q
uv run ruff check src/ tests/
uv build
```

## Publish

Commit and push the tested source, then choose an unused tag matching the package version. Do not move an existing release tag. The following is an example for this version; future releases must use their own version:

```bash
git tag -a v0.4.2 -m "Release v0.4.2"
git push origin v0.4.2
gh release create v0.4.2 --verify-tag --title "v0.4.2" --notes-file docs/RELEASE_NOTES.md
```

Attach the reviewed source bundle and its `SHA256SUMS.txt`; attach installable package artifacts only after checking their contents and entry points. Use the README's source installation for the full agent/skill workflow.

## Automation

Pushing a matching version tag triggers `release.yml`. The workflow builds distributions; PyPI publication runs only when `PUBLISH_TO_PYPI` is `true`. Create the GitHub Release after pushing the tag.

The repository's [release workflow](https://github.com/arcbaslow/figma-taxonomy-gen/blob/master/.github/workflows/release.yml) is the source of truth. Preserve existing publishing settings unless a registry release is explicitly intended. Wait for the default-branch CI run to pass before creating a stable release.

For workflows that expose `workflow_dispatch`, the `tag` input is checked against the dispatched branch's package version. Dispatch from the intended release ref when retrying a build. Do not assume that typing an old tag selects its source in every workflow.
