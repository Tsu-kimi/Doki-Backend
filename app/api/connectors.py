"""
Connector API routes for Google Sheets and Supabase integration.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from app.auth.dependencies import get_current_user
from app.connectors.sheets import list_user_spreadsheets, get_spreadsheet_schema
from app.connectors.supabase import (
    store_user_supabase_connection,
    test_user_supabase_connection,
    list_user_supabase_tables
)
from app.models.connectors import (
    SpreadsheetInfo,
    SpreadsheetSchema,
    SupabaseConnectionRequest,
    SupabaseConnectionResponse,
    TableSchema
)

router = APIRouter()


# ============================================================================
# Google Sheets Connector Routes
# ============================================================================

@router.get("/sheets/list", response_model=List[SpreadsheetInfo])
async def list_spreadsheets(user: dict = Depends(get_current_user)):
    """
    List all Google Spreadsheets accessible to the authenticated user.
    Requires Google OAuth connection via /auth/google/login.
    """
    try:
        spreadsheets = await list_user_spreadsheets(user["user_id"])
        return spreadsheets
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list spreadsheets: {str(e)}")


@router.get("/sheets/schema", response_model=SpreadsheetSchema)
async def get_sheets_schema(
    spreadsheet_id: str = Query(..., description="Google Spreadsheet ID"),
    user: dict = Depends(get_current_user)
):
    """
    Fetch schema for a specific Google Spreadsheet.
    Returns all tabs with their column headers.
    """
    try:
        schema = await get_spreadsheet_schema(user["user_id"], spreadsheet_id)
        return schema
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch spreadsheet schema: {str(e)}")


# ============================================================================
# Supabase User Connector Routes
# ============================================================================

@router.post("/supabase/connect", response_model=SupabaseConnectionResponse)
async def connect_supabase(
    request: SupabaseConnectionRequest,
    user: dict = Depends(get_current_user)
):
    """
    Connect user's own Supabase project by storing encrypted credentials.
    Requires project URL, anon key (optional), and service role key.
    """
    try:
        connection_id = await store_user_supabase_connection(
            user_id=user["user_id"],
            project_url=request.project_url,
            anon_key=request.anon_key,
            service_role_key=request.service_role_key
        )
        
        return SupabaseConnectionResponse(
            success=True,
            message="Supabase project connected successfully",
            connection_id=connection_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect Supabase: {str(e)}")


@router.get("/supabase/test")
async def test_supabase(user: dict = Depends(get_current_user)):
    """
    Test if user's Supabase connection is valid.
    Returns connection status.
    """
    try:
        is_valid = await test_user_supabase_connection(user["user_id"])
        
        if is_valid:
            return {"status": "connected", "message": "Connection verified"}
        else:
            return {"status": "disconnected", "message": "No connection found or connection invalid"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test connection: {str(e)}")


@router.get("/supabase/list", response_model=List[TableSchema])
async def list_supabase_tables(
    schema: str = Query("public", description="PostgreSQL schema name"),
    user: dict = Depends(get_current_user)
):
    """
    List all tables and columns from user's Supabase project.
    Returns table schemas with column information.
    """
    try:
        tables = await list_user_supabase_tables(user["user_id"], schema)
        return tables
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tables: {str(e)}")
