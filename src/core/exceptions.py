class TaskQueueBaseError(Exception):
    """Excepción base del sistema. Todas las excepciones custom heredan de esta."""
    pass

class ValidationError(TaskQueueBaseError):
    """Se lanza cuando un payload o archivo no pasa las validaciones de negocio."""
    pass

class SecurityError(TaskQueueBaseError):
    """Se lanza ante intentos de operaciones inseguras o inputs maliciosos."""
    pass

class StorageError(TaskQueueBaseError):
    """Se lanza ante fallos en lectura/escritura de archivos."""
    pass

class TaskEnqueueError(TaskQueueBaseError):
    """Se lanza cuando no se puede encolar una tarea correctamente."""
    pass

class TaskNotFoundError(TaskQueueBaseError):
    """Se lanza cuando se consulta un job que no existe en la base de datos."""
    pass