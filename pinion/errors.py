class PinionError(Exception):
    pass


class TaskNotFound(PinionError):
    pass


class TaskExecutionError(PinionError):
    pass

