from pydantic import BaseModel

from artemis.tools.base import Tool


class Input(BaseModel):
    name_raw: str


TOOL = Tool("resolve_customer", "Candidate customers with match scores for a payer name as printed by the "
            "bank.", Input, lambda ctx, i: ctx.out(ctx.deps.core.resolve_customer(i.name_raw)))
