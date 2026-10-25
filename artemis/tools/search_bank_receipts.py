from pydantic import BaseModel

from artemis.tools.base import Tool


class Input(BaseModel):
    customer_id: str | None = None
    amount_paise: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    narration_text: str | None = None


TOOL = Tool("search_bank_receipts", "Find bank statement receipts, including ones already in other cases "
            "(for split payments). Amounts in paise.", Input,
            lambda ctx, i: ctx.out(ctx.deps.core.search_bank_receipts(**i.model_dump())))
