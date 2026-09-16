from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

MONEY_QUANTUM = Decimal("0.0001")


def parse_money(value: object) -> Decimal:
    if isinstance(value, float):
        raise ValueError("money must be sent as a decimal string")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("invalid monetary amount") from error
    if not amount.is_finite():
        raise ValueError("money must be finite")
    exponent = amount.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError("money must be finite")
    if exponent < -4:
        raise ValueError("money supports at most four decimal places")
    return amount.quantize(MONEY_QUANTUM)


Money = Annotated[
    Decimal,
    BeforeValidator(parse_money),
    PlainSerializer(lambda value: format(value, ".4f"), return_type=str, when_used="json"),
]
