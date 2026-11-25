from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class AppException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "bad_request",
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, status.HTTP_401_UNAUTHORIZED, "unauthorized")


class ForbiddenError(AppException):
    def __init__(self, message: str = "You do not have permission to perform this action") -> None:
        super().__init__(message, status.HTTP_403_FORBIDDEN, "forbidden")


class NotFoundError(AppException):
    def __init__(self, message: str = "Requested resource was not found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND, "not_found")


class ConflictError(AppException):
    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(message, status.HTTP_409_CONFLICT, "conflict")


class TooManyRequestsError(AppException):
    def __init__(self, message: str = "Too many attempts. Please try again later.") -> None:
        super().__init__(message, status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(loc) for loc in err["loc"] if loc != "body"),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation failed",
                "code": "validation_error",
                "errors": errors,
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, __: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "A record with conflicting unique values already exists.",
                "code": "integrity_conflict",
            },
        )
