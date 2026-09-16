from decimal import Decimal

from pydantic import BaseModel, Field

from lume.core.money import Money


class BudgetUpsert(BaseModel):
    total_limit: Money = Field(gt=0)


class CategoryLimitUpsert(BaseModel):
    limit_amount: Money = Field(gt=0)


class CategoryBudgetResponse(BaseModel):
    category_id: str
    category_name: str
    limit_amount: Money
    spent: Money
    remaining: Money
    percentage_used: Money


class BudgetResponse(BaseModel):
    id: str
    month: str
    currency: str
    total_limit: Money
    spent: Money
    remaining: Money
    percentage_used: Money
    categories: list[CategoryBudgetResponse]


def percentage(spent: Decimal, limit: Decimal) -> Decimal:
    if limit == 0:
        return Decimal("0.0000")
    return ((spent / limit) * Decimal(100)).quantize(Decimal("0.0001"))
