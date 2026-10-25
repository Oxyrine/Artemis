from pydantic import BaseModel

from artemis.tools.base import Tool


class Input(BaseModel):
    customer_id: str | None = None
    utr: str | None = None
    invoice_ids: list[str] | None = None
    text: str | None = None


TOOL = Tool("search_remittance_email", "Find remittance/credit-note emails by customer, UTR, invoice ids or "
            "text. Returns excerpts (supporting-tier evidence).", Input,
            lambda ctx, i: ctx.out(ctx.deps.core.search_remittance_email(**i.model_dump())))
