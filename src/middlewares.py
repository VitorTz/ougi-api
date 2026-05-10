from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from datetime import datetime
import uuid
import logging
import time



class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adiciona headers de segurança em todas as respostas.
    Previne: MIME sniffing, clickjacking, XSS refletido
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Previne MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Previne clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Ou se precisa de iframes internos:
        # response.headers["X-Frame-Options"] = "SAMEORIGIN"
        
        # XSS Protection (legacy, mas útil)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # HSTS (força HTTPS)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # Content Security Policy (customizado para imagens de manhwas)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "img-src 'self' data: https:; "  # Permite imagens HTTPS
            "style-src 'self' 'unsafe-inline'; "  # Se precisar CSS inline
            "font-src 'self'; "
            "connect-src 'self' https:; "
            "media-src 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none'"
        )
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (ex: desabilita microfone/câmera)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=()"
        )
        
        # Remover header sensível do Uvicorn
        response.headers.pop("server", None)
        
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Adiciona um Request ID único para rastreamento.
    Facilita debugging em logs distribuídos.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Tenta usar X-Request-ID se vier do cliente, senão gera novo
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        
        # Armazena em request.state para usar em handlers
        request.state.request_id = request_id
        
        response = await call_next(request)
        
        # Adiciona na resposta para o cliente rastrear
        response.headers["X-Request-ID"] = request_id
        
        return response


class BotDetectionMiddleware(BaseHTTPMiddleware):
    """
    Detecta e bloqueia bots/scrapers agressivos.
    Bloqueia User-Agents suspeitos que tentam ler chapters em massa.
    """
    
    # User-Agents de bots conhecidos
    BLOCKED_USER_AGENTS = {
        "scrapy",
        "curl",
        "wget",
        "python",
        "requests",
        "go-http-client",
        "java",
        "okhttp",
        "selenium",
        "phantomjs",
        "headlesschrome",
    }
    
    async def dispatch(self, request: Request, call_next):
        user_agent = request.headers.get("user-agent", "").lower()
        
        # Se algum bot-keyword estiver no User-Agent
        if any(bot in user_agent for bot in self.BLOCKED_USER_AGENTS):
            if not request.url.path.startswith("/health"):
                # Pode retornar 403 ou deixar passar por rate limit
                return Response(status_code=403, content="Forbidden")
        
        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Limita tamanho de requisições para prevenir DoS.
    """
    
    def __init__(self, app, max_upload_size: int = 10 * 1024 * 1024):  # 10MB padrão
        super().__init__(app)
        self.max_upload_size = max_upload_size
    
    async def dispatch(self, request: Request, call_next):
        # Checa Content-Length header
        content_length = request.headers.get("content-length")
        
        if content_length and int(content_length) > self.max_upload_size:
            return Response(
                status_code=413,
                content={"detail": "Request body too large"}
            )
        
        return await call_next(request)
