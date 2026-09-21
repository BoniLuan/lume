import csv
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from uuid import NAMESPACE_URL, uuid5

from lume.imports.schemas import StatementRow

_DATE_ALIASES = {
    "date",
    "data",
    "transaction date",
    "data lançamento",
    "data lancamento",
    "posted date",
}
_DESCRIPTION_ALIASES = {
    "description",
    "descricao",
    "descrição",
    "memo",
    "historico",
    "histórico",
    "name",
    "merchant",
}
_AMOUNT_ALIASES = {"amount", "valor", "value", "transaction amount"}
_TYPE_ALIASES = {"type", "tipo", "kind", "natureza"}
_DEBIT_ALIASES = {"debit", "débito", "debito", "withdrawal"}
_CREDIT_ALIASES = {"credit", "crédito", "credito", "deposit"}
_ID_ALIASES = {"id", "transaction id", "fitid", "identificador"}


def _field(row: dict[str, str], aliases: set[str]) -> str:
    return next(
        (value.strip() for key, value in row.items() if key.strip().casefold() in aliases), ""
    )


def _date(raw: str) -> date:
    value = raw.strip()
    value = value[:8] if re.match(r"^\d{8}(?:\d{6})?", value) else value[:10]
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported statement date: {raw[:30]}")


def _amount(raw: str) -> Decimal:
    value = re.sub(r"[^0-9,.-]", "", raw.strip())
    if "," in value and "." in value:
        value = (
            value.replace(".", "").replace(",", ".")
            if value.rfind(",") > value.rfind(".")
            else value.replace(",", "")
        )
    elif "," in value:
        value = value.replace(",", ".")
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Statement contains an invalid amount") from error
    exponent = amount.as_tuple().exponent
    if not amount.is_finite() or amount == 0 or not isinstance(exponent, int) or exponent < -2:
        raise ValueError("Statement amounts must be nonzero with at most two decimal places")
    return amount


def _parse_csv(content: str) -> list[tuple[date, str, Decimal, str | None]]:
    sample = content[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(StringIO(content), dialect=dialect)
    if reader.fieldnames is None:
        raise ValueError("CSV needs a header row")
    headers = {name.strip().casefold() for name in reader.fieldnames if name}
    if not (
        headers & _DATE_ALIASES
        and headers & _DESCRIPTION_ALIASES
        and (headers & _AMOUNT_ALIASES or headers & _DEBIT_ALIASES or headers & _CREDIT_ALIASES)
    ):
        raise ValueError("CSV needs date, description, and amount or debit/credit columns")
    records = []
    for row in reader:
        if not any(row.values()):
            continue
        raw_amount = _field(row, _AMOUNT_ALIASES)
        if raw_amount:
            amount = _amount(raw_amount)
            kind = _field(row, _TYPE_ALIASES).casefold()
            if kind in {"debit", "expense", "débito", "debito", "saída", "saida"}:
                amount = -abs(amount)
            elif kind in {"credit", "income", "crédito", "credito", "entrada"}:
                amount = abs(amount)
        else:
            debit = _field(row, _DEBIT_ALIASES)
            credit = _field(row, _CREDIT_ALIASES)
            if bool(debit) == bool(credit):
                raise ValueError("Each CSV row needs exactly one debit or credit amount")
            amount = -abs(_amount(debit)) if debit else abs(_amount(credit))
        description = _field(row, _DESCRIPTION_ALIASES)[:160]
        if not description:
            raise ValueError("Statement rows need a description")
        records.append(
            (
                _date(_field(row, _DATE_ALIASES)),
                description,
                amount,
                _field(row, _ID_ALIASES) or None,
            )
        )
    return records


def _tag(block: str, name: str) -> str:
    match = re.search(rf"<{name}>([^<\r\n]+)", block, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _parse_ofx(content: str) -> list[tuple[date, str, Decimal, str | None]]:
    records = []
    for match in re.finditer(
        r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|$)", content, re.IGNORECASE | re.DOTALL
    ):
        block = match.group(1)
        raw_date = _tag(block, "DTPOSTED")
        description = (_tag(block, "NAME") or _tag(block, "MEMO"))[:160]
        if not raw_date or not description:
            raise ValueError("OFX transaction lacks a date or description")
        records.append(
            (
                _date(raw_date),
                description,
                _amount(_tag(block, "TRNAMT")),
                _tag(block, "FITID") or None,
            )
        )
    return records


def parse_statement(account_id: str, filename: str, content: str) -> tuple[str, list[StatementRow]]:
    if not content.strip():
        raise ValueError("Statement file is empty")
    if filename.lower().endswith(".ofx"):
        format_name = "ofx"
        parsed = _parse_ofx(content)
    elif filename.lower().endswith(".csv"):
        format_name = "csv"
        parsed = _parse_csv(content)
    else:
        raise ValueError("Choose a .csv or .ofx statement")
    if not parsed or len(parsed) > 500:
        raise ValueError("Statement must contain between 1 and 500 transactions")
    occurrences: dict[str, int] = {}
    rows = []
    for posted, description, signed_amount, source_id in parsed:
        identity = source_id or f"{posted.isoformat()}|{description.casefold()}|{signed_amount}"
        occurrences[identity] = occurrences.get(identity, 0) + 1
        stable = f"{account_id}|{identity}|{occurrences[identity]}"
        row_key = str(uuid5(NAMESPACE_URL, f"lume-import:{stable}"))
        rows.append(
            StatementRow(
                row_key=row_key,
                effective_date=posted,
                description=description,
                kind="income" if signed_amount > 0 else "expense",
                amount=abs(signed_amount),
                source_id=source_id,
                matched_transaction_id=None,
                suggested_category_id=None,
            )
        )
    return format_name, rows


def merchant_key(description: str) -> str:
    return re.sub(r"\s+", " ", description.casefold()).strip()[:160]
