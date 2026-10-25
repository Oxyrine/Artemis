from pydantic import BaseModel

from artemis.tools.base import Tool


class Input(BaseModel):
    customer_id: str
    quarter: int  # financial quarter 1-4 (Apr-Jun = 1)


TOOL = Tool("get_authorized_tax_credit_extract", "Tax-credit (26AS/AIS) rows for a deductor and quarter. "
            "Empty rows means the credit is not filed yet. Primary evidence.", Input,
            lambda ctx, i: ctx.out(ctx.deps.core.get_authorized_tax_credit_extract(i.customer_id, i.quarter)))
