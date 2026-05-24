from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request, status
import re


class BotDetectionMiddleware(BaseHTTPMiddleware):
    
    BLOCKED_PATTERNS = [
        r"scrapy",                    
        r"selenium|phantomjs",        
        r"headlesschrome",            
        r"bot|spider|crawl",          
        r"curl|wget",                 
        r"python-requests|httpx",     
    ]
    
    WHITELIST_PATTERNS = [
        r"chrome|firefox|safari|edge",  
        r"okhttp|dart",                 
        r"iphone|ipad|android",         
    ]

    def __init__(self, app):
        """
        Args:
            app: FastAPI app
        """
        super().__init__(app)             
        
        self.blocked_patterns_compiled = [re.compile(p, re.IGNORECASE) for p in self.BLOCKED_PATTERNS]
        self.whitelist_patterns_compiled = [re.compile(p, re.IGNORECASE) for p in self.WHITELIST_PATTERNS]    
    
    def _is_blocked_bot(self, user_agent: str) -> tuple[bool, str]:
        """
        Verifica se User-Agent é um bot conhecido.
        
        Returns:
            (is_blocked, reason)
        """
        if not user_agent:
            return True, "missing_user_agent"

        # Check for blocked patterns first
        for pattern in self.blocked_patterns_compiled:
            if pattern.search(user_agent):
                return True, f"blocked_pattern: {pattern.pattern}"
        
        # Check for whitelisted patterns
        for pattern in self.whitelist_patterns_compiled:
            if pattern.search(user_agent):
                return False, "whitelisted"
        
        
        return False, "allowed"
    
    
    async def dispatch(self, request: Request, call_next):
        user_agent = request.headers.get("user-agent", "").strip()
                
        is_blocked, ua_reason = self._is_blocked_bot(user_agent)
        
        if is_blocked:
            return Response(
                status_code=status.HTTP_403_FORBIDDEN,
                content="Access denied"
            )
                
        response = await call_next(request)        
        response.headers["X-Bot-Check"] = "passed"
        
        return response