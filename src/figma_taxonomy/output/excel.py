"""Excel output formatter matching the taxonomy template structure."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openpyxl.cell.cell import Cell
    from openpyxl.worksheet.worksheet import Worksheet

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import TaxonomyEvent


def _text_cell(sheet: Worksheet, row: int, column: int, value: str) -> Cell:
    """Store design text literally; never truncate it or create Excel formulas."""
    if isinstance(value, str) and (len(value) > 32767 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value)):
        raise ValueError("Excel cannot represent this text (cell length/control characters); use JSON or revise the source.")
    cell = sheet.cell(row=row, column=column, value=value)
    if isinstance(value, str):
        cell.data_type = "s"
    return cell


def write_excel(
    events: list[TaxonomyEvent],
    config: TaxonomyConfig,
    output_path: Path,
) -> None:
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()

    # --- Events sheet ---
    ws_events = wb.active
    ws_events.title = "Events"

    headers = [
        "", "Flow", "Event Name", "Event Description", "Parameter Set",
        "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
    ]
    headers.extend(["Source Node ID", "Source Node IDs"])
    for col, header in enumerate(headers, 1):
        cell = _text_cell(ws_events, row=2, column=col, value=header)
        cell.font = Font(bold=True)

    global_names = {p["name"] for p in config.global_properties}

    for i, event in enumerate(events):
        row = i + 3
        _text_cell(ws_events, row=row, column=2, value=event.flow)
        _text_cell(ws_events, row=row, column=3, value=event.event_name)
        _text_cell(ws_events, row=row, column=4, value=event.description)
        _text_cell(ws_events, row=row, column=14, value=event.source_node_id)
        _text_cell(ws_events, row=row, column=15, value=json.dumps(event.source_node_ids))

        event_props = [p for p in event.properties if p.name not in global_names]

        if event_props:
            param_set = ", ".join(p.name for p in event_props)
            _text_cell(ws_events, row=row, column=5, value=param_set)

            for j, prop in enumerate(event_props[:4]):
                name_col = 6 + (j * 2)
                desc_col = 7 + (j * 2)
                _text_cell(ws_events, row=row, column=name_col, value=prop.name)
                _text_cell(ws_events, row=row, column=desc_col, value=prop.description)

    # --- Parameters sheet ---
    ws_params = wb.create_sheet("Parameters")

    param_headers = [
        "", "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
    ]
    for col, header in enumerate(param_headers, 1):
        cell = _text_cell(ws_params, row=2, column=col, value=header)
        cell.font = Font(bold=True)

    for i, prop in enumerate(config.global_properties):
        row = i + 3
        _text_cell(ws_params, row=row, column=2, value=prop["name"])
        _text_cell(ws_params, row=row, column=3, value=prop.get("description", ""))

    # Preserve the legacy overview while exposing every event-specific schema.
    details = wb.create_sheet("Event Properties")
    detail_headers = ["Event Name", "Flow", "Property Name", "Type", "Description", "Enum Values", "Source Node IDs"]
    for column, header in enumerate(detail_headers, 1):
        _text_cell(details, 1, column, header).font = Font(bold=True)
    row = 2
    for event in events:
        for prop in event.properties:
            values = [event.event_name, event.flow, prop.name, prop.type, prop.description,
                      json.dumps(prop.enum_values, ensure_ascii=False) if prop.enum_values is not None else "",
                      json.dumps(event.source_node_ids, ensure_ascii=False)]
            for column, value in enumerate(values, 1):
                _text_cell(details, row, column, value)
            row += 1
    details.freeze_panes = "A2"
    details.auto_filter.ref = details.dimensions
    wb.save(output_path)
