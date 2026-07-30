from __future__ import annotations


class RNDSConnectorError(RuntimeError):
    """Base error that never carries tokens, credentials, or clinical payloads."""

    retryable = False


class RNDSConfigurationError(RNDSConnectorError):
    pass


class RNDSBundleValidationError(RNDSConnectorError):
    pass


class RNDSAuthenticationError(RNDSConnectorError):
    """Authentication can be retried because no clinical payload was submitted."""

    retryable = True


class RNDSServerRejectedError(RNDSConnectorError):
    def __init__(self, status_code: int, outcome_codes: tuple[str, ...] = ()):
        self.status_code = int(status_code)
        self.outcome_codes = tuple(outcome_codes)
        suffix = f" (OperationOutcome codes: {', '.join(self.outcome_codes)})" if self.outcome_codes else ""
        super().__init__(f"RNDS rejected the request with HTTP {self.status_code}{suffix}")


class RNDSUnknownSubmissionStateError(RNDSConnectorError):
    """The operator must reconcile before attempting another submission."""


class RNDSUnsupportedOperationError(RNDSConnectorError):
    pass
