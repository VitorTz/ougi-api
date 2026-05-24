from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from fastapi import Request, status


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Limits the total size of HTTP requests to prevent DoS attacks via Memory Exhaustion (OOM).
    Safely handles falsified Content-Length headers and chunked transfers.
    """
    
    def __init__(self, app, max_upload_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_upload_size = max_upload_size

    async def dispatch(self, request: Request, call_next):
        if request.method not in ["POST", "PUT", "PATCH"]:
            return await call_next(request)
                
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_upload_size:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body too large (Declared by Content-Length)."}
            )
                
        body_bytes = 0
        async for chunk in request.stream():
            body_bytes += len(chunk)
            if body_bytes > self.max_upload_size:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": "Request body too large (Exceeded max streaming size)."}
                )
                        
        return await call_next(request)