class QuLabException(Exception):
    """
    Base exception.
    """


###############################################################
# RPC Exceptions
###############################################################


class QuLabRPCError(QuLabException):
    """
    RPC base exception.
    """


class QuLabRPCServerError(QuLabRPCError):
    """
    Server side error.
    """


class QuLabRPCTimeout(QuLabRPCError):
    """
    Timeout.
    """


###############################################################
# DHT Exceptions
###############################################################


class QuLabDHTMalformedMessage(QuLabException):
    """
    Message does not contain what is expected.
    """
