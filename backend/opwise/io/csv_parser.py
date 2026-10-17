"""Strict CSV bundle parser and validator.

Governed by DATA_AND_API.md Section 4.1 and Section 4.3.
Parses multi-file CSV archives (machines.csv, orders.csv, operations.csv, downtimes.csv)
with row-level error reporting, formula injection detection, and bounds validation.
"""

import csv
import io
from collections.abc import Mapping, Sequence

from opwise.io.parsing_types import (
    ParsedDowntime,
    ParsedFactoryData,
    ParsedMachine,
    ParsedOperation,
    ParsedOrder,
    RowError,
)
from opwise.io.security import (
    MAX_ROW_COUNT,
    inspect_safe_zip,
    is_formula_cell,
)

REQUIRED_FILES = {"machines.csv", "orders.csv", "operations.csv"}

MACHINE_COLS = ["machine_id", "name"]
ORDER_COLS = ["order_id", "name", "release_minute", "due_minute", "tardiness_weight"]
OP_COLS = ["operation_id", "order_id", "sequence_index", "machine_id", "processing_minutes"]
DT_COLS = ["downtime_id", "machine_id", "start_minute", "end_minute", "reason"]


def _clean_header(headers: Sequence[str]) -> list[str]:
    """Clean BOM, whitespace, and normalize headers to lowercase."""
    return [h.replace("\ufeff", "").strip().lower() for h in headers]


def _parse_int_field(
    val: str,
    field_name: str,
    sheet: str,
    row: int,
    errors: list[RowError],
    min_val: int | None = None,
) -> int | None:
    """Validate and convert an integer string, recording RowError on failure."""
    if is_formula_cell(val):
        errors.append(RowError(sheet, row, field_name, val, "Spreadsheet formulas are not permitted."))
        return None
    try:
        iv = int(val.strip())
    except (ValueError, TypeError):
        errors.append(RowError(sheet, row, field_name, val, f"Must be an integer, got '{val}'."))
        return None

    if min_val is not None and iv < min_val:
        errors.append(
            RowError(sheet, row, field_name, val, f"Value {iv} violates minimum bound (must be >= {min_val}).")
        )
        return None
    return iv


def _parse_machines_csv(reader: csv.DictReader, errors: list[RowError]) -> list[ParsedMachine]:
    """Parse machines.csv rows."""
    machines: list[ParsedMachine] = []
    sheet = "machines.csv"
    for row_idx, row in enumerate(reader, start=2):
        if row_idx > MAX_ROW_COUNT + 1:
            errors.append(RowError(sheet, row_idx, "rows", "", f"Exceeded maximum row limit of {MAX_ROW_COUNT}."))
            break
        m_id = (row.get("machine_id") or "").strip()
        name = (row.get("name") or "").strip()
        if not m_id:
            errors.append(RowError(sheet, row_idx, "machine_id", m_id, "Machine ID cannot be empty."))
            continue
        if is_formula_cell(m_id) or is_formula_cell(name):
            errors.append(RowError(sheet, row_idx, "name", name, "Spreadsheet formulas are not permitted."))
            continue
        machines.append(ParsedMachine(machine_id=m_id, name=name or m_id))
    return machines


def _parse_orders_csv(reader: csv.DictReader, errors: list[RowError]) -> list[ParsedOrder]:
    """Parse orders.csv rows."""
    orders: list[ParsedOrder] = []
    sheet = "orders.csv"
    for row_idx, row in enumerate(reader, start=2):
        if row_idx > MAX_ROW_COUNT + 1:
            errors.append(RowError(sheet, row_idx, "rows", "", f"Exceeded maximum row limit of {MAX_ROW_COUNT}."))
            break
        o_id = (row.get("order_id") or "").strip()
        name = (row.get("name") or "").strip()
        if not o_id:
            errors.append(RowError(sheet, row_idx, "order_id", o_id, "Order ID cannot be empty."))
            continue
        rel = _parse_int_field(row.get("release_minute") or "", "release_minute", sheet, row_idx, errors, min_val=0)
        due = _parse_int_field(row.get("due_minute") or "", "due_minute", sheet, row_idx, errors, min_val=0)
        wt = _parse_int_field(row.get("tardiness_weight") or "", "tardiness_weight", sheet, row_idx, errors, min_val=1)
        if rel is not None and due is not None and wt is not None:
            orders.append(
                ParsedOrder(order_id=o_id, name=name or o_id, release_minute=rel, due_minute=due, tardiness_weight=wt)
            )
    return orders


def _parse_operations_csv(reader: csv.DictReader, errors: list[RowError]) -> list[ParsedOperation]:
    """Parse operations.csv rows."""
    operations: list[ParsedOperation] = []
    sheet = "operations.csv"
    for row_idx, row in enumerate(reader, start=2):
        if row_idx > MAX_ROW_COUNT + 1:
            errors.append(RowError(sheet, row_idx, "rows", "", f"Exceeded maximum row limit of {MAX_ROW_COUNT}."))
            break
        op_id = (row.get("operation_id") or "").strip()
        order_id = (row.get("order_id") or "").strip()
        machine_id = (row.get("machine_id") or "").strip()
        if not op_id:
            errors.append(RowError(sheet, row_idx, "operation_id", op_id, "Operation ID cannot be empty."))
            continue
        if not order_id:
            errors.append(RowError(sheet, row_idx, "order_id", order_id, "Order ID cannot be empty."))
            continue
        if not machine_id:
            errors.append(RowError(sheet, row_idx, "machine_id", machine_id, "Machine ID cannot be empty."))
            continue
        seq = _parse_int_field(row.get("sequence_index") or "", "sequence_index", sheet, row_idx, errors, min_val=1)
        dur = _parse_int_field(row.get("processing_minutes") or "", "processing_minutes", sheet, row_idx, errors, min_val=1)
        if seq is not None and dur is not None:
            operations.append(
                ParsedOperation(
                    operation_id=op_id,
                    order_id=order_id,
                    sequence_index=seq,
                    machine_id=machine_id,
                    processing_minutes=dur,
                )
            )
    return operations


