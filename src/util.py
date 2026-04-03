from src.constants import Constants
from datetime import datetime, timezone
from difflib import SequenceMatcher
import re


def seconds_until(target: datetime) -> int:
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = (target - now).total_seconds()
    return int(diff) if diff > 0 else 0


def is_impostor_name(username: str) -> bool:
    """
    Detects if a user is trying to impersonate a celestial entity.
    Returns True if the name is forbidden, False if it is safe.
    """
    # 1. Lowercase and remove all non-alphanumeric characters (including spaces, _, -)
    clean_name = re.sub(r'[^a-z0-9]', '', username.lower())
    
    # 2. Translate 'Leetspeak' (Hacker slang) back to standard characters
    leetspeak_map = {
        '0': 'o',
        '1': 'i',
        '3': 'e',
        '4': 'a',
        '5': 's',
        '7': 't',
        '8': 'b',
        '@': 'a',
        '!': 'i'
    }
    
    translated_name = "".join(leetspeak_map.get(char, char) for char in clean_name)
    
    for restricted in Constants.RESTRICTED_NAMES:
        if restricted in translated_name:
            return True
    
    for restricted in Constants.RESTRICTED_NAMES:
        similarity = SequenceMatcher(None, translated_name, restricted).ratio()            
        if similarity > 0.75:
            return True
            
    return False