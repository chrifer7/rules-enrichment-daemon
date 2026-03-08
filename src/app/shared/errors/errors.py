class DaemonError(Exception):
    pass


class ExternalApiTimeoutError(DaemonError):
    pass


class ExternalApiUnavailableError(DaemonError):
    pass


class RuleEvaluationError(DaemonError):
    pass


class InvalidRuleDefinitionError(DaemonError):
    pass


class EnrichmentSubmissionError(DaemonError):
    pass


class DatabasePersistenceError(DaemonError):
    pass


class DeadLetterError(DaemonError):
    pass