def _parse_downtimes_csv(reader: csv.DictReader, errors: list[RowError]) -> list[ParsedDowntime]:
    """Parse downtimes.csv rows."""
    downtimes: list[ParsedDowntime] = []
    sheet = "downtimes.csv"
    for row_idx, row in enumerate(reader, start=2):
        if row_idx > MAX_ROW_COUNT + 1:
            errors.append(RowError(sheet, row_idx, "rows", "", f"Exceeded maximum row limit of {MAX_ROW_COUNT}."))
            break
        dt_id = (row.get("downtime_id") or "").strip()
        m_id = (row.get("machine_id") or "").strip()
        reason = (row.get("reason") or "").strip()
        if not dt_id:
            errors.append(RowError(sheet, row_idx, "downtime_id", dt_id, "Downtime ID cannot be empty."))
            continue
        if not m_id:
            errors.append(RowError(sheet, row_idx, "machine_id", m_id, "Machine ID cannot be empty."))
            continue
        start = _parse_int_field(row.get("start_minute") or "", "start_minute", sheet, row_idx, errors, min_val=0)
        end = _parse_int_field(row.get("end_minute") or "", "end_minute", sheet, row_idx, errors, min_val=0)
        if start is not None and end is not None:
            if end <= start:
                errors.append(
                    RowError(sheet, row_idx, "end_minute", str(end), f"End minute ({end}) must be strictly greater than start ({start}).")
                )
            else:
                downtimes.append(
                    ParsedDowntime(downtime_id=dt_id, machine_id=m_id, start_minute=start, end_minute=end, reason=reason)
                )
    return downtimes


def _validate_columns(
    reader_fields: Sequence[str] | None, expected_cols: list[str], filename: str, errors: list[RowError]
) -> bool:
    """Validate that required columns are present in the CSV header."""
    if not reader_fields:
        errors.append(RowError(filename, 1, "header", "", "CSV file is empty or missing header row."))
        return False
    cleaned_fields = set(_clean_header(reader_fields))
    missing = [col for col in expected_cols if col not in cleaned_fields]
    if missing:
        errors.append(RowError(filename, 1, "header", ", ".join(missing), f"Missing required column(s): {', '.join(missing)}."))
        return False
    return True


def parse_csv_bundle(file_map: Mapping[str, str | bytes]) -> ParsedFactoryData:
    """Parse an extracted bundle of CSV file contents into structured domain objects."""
    result = ParsedFactoryData()
    normalized_map = {k.lower().strip(): v for k, v in file_map.items()}

    # Check required CSV files presence
    missing_files = [f for f in REQUIRED_FILES if f not in normalized_map]
    if missing_files:
        for mf in missing_files:
            result.errors.append(RowError(mf, 0, "file", "", f"Missing required CSV file: '{mf}'."))
        return result

    # 1. Parse machines.csv
    m_content = normalized_map["machines.csv"]
    m_text = m_content.decode("utf-8-sig") if isinstance(m_content, bytes) else m_content
    m_reader = csv.DictReader(io.StringIO(m_text))
    if _validate_columns(m_reader.fieldnames, MACHINE_COLS, "machines.csv", result.errors):
        result.machines = _parse_machines_csv(m_reader, result.errors)

    # 2. Parse orders.csv
    o_content = normalized_map["orders.csv"]
    o_text = o_content.decode("utf-8-sig") if isinstance(o_content, bytes) else o_content
    o_reader = csv.DictReader(io.StringIO(o_text))
    if _validate_columns(o_reader.fieldnames, ORDER_COLS, "orders.csv", result.errors):
        result.orders = _parse_orders_csv(o_reader, result.errors)

    # 3. Parse operations.csv
    op_content = normalized_map["operations.csv"]
    op_text = op_content.decode("utf-8-sig") if isinstance(op_content, bytes) else op_content
    op_reader = csv.DictReader(io.StringIO(op_text))
    if _validate_columns(op_reader.fieldnames, OP_COLS, "operations.csv", result.errors):
        result.operations = _parse_operations_csv(op_reader, result.errors)

    # 4. Parse optional downtimes.csv
    if "downtimes.csv" in normalized_map:
        dt_content = normalized_map["downtimes.csv"]
        dt_text = dt_content.decode("utf-8-sig") if isinstance(dt_content, bytes) else dt_content
        dt_reader = csv.DictReader(io.StringIO(dt_text))
        if _validate_columns(dt_reader.fieldnames, DT_COLS, "downtimes.csv", result.errors):
            result.downtimes = _parse_downtimes_csv(dt_reader, result.errors)

    return result


def parse_csv_zip_archive(zip_bytes: bytes) -> ParsedFactoryData:
    """Safely inspect and parse a ZIP archive containing CSV files."""
    zf = inspect_safe_zip(zip_bytes, is_xlsx=False)
    file_map: dict[str, bytes] = {}
    for name in zf.namelist():
        basename = name.split("/")[-1].split("\\")[-1]
        if basename:
            file_map[basename] = zf.read(name)
    return parse_csv_bundle(file_map)
