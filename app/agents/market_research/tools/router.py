from app.agents.market_research.schemas import MarketMode


def get_sources(mode: MarketMode) -> list[str]:
    mapping = {
        "egypt": ["wuzzuf", "bayt", "capmas", "jobspy"],
        "freelance": ["upwork", "mostaql", "khamsat", "jobspy"],
        "international": ["adzuna", "jobspy"],
    }

    return mapping[mode]