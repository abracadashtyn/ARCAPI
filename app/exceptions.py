class AlreadyExistsException(Exception):
    """Raised when attempting to create a resource that already exists"""
    pass

class CustomGameException(Exception):
    """Raised when a match's game format is custom and so the detail log does not match the expected format"""
    pass