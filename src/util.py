from fastapi import Request
from src.constants import Constants
from datetime import datetime, timezone, date
from difflib import SequenceMatcher
from typing import Any
import math
import unicodedata
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


def is_of_legal_age(birthdate: date, legal_age: int = 18) -> bool:
    """
    Checks if a user is of legal age (default 18+) based on their birthdate.
    Essential for restricting access to adult manhwa content.
    """
    today = date.today()
    age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
    return age >= legal_age


def is_valid_image_signature(header_bytes: bytes) -> bool:
    """
    Validates if an uploaded file is a genuine image (JPEG, PNG, WEBP, GIF)
    by checking its 'magic numbers' (file signatures).
    Pass the first 12 bytes of the file (e.g., file.read(12)) to this function.
    """
    signatures = {
        b'\xff\xd8\xff': 'jpeg',
        b'\x89PNG\r\n\x1a\n': 'png',
        b'GIF87a': 'gif',
        b'GIF89a': 'gif',
    }
    
    # WEBP signatures have 'RIFF' at the start and 'WEBP' at bytes 8-11
    if header_bytes.startswith(b'RIFF') and header_bytes[8:12] == b'WEBP':
        return True
        
    for signature in signatures:
        if header_bytes.startswith(signature):
            return True
            
    return False


def generate_slug(title: str) -> str:
    normalized = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('utf-8')
    normalized = normalized.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', normalized)
    return slug.strip('-')


def get_pagination_metadata(total_items: int, limit: int, offset: int) -> dict[str, Any]:
    """
    Generates standardized pagination metadata to attach to your API responses.
    This makes it infinitely easier for the frontend to render 'Next/Prev' buttons.
    """
    safe_limit = limit if limit > 0 else 1 
    
    current_page = math.floor(offset / safe_limit) + 1
    total_pages = math.ceil(total_items / safe_limit)
    
    return {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": current_page,
        "has_next": current_page < total_pages,
        "has_previous": current_page > 1,
        "limit": limit,
        "offset": offset
    }


def redact_sensitive_data(payload: dict) -> dict:
    """
    Recursively scans a dictionary and masks sensitive fields (like passwords or tokens).
    Extremely useful before saving JSON payloads to your audit logs or system logs.
    """
    sensitive_keys = {
        'password', 
        'password_hash', 
        'token', 
        'access_token', 
        'refresh_token', 
        'credit_card'
    }
    redacted = {}
    
    for key, value in payload.items():
        if isinstance(value, dict):
            redacted[key] = redact_sensitive_data(value)
        elif key.lower() in sensitive_keys:
            redacted[key] = "********"
        else:
            redacted[key] = value
            
    return redacted