from fastapi import status
from fastapi.exceptions import HTTPException
from typing import Any, Optional, Dict
import traceback



CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
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
    

class DuplicateRecordError(Exception):
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)