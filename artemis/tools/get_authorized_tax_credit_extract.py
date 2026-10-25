from pydantic import BaseModel

from artemis.tools.base import Tool


class Input(BaseModel):
    customer_id: str
    quarter: int  # Indian financial quarter (Apr-Jun=1, Jul-Sep=2); use financial_quarter from the opening context


TOOL = Tool("get_authorized_tax_credit_extract", "Tax-credit (26AS/AIS) rows for a deductor and quarter. "
            "quarter is the Indian FINANCIAL quarter (Apr-Jun=1, Jul-Sep=2, Oct-Dec=3, Jan-Mar=4): "
            "use financial_quarter from the opening context. Empty rows means not filed yet. Primary evidence.", Input,
            lambda ctx, i: ctx.out(ctx.deps.core.get_authorized_tax_credit_extract(i.customer_id, i.quarter)))
