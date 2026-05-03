from fastapi import Request
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


def get_real_client_ip(request: Request) -> str:
    """
    Extracts the real IP address of the user from the FastAPI Request object.
    It checks common proxy and CDN headers before falling back to the 
    direct client connection host.
    """    
    # 1. Cloudflare specific header (if you use Cloudflare)
    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    if cf_connecting_ip:
        return cf_connecting_ip

    # 2. Standard header used by most proxies and load balancers
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # X-Forwarded-For can contain a comma-separated list of IPs.
        # The first IP in the list is the original client IP.
        real_ip = x_forwarded_for.split(",")[0].strip()
        return real_ip

    # 3. Another common proxy header (often used by Nginx)
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip

    # 4. Fallback: Direct connection IP (works on localhost or exposed servers)
    if request.client and request.client.host:
        return request.client.host

    # 5. Failsafe default if everything else is missing
    return "Unknown"