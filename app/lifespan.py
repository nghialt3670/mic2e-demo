import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MIC2E Demo application startup")
    yield
    logger.info("MIC2E Demo application shutdown")
