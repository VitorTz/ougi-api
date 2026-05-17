from fastapi.exceptions import HTTPException
from typing import Any, Optional, Dict
from fastapi import status
import traceback



CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


FORBIDDEN_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="You do not have permission to perform this action.",
)


ACCOUNT_NOT_FOUND_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, 
    detail='User account no longer exists or is invalid.'
)


MAX_LOGIN_ATTEMPT_EXCEPTION = HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Too many failed login attempts. Please try again in 15 minutes."
)


EMPTY_UPDATE_EXCEPTION = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST, 
    detail="No valid fields provided for update."
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


class DuplicateRecordError(HTTPException):
    
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )


class DatabaseException(Exception):
    """
    Custom exception to handle database errors, separating the client-facing 
    message from the detailed internal log data.
    """
    def __init__(
        self, 
        client_message: str, 
        original_error: Exception,
        query: Optional[str] = None,
        params: Optional[Any] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ):
        super().__init__(str(original_error))
        self.client_message = client_message
        self.original_error = original_error
        self.error_type = type(original_error).__name__
        self.query = query
        self.params = params
        self.context = additional_context or {}
        self.user_id = user_id
        self.traceback_str = "".join(
            traceback.format_exception(
                type(original_error), 
                original_error, 
                original_error.__traceback__
            )
        )

    def get_client_response(self) -> dict:
        """
        Returns a dictionary safe to be serialized as JSON and sent to the frontend.
        """
        return {
            "error": self.client_message
        }

    def get_log_payload(self) -> dict:
        """
        Returns a comprehensive dictionary to be inserted into your error logs table.
        """
        return {
            "error_type": self.error_type,
            "error_message": str(self.original_error),
            "failed_query": self.query,
            "query_parameters": str(self.params) if self.params else None,
            "user_id": self.user_id,
            "execution_context": self.context,
            "stack_trace": self.traceback_str
        }
    