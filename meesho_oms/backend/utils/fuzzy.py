"""
Fuzzy matching: map OCR-extracted item names to stock item names.
Uses fuzzywuzzy (Levenshtein distance).
"""
from fuzzywuzzy import fuzz, process


def find_best_stock_match(ocr_name: str, stock_items: list[str],
                          threshold: int = 70) -> tuple[str | None, int]:
    """
    Return (best_match_name, score) or (None, 0) if no match above threshold.
    stock_items: list of item_name strings from stock table.
    """
    if not stock_items:
        return None, 0
    result = process.extractOne(
        ocr_name,
        stock_items,
        scorer=fuzz.token_set_ratio
    )
    if result and result[1] >= threshold:
        return result[0], result[1]
    return None, 0


def fuzzy_deduplicate(items: list[dict]) -> list[dict]:
    """
    Within a parsed invoice, merge duplicate items
    (same item OCR'd twice on different lines).
    """
    seen: list[dict] = []
    for item in items:
        matched = False
        for s in seen:
            if fuzz.token_set_ratio(item["item_name"], s["item_name"]) >= 85:
                s["qty"] += item["qty"]
                matched = True
                break
        if not matched:
            seen.append(dict(item))
    return seen
