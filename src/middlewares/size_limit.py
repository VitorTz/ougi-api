from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers
from fastapi.responses import JSONResponse
from fastapi import Request, status


class RequestSizeLimitASGIMiddleware:
    
    
    def __init__(self, app, max_upload_size: int = 10 * 1024 * 1024):
        self.app = app
        self.max_upload_size = max_upload_size
    
    async def __call__(self, scope, receive, send):
        """ASGI interface"""
        
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        method = scope.get("method", "GET")
        if method not in ["POST", "PUT", "PATCH"]:
            await self.app(scope, receive, send)
            return
        
        # Check Content-Length header (ultra fast)
        headers = Headers(scope=scope)
        content_length = headers.get("content-length")
        
        if content_length:
            try:
                if int(content_length) > self.max_upload_size:
                    await send({
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [[b"content-type", b"application/json"]],
                    })
                    await send({
                        "type": "http.response.body",
                        "body": b'{"detail":"Request body too large"}',
                    })
                    return
            except ValueError:
                pass
        
        # Monitor chunked transfers without consuming
        body_received = 0
        
        async def receive_with_check():
            nonlocal body_received
            
            message = await receive()
            
            if message["type"] == "http.request":
                body_received += len(message.get("body", b""))
                
                if body_received > self.max_upload_size:
                    await send({
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [[b"content-type", b"application/json"]],
                    })
                    await send({
                        "type": "http.response.body",
                        "body": b'{"detail":"Request body too large"}',
                    })
                    return {"type": "http.disconnect"}
            
            return message
        
        # Call app with wrapped receive
        await self.app(scope, receive_with_check, send)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Limits the total size of HTTP requests to prevent DoS attacks via Memory Exhaustion (OOM).
    
    ⚠️ IMPORTANT: This middleware does NOT consume the request body.
    It validates at the ASGI level using a wrapper around `receive()` callable.
    
    - Fast: Checks Content-Length header first (O(1))
    - Reliable: Monitors actual bytes received for chunked transfers
    - Non-blocking: Doesn't consume the stream
    """
    
    def __init__(self, app, max_upload_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_upload_size = max_upload_size
    
    async def dispatch(self, request: Request, call_next):
        """
        Dispatch with size limit validation.
        Does NOT consume request.stream() or body.
        """
        
        # Only check for methods that have bodies
        if request.method not in ["POST", "PUT", "PATCH"]:
            return await call_next(request)
        
        # ===== FAST PATH: Check Content-Length header =====
        content_length = request.headers.get("content-length")
        
        if content_length:
            try:
                declared_size = int(content_length)
                if declared_size > self.max_upload_size:
                    print(
                        f"Request rejected: Content-Length {declared_size} "
                        f"exceeds limit {self.max_upload_size}"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "detail": (
                                f"Request body too large. "
                                f"Max size: {self.max_upload_size} bytes, "
                                f"received: {declared_size} bytes"
                            )
                        }
                    )
            except (ValueError, TypeError):
                print("Invalid Content-Length header")
                pass  # Invalid header, check actual stream below
        
        # ===== RELIABLE PATH: Monitor chunked transfers =====
        # Wrap the receive callable to monitor size without consuming
        body_received = 0
        original_receive = request._receive
        
        async def receive_with_size_check():
            """
            Wrapper around receive() that monitors total bytes
            without consuming the request body.
            """
            nonlocal body_received
            
            # Call the original receive
            message = await original_receive()
            
            # Monitor body chunks (but don't consume)
            if message["type"] == "http.request":
                chunk_size = len(message.get("body", b""))
                body_received += chunk_size
                
                # Check if exceeded
                if body_received > self.max_upload_size:
                    print(
                        f"Request rejected: Total size {body_received} "
                        f"exceeds limit {self.max_upload_size}"
                    )
                    # Return error message instead of actual data
                    return {
                        "type": "http.disconnect",
                        "body": b""
                    }
            
            return message
        
        # Replace receive with our wrapper (non-destructive)
        request._receive = receive_with_size_check
        
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            print(f"Error in RequestSizeLimitMiddleware: {e}")
            raise
 
 
# ============================================================================
# Alternative: Ultra-lightweight version if you're confident about Content-Length
# ============================================================================
 
class RequestSizeLimitMiddlewareLight(BaseHTTPMiddleware):
    """
    Lightweight version: Only checks Content-Length header.
    Use if your clients always send Content-Length (browser, curl, httpx).
    
    Benefits:
    - Zero overhead for request body
    - O(1) complexity
    - No stream wrapping
    
    Limitations:
    - Won't catch requests without Content-Length
    - Vulnerable to falsified headers (unless frontend validates)
    """
    
    def __init__(self, app, max_upload_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_upload_size = max_upload_size
    
    async def dispatch(self, request: Request, call_next):
        if request.method not in ["POST", "PUT", "PATCH"]:
            return await call_next(request)
        
        content_length = request.headers.get("content-length")
        
        if content_length:
            try:
                if int(content_length) > self.max_upload_size:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"detail": "Request body too large"}
                    )
            except ValueError:
                pass
        
        return await call_next(request)
