import re
from typing import List

def extract_ip_addresses(log_text: str) -> List[str]:
    """
    Extracts IPv4 addresses from log entries.
    BUG: regex misses matching proper boundary or octet limits.
    """
    # BUG: captures digits without proper boundary check
    pattern = r"\d+\.\d+\.\d+\.\d+"
    return re.findall(pattern, log_text)
