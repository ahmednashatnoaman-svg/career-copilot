'''This file is probably redundant. Wasn't used once in the project'''

def calculate_confidence(source_count: int, recency_score: float) -> float:
    return min(1.0, (source_count * 0.3) + (recency_score * 0.7))