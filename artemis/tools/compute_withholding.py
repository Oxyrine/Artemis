from pydantic import BaseModel

from artemis.tools.base import Tool


class Input(BaseModel):
    customer_id: str
    invoice_ids: list[str]
    transaction_date: str  # ISO YYYY-MM-DD


TOOL = Tool("compute_withholding", "Expected TDS in paise for the invoices, with the rule used and base "
            "amount. Never calculate TDS yourself; call this.", Input,
            lambda ctx, i: ctx.out(ctx.deps.core.compute_withholding(i.customer_id, i.invoice_ids,
                                                                     i.transaction_date)))
