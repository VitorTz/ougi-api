from fastapi.exceptions import HTTPException
from typing import Any
from fastapi import status
from src.util import format_stacktrace


class CredentialsException(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials", headers: dict[str, str] | None = None):
        _headers = {"WWW-Authenticate": "Bearer"}
        if headers:
            _headers.update(headers)
            
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=_headers
        )


class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "You do not have permission to perform this action."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class AccountNotFoundException(HTTPException):
    def __init__(self, detail: str = "User account no longer exists or is invalid."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )


class MaxLoginAttemptException(HTTPException):
    def __init__(self, detail: str = "Too many failed login attempts. Please try again in 15 minutes."):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail
        )


class EmptyUpdateException(HTTPException):
    def __init__(self, detail: str = "No valid fields provided for update."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

class ConflictException(HTTPException):

    """
    Exception raised when a request conflicts with the current state of the server.
    Useful for duplicate unique constraints (e.g., email already registered).
    """

    def __init__(self, detail: str = "Resource already exists or conflicts with current state."):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )


class ResourceNotFoundException(HTTPException):
    """
    Exception raised when a requested resource does not exist in the database.
    """

    def __init__(self, resource_name: str = "Resource"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} not found."
        )


class BusinessRuleException(HTTPException):
    """
    Exception raised for domain logic violations that result in a bad request.
    """

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class AccountSuspendedException(HTTPException):
    """
    Exception raised when a user attempts to authenticate with a banned or inactive account.
    """
    def __init__(self, detail: str = "Your account has been suspended or is currently inactive."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class DuplicateRecordError(Exception):
    
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(self.detail)


class DatabaseException(Exception):
    """
    Custom exception to handle database errors, separating the client-facing 
    message from the detailed internal log data.
    """
    def __init__(
        self, 
        client_message: str, 
        original_error: Exception,
        query: str | None = None,
        params: Any = None,
        additional_context: dict | None = None,
        user_id: str | None = None
    ):
        super().__init__(str(original_error))
        self.client_message = client_message
        self.original_error = original_error
        self.error_type = type(original_error).__name__
        self.query = query
        self.params = params
        self.query_parameters = str(params) if params else None
        self.context = additional_context or {}
        self.user_id = user_id
        self.traceback_str = format_stacktrace(original_error)
        self.error_message = str(self.original_error)