"""Combined Ginflow routing and completion gate plugin."""

from . import block_routing, gate, routing


def register(ctx) -> None:
    routing.register(ctx)
    block_routing.register(ctx)
    gate.register(ctx)


pre_tool_call = gate.pre_tool_call
post_tool_call = gate.post_tool_call
validate_completion = gate.validate_completion
load_card = gate.load_card

__all__ = ["register", "pre_tool_call", "post_tool_call", "validate_completion", "load_card"]
