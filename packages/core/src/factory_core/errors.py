"""Errors raised by the core. Modules raise ContractError instead."""


class FactoryError(Exception):
    """Base class for core failures."""


class PolicyError(FactoryError):
    """A resolved config violates policy."""


class LoaderError(FactoryError):
    """A module entry point or manifest is invalid."""


class RegistryError(FactoryError):
    """An agent or skill version cannot be stored or found."""
