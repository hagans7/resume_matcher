"""Base response schemas — consistent JSON envelope for all API responses.

Every endpoint returns either SuccessResponse or ErrorResponse.
Consistent shape: { success, data, error }
"""

from typing import Any

from pydantic import BaseModel


class SuccessResponse(BaseModel):
    success: bool = True
    data: Any
    error: None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: dict | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    data: None = None
    error: ErrorDetail
