"""Figma client regressions use mocked HTTP and never touch the design cache."""

from unittest.mock import Mock

import httpx
import pytest

from figma_taxonomy import figma_client


@pytest.mark.parametrize(('value', 'key'), [
    ('ABC123', 'ABC123'),
    ('https://www.figma.com/design/ABC123/App?node-id=1-2', 'ABC123'),
    ('https://figma.com/file/ABC123/branch/XYZ789/App', 'XYZ789'),
])
def test_parse_file_key(value: str, key: str) -> None:
    assert figma_client._parse_file_key(value) == key


@pytest.mark.parametrize('value', [
    '../private', 'https://evilfigma.com/design/ABC/App',
    'https://figma.com.evil.test/design/ABC/App', '',
])
def test_reject_invalid_file_keys(value: str) -> None:
    with pytest.raises(ValueError, match='Figma'):
        figma_client._parse_file_key(value)


def test_no_cache_never_reads_or_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('FIGMA_TOKEN', 'test-only')
    read = Mock(side_effect=AssertionError('Cache read forbidden'))
    write = Mock(side_effect=AssertionError('Cache write forbidden'))
    monkeypatch.setattr(figma_client, '_read_cache', read)
    monkeypatch.setattr(figma_client, '_write_cache', write)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={'document': {}, 'version': 'test'})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(figma_client.httpx, 'Client', lambda **kwargs: client)
    assert figma_client.fetch_file('ABC', no_cache=True)['version'] == 'test'
    assert len(calls) == 1
    assert calls[0].headers['X-FIGMA-TOKEN'] == 'test-only'
    read.assert_not_called()
    write.assert_not_called()


@pytest.mark.parametrize(('status', 'message'), [
    (403, 'file_content:read'), (404, 'file key'), (429, '120'),
])
def test_actionable_errors(
    status: int, message: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('FIGMA_TOKEN', 'test-only')
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, headers={'Retry-After': '120'}),
    ))
    monkeypatch.setattr(figma_client.httpx, 'Client', lambda **kwargs: client)
    with pytest.raises(RuntimeError, match=message):
        figma_client.fetch_file('ABC', no_cache=True)
