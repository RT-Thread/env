"""Domain errors exposed by the Env plugin subsystem."""


class PluginError(Exception):
    exit_code = 4


class UsageError(PluginError):
    exit_code = 2


class PackageError(PluginError):
    exit_code = 3


class ManifestError(PackageError):
    pass


class IntegrityError(PackageError):
    pass


class CompatibilityError(PackageError):
    pass


class CommandConflictError(PackageError):
    pass


class StateError(PluginError):
    pass


class TransactionError(PluginError):
    pass


class DispatchError(PluginError):
    exit_code = 5


class PermissionDenied(DispatchError):
    pass


class WorkspaceBoundaryError(PermissionDenied):
    pass
