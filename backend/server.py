import os
import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core import db, client
from auth import auth_router, seed_users
from api import api
from worker import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("server")

app = FastAPI(title="Smartize Outreach")

app.include_router(auth_router)
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await seed_users()
    await db.users.create_index("email", unique=True)
    await db.contacts.create_index("email")
    await db.contacts.create_index("group_id")
    await db.email_jobs.create_index("campaign_id")
    await db.email_jobs.create_index("tracking_id")
    await db.email_jobs.create_index("status")
    start_scheduler()
    logger.info("Smartize Outreach backend iniciado.")


@app.on_event("shutdown")
async def shutdown():
    client.close()


@app.get("/api/")
async def root():
    return {"message": "Smartize Outreach API"}
