from app.agents.market_research.graph import market_agent_graph
from app.agents.market_research.schemas import MarketAgentInput  # noqa: F401


def market_node(state: dict) -> dict:
    """Supervisor-facing node: expects state['market_input']: MarketAgentInput."""
    market_input = state["market_input"]
    # Serialize the initial state as a plain dict so the parent PostgresSaver
    # can checkpoint it via msgpack without hitting Pydantic model type errors.
    initial = {
        "input": market_input.model_dump(mode="json")
        if hasattr(market_input, "model_dump")
        else market_input
    }
    result = market_agent_graph.invoke(initial)
    validated = result.get("validated_output")
    if hasattr(validated, "model_dump"):
        validated = validated.model_dump(mode="json")
    return {"market": validated}
