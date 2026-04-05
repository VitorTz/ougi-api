from slowapi import Limiter
from src.util import get_real_client_ip


limiter = Limiter(key_func=get_real_client_ip)