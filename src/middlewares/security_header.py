from starlette.middleware.base import BaseHTTPMiddleware
from src.constants import Constants
from fastapi import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects strict security headers into all HTTP responses.
    Customized for a Headless API serving JSON and SVG assets (Manhwa Reader).
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 1. Prevent MIME type sniffing (Crucial for API and SVG security)
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # 2. Prevent Clickjacking (Ensures the API can't be loaded in iframes)
        response.headers["X-Frame-Options"] = "DENY"
        
        # 3. Cross-Origin Resource Policy (CORP)
        # "cross-origin" allows your frontend (ononougi.com) to load images/assets 
        # from this API via CORS, but blocks simple hotlinking by standard HTML tags on other sites.
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        
        # 4. Strict-Transport-Security (HSTS)
        # ONLY apply in production. If applied in localhost, it will permanently break your local dev environment.
        if Constants.IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # 5. Content Security Policy (CSP)
        # Since this is an API, CSP mostly protects endpoints that return images (like your SVG identicons)
        # preventing them from executing embedded malicious javascript.
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "frame-ancestors 'none'; "
            "img-src 'self' data: https:; " # Allows HTTPS images (like covers from S3/R2 buckets)
            "base-uri 'none'; "
            "form-action 'none';"
        )
        
        # 6. Referrer Policy (Protects user privacy when navigating away)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # 7. Permissions Policy (APIs do not need access to browser hardware)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=()"
        )
        
        # 8. Hide Server Information (Security through obscurity)
        # Safely uses 'del' to prevent AttributeError on MutableHeaders
        if "server" in response.headers:
            del response.headers["server"]
            
        # 9. Default Cache-Control for JSON APIs
        # Prevents browsers from caching sensitive JSON data (like /me or /admin/logs)
        # Note: Routes that NEED caching (like /identicons/avatar.svg) will overwrite this header natively in the route.
        if "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        
        return response