from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from src.core.db import init_db
from src.core.settings import Settings
from src.v1.auth.auth_router import auth_router

settings = Settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db(settings)
    yield


app = FastAPI(title="PYTA API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
)

app.include_router(auth_router)


@app.exception_handler(ValidationError)
async def validation_exception_handler(_request: Request, exc: ValidationError) -> JSONResponse:
    errors = exc.errors()[0]

    details = {
        "loc": errors["loc"],
        "msg": errors["msg"],
        "type": errors["type"],
    }

    return JSONResponse(status_code=422, content={"detail": details})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.port, reload=settings.debug)
