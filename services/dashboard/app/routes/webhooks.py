from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import call, sales_rep, sales_manager, scheduled_call, company
from datetime import datetime, timedelta
from openai import OpenAI
import json
from ..services.bland_ai import BlandAI
from ..models.scheduled_call import CallType  # Add this import
from ..utils.date_calculator import DateCalculator
from sqlalchemy import func
import requests
from app.routes import call_rail, bland, company, sales_rep, sales_manager, calls, backend, user, delete
from app.routes.dependencies import client, bland_ai, date_calculator

#931980e753b188c6856ffaed726ef00a
router = APIRouter(prefix="/webhook", tags=["webhooks"])
router.include_router(backend.router)
router.include_router(bland.router)
router.include_router(call_rail.router)
router.include_router(calls.router)
router.include_router(company.router)
router.include_router(sales_manager.router)
router.include_router(sales_rep.router)
router.include_router(user.router)
router.include_router(delete.router)

