from fastapi import APIRouter

router = APIRouter()


@router.get("/sheets/schema")
async def get_sheets_schema():
    return {"schema": []}


@router.get("/supabase/schema")
async def get_supabase_schema():
    return {"schema": []}
