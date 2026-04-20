from __future__ import annotations


class BrokerConnectorError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        response_body: dict | str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        self.retryable = retryable

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "status_code": self.status_code,
            "response_body": self.response_body,
            "retryable": self.retryable,
        }
