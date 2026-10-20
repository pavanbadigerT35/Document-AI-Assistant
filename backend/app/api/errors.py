import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _body(request: Request, code: str, message: str, extra: dict | None = None) -> dict:
    body = {"error": {"code": code, "message": message, "request_id": request_id(request)}}
    if extra:
        body["error"].update(extra)
    return body


def install_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        try:
            response = await call_next(request)
        except Exception:  # last-resort handler: log the traceback, return a safe message
            log.exception("Unhandled error (request %s)", request.state.request_id)
            response = JSONResponse(_body(request, "internal_error", "Something went wrong on the server."), status_code=500)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(_body(request, exc.code, exc.message), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "problem": e["msg"]} for e in exc.errors()]
        return JSONResponse(_body(request, "validation_error", "The request was not valid.", {"details": details}), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return JSONResponse(_body(request, "http_error", str(exc.detail)), status_code=exc.status_code)
