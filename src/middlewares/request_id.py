from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import uuid


class RequestIDMiddleware(BaseHTTPMiddleware):
    
    """
    Generates a unique ID for each HTTP request.
    Attaches it to the internal request state and the external response headers
    for advanced tracing and debugging.
    """
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)        
        response.headers["X-Request-ID"] = request_id
        
        return response