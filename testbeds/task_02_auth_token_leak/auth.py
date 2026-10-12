import re

def format_auth_log(header_value: str) -> str:
    """
    Formats authorization header for operational logs.
    Bug: logs entire raw secret token instead of masking it.
    """
    if not header_value.startswith("Bearer "):
        return f"Auth: {header_value}"

    raw_token = header_value.split("Bearer ", 1)[1]
    # BUG: plain-text token leak
    return f"Auth: Bearer {raw_token}"
