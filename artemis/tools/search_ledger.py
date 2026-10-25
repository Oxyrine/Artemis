from pydantic import BaseModel

from artemis.tools.base import Tool


class Input(BaseModel):
    customer_id: str
    amount_paise: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    status: str | None = None  # open | partially_applied | applied (default open)


TOOL = Tool("search_ledger", "Find invoices in the ERP ledger for a customer (default: open invoices). "
            "Returns gross, taxable and GST amounts in paise.", Input,
            lambda ctx, i: ctx.out(ctx.deps.core.search_ledger(**i.model_dump())))
