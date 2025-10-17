"""
Pydantic models for connector API requests and responses.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# Google Sheets Connector Models
class SpreadsheetInfo(BaseModel):
    """Information about a Google Spreadsheet from Drive API."""
    id: str = Field(..., description="Spreadsheet file ID")
    name: str = Field(..., description="Spreadsheet name/title")
    modified_time: Optional[str] = Field(None, description="Last modified timestamp")
    web_view_link: Optional[str] = Field(None, description="Link to view in browser")


class SheetColumn(BaseModel):
    """Column information from a Google Sheet tab."""
    name: str = Field(..., description="Column header name")
    index: int = Field(..., description="Zero-based column index")


class SheetTab(BaseModel):
    """Tab/sheet information with columns."""
    sheet_name: str = Field(..., description="Name of the sheet tab")
    sheet_id: int = Field(..., description="Sheet ID")
    columns: List[SheetColumn] = Field(default_factory=list, description="Column headers")


class SpreadsheetSchema(BaseModel):
    """Complete schema for a spreadsheet with all tabs."""
    spreadsheet_id: str
    title: str
    sheets: List[SheetTab]


# Supabase Connector Models
class SupabaseConnectionRequest(BaseModel):
    """Request to connect a user's Supabase project."""
    project_url: str = Field(..., description="Supabase project URL (e.g., https://abc.supabase.co)")
    anon_key: Optional[str] = Field(None, description="Anon/publishable key (optional)")
    service_role_key: str = Field(..., description="Service role/secret key (required)")


class SupabaseConnectionResponse(BaseModel):
    """Response after connecting Supabase project."""
    success: bool
    message: str
    connection_id: Optional[str] = None


class TableColumn(BaseModel):
    """Supabase table column information."""
    name: str = Field(..., description="Column name")
    type: str = Field(..., description="PostgreSQL data type")
    is_nullable: bool = Field(default=True, description="Whether column allows NULL")
    default_value: Optional[str] = Field(None, description="Default value if any")


class TableSchema(BaseModel):
    """Schema for a Supabase table."""
    table_name: str
    schema: str = Field(default="public", description="PostgreSQL schema name")
    columns: List[TableColumn]


class SupabaseSchemaResponse(BaseModel):
    """Response containing list of tables and their schemas."""
    tables: List[TableSchema]
