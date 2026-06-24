from app.agents.market_research.schemas import MarketMode


def get_sources(mode: MarketMode) -> list[str]:
    mapping = {
        "egypt": ["wuzzuf", "bayt", "capmas"],
        "freelance": ["upwork", "mostaql", "khamsat"],
        "international": ["adzuna"],
    }

    return mapping[mode]