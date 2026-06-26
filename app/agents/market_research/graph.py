from langgraph.graph import END, START, StateGraph

from app.agents.market_research.nodes.planner import planner_node
from app.agents.market_research.nodes.postings import postings_node
from app.agents.market_research.nodes.salaries import salaries_node
from app.agents.market_research.nodes.skill_gap import skill_gap_node
from app.agents.market_research.nodes.trends import trends_node
from app.agents.market_research.nodes.validator import validator_node
from app.agents.market_research.state import MarketAgentState

builder = StateGraph(MarketAgentState)

builder.add_node("planner", planner_node)

builder.add_node("postings", postings_node)
builder.add_node("salaries", salaries_node)
builder.add_node("trends", trends_node)

builder.add_node("skill_gap", skill_gap_node)

builder.add_node("validator", validator_node)

builder.add_edge(START, "planner")

builder.add_edge("planner", "postings")
builder.add_edge("planner", "salaries")
builder.add_edge("planner", "trends")

builder.add_edge("postings", "skill_gap")
builder.add_edge("salaries", "skill_gap")
builder.add_edge("trends", "skill_gap")

builder.add_edge("skill_gap", "validator")

builder.add_edge("validator", END)

market_agent_graph = builder.compile()