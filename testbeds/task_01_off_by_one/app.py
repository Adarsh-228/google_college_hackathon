from typing import List, Any

def paginate(items: List[Any], page: int, size: int) -> List[Any]:
    """
    Returns items for a 1-indexed page number.
    Bug: slice upper bound subtracts 1 unnecessarily.
    """
    if page < 1 or size < 1:
        return []
    start = (page - 1) * size
    # BUG: off-by-one slice upper bound
    return items[start : start + size - 1]
