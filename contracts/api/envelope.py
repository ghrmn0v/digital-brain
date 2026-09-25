"""Request/response envelope for the platform-independent Brain API.

Transport-agnostic JSON-RPC-shaped envelope. A client sends an
:class:`ApiRequest`; the service answers with a typed :class:`ApiResponse`.

- ``params`` is a generic payload dict — each method validates it against its
  own typed ``contracts.api.params`` model on arrival.
- ``result`` is the typed per-method payload model from ``contracts.api.results``.
- Every response carries its request ``id`` so a client can pair answers.
- A response is exactly one of ``ok + result`` / ``error`` (validated).

Only contracts here — no parsing loop, no IO, no transport.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from contracts.common.types import ContractVersion, Source

from .errors import ApiError
from .methods import ApiMethod

T = TypeVar("T")


class ApiRequest(BaseModel):
    """One client message. ``params`` is validated per-method on arrival."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    method: ApiMethod
    version: ContractVersion = "v1"
    params: dict[str, Any] = Field(default_factory=dict)
    source: Source | None = None

    @field_validator("id")
    @classmethod
    def _strip_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


class ApiResponse(BaseModel, Generic[T]):
    """A typed answer to one :class:`ApiRequest`."""

    model_config = ConfigDict(extra="forbid")

    id: str
    method: ApiMethod | None = None
    version: ContractVersion = "v1"
    ok: bool
    result: T | None = None
    error: ApiError | None = None

    @model_validator(mode="after")
    def _ok_or_error(self) -> "ApiResponse[T]":
        if self.ok and self.error is not None:
            raise ValueError("ok response cannot carry an error")
        if self.ok and self.result is None:
            raise ValueError("ok response requires a result payload")
        if not self.ok and self.result is not None:
            raise ValueError("error response cannot carry a result")
        if not self.ok and self.error is None:
            raise ValueError("error response requires an error payload")
        return self

    @field_validator("id")
    @classmethod
    def _strip_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


def ok_response(
    request_id: str,
    method: ApiMethod,
    result: T,
    *,
    version: ContractVersion = "v1",
) -> ApiResponse[T]:
    """Build a typed success response."""
    return ApiResponse[T](
        id=request_id,
        method=method,
        version=version,
        ok=True,
        result=result,
    )


def error_response(
    request_id: str,
    method: ApiMethod | None,
    error: ApiError,
    *,
    version: ContractVersion = "v1",
) -> ApiResponse[None]:
    """Build a typed failure response."""
    return ApiResponse[None](
        id=request_id,
        method=method,
        version=version,
        ok=False,
        error=error,
    )