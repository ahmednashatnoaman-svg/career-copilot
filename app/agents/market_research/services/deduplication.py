def remove_duplicates(items: list[dict]) -> list[dict]:
    seen = set()
    result = []

    for item in items:
        key = str(item)

        if key not in seen:
            seen.add(key)
            result.append(item)

    return result