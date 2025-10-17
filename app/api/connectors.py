from fastapi import APIRouter
from app.connectors.sheets import list_sheets
from app.connectors.supabase import list_tables

router = APIRouter()


@router.get("/sheets/schema")
async def get_sheets_schema():
    return {"schema": list_sheets()}


@router.get("/supabase/schema")
async def get_supabase_schema():
    return {"schema": list_tables()}
