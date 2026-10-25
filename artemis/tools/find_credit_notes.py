from pydantic import BaseModel

from artemis.tools.base import Tool


class Input(BaseModel):
    customer_id: str
    invoice_ids: list[str] | None = None


TOOL = Tool("find_credit_notes", "Credit notes for a customer/invoices with source (erp|email_only) and "
            "status (issued|agreed_not_issued).", Input,
            lambda ctx, i: ctx.out(ctx.deps.core.find_credit_notes(i.customer_id, i.invoice_ids)))
