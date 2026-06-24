from app.agents.market_research.graph import market_agent_graph
from app.agents.market_research.schemas import MarketAgentInput  # noqa: F401


def market_node(state: dict) -> dict:
    """Supervisor-facing node: expects state['market_input']: MarketAgentInput."""
    result = market_agent_graph.invoke({"input": state["market_input"]})
    return {"market": result["validated_output"]}
