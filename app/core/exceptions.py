"""Application-specific exceptions and their FastAPI handlers."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for all domain errors. Carries an HTTP status code."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN


class UnsupportedFileTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        from app.core.logging import get_logger

        get_logger(__name__).exception("Unhandled exception on %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
