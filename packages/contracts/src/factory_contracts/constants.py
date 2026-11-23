"""Names shared by the API, the worker, and the orchestrator module."""

NOOP_WORKFLOW = "NoOpRequestWorkflow"
FACTORY_WORKFLOW = "FactoryRequestWorkflow"
TASK_QUEUE = "factory"
ORCHESTRATOR_MODULE = "orchestrator-temporal@0.1.0"
SESSION_SECRET_ENV = "FACTORY_SESSION_SECRET"
DEFAULT_SESSION_SECRET = "dev-session-secret"
