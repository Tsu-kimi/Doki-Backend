"""
Google Sheets connector for listing spreadsheets and fetching schemas.
Uses Google Drive API for listing files and Sheets API for schema introspection.
"""
from typing import List, Dict, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.connectors.supabase import get_supabase_client
from app.core.encryption import decrypt_token_from_storage
from app.auth.dependencies import get_google_oauth_config
from app.models.connectors import SpreadsheetInfo, SpreadsheetSchema, SheetTab, SheetColumn


async def get_user_google_credentials(user_id: str) -> Optional[Credentials]:
    """
    Retrieve and decrypt user's Google OAuth credentials from database.
    
    Args:
        user_id: User's Supabase auth ID
        
    Returns:
        Google OAuth Credentials object or None if not found
    """
    supabase = get_supabase_client()
    
    # Fetch credentials from database
    response = supabase.table("credentials")\
        .select("*")\
        .eq("user_id", user_id)\
        .eq("provider", "google")\
        .execute()
    
    if not response.data or len(response.data) == 0:
        return None
    
    cred_data = response.data[0]
    
    try:
        # Decrypt tokens
        access_token = decrypt_token_from_storage(cred_data["access_token_encrypted"])
        refresh_token = decrypt_token_from_storage(cred_data.get("refresh_token_encrypted")) if cred_data.get("refresh_token_encrypted") else None
        
        print(f"Decrypted access_token length: {len(access_token) if access_token else 0}")
        print(f"Decrypted refresh_token length: {len(refresh_token) if refresh_token else 0}")
        
        # Get OAuth config for client_id and client_secret (needed for token refresh)
        oauth_config = get_google_oauth_config()
        
        # Build Credentials object
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=oauth_config["client_id"],
            client_secret=oauth_config["client_secret"],
        )
        
        print(f"Credentials object created successfully")
        return credentials
        
    except Exception as e:
        print(f"Error in get_user_google_credentials: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


async def list_user_spreadsheets(user_id: str) -> List[SpreadsheetInfo]:
    """
    List all Google Spreadsheets accessible to the user via Drive API.
    
    Args:
        user_id: User's Supabase auth ID
        
    Returns:
        List of SpreadsheetInfo objects
        
    Raises:
        HTTPException: If credentials not found or API call fails
    """
    credentials = await get_user_google_credentials(user_id)
    if not credentials:
        raise ValueError("Google credentials not found for user")
    
    try:
        # Build Drive API service
        service = build('drive', 'v3', credentials=credentials)
        
        # Query for spreadsheets only
        query = "mimeType='application/vnd.google-apps.spreadsheet'"
        
        # List spreadsheets
        results = service.files().list(
            q=query,
            pageSize=100,
            fields="files(id, name, modifiedTime, webViewLink)",
            orderBy="modifiedTime desc"
        ).execute()
        
        files = results.get('files', [])
        
        # Convert to SpreadsheetInfo objects
        spreadsheets = [
            SpreadsheetInfo(
                id=file['id'],
                name=file['name'],
                modified_time=file.get('modifiedTime'),
                web_view_link=file.get('webViewLink')
            )
            for file in files
        ]
        
        return spreadsheets
        
    except HttpError as error:
        print(f"Google API HttpError: status={error.resp.status}, reason={error._get_reason()}")
        if error.resp.status == 401:
            raise ValueError("Invalid or expired Google credentials. Please re-authenticate.")
        raise ValueError(f"Google Drive API error: {error}")
    except Exception as e:
        print(f"Unexpected error in list_user_spreadsheets: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


async def get_spreadsheet_schema(user_id: str, spreadsheet_id: str) -> SpreadsheetSchema:
    """
    Fetch schema for a specific spreadsheet including all tabs and columns.
    
    Args:
        user_id: User's Supabase auth ID
        spreadsheet_id: Google Spreadsheet ID
        
    Returns:
        SpreadsheetSchema with tabs and column headers
        
    Raises:
        HTTPException: If credentials not found or API call fails
    """
    credentials = await get_user_google_credentials(user_id)
    if not credentials:
        raise ValueError("Google credentials not found for user")
    
    try:
        # Build Sheets API service
        service = build('sheets', 'v4', credentials=credentials)
        
        # Get spreadsheet metadata (includeGridData=False for performance)
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            includeGridData=False
        ).execute()
        
        title = spreadsheet.get('properties', {}).get('title', 'Untitled')
        sheets_data = spreadsheet.get('sheets', [])
        
        # Parse each sheet/tab
        sheet_tabs = []
        for sheet in sheets_data:
            properties = sheet.get('properties', {})
            sheet_name = properties.get('title', 'Untitled Sheet')
            sheet_id = properties.get('sheetId', 0)
            
            # Fetch first row to get column headers
            range_name = f"'{sheet_name}'!1:1"
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            headers = values[0] if values else []
            
            # Build column list
            columns = [
                SheetColumn(name=header, index=idx)
                for idx, header in enumerate(headers)
            ]
            
            sheet_tabs.append(SheetTab(
                sheet_name=sheet_name,
                sheet_id=sheet_id,
                columns=columns
            ))
        
        return SpreadsheetSchema(
            spreadsheet_id=spreadsheet_id,
            title=title,
            sheets=sheet_tabs
        )
        
    except HttpError as error:
        if error.resp.status == 401:
            raise ValueError("Invalid or expired Google credentials. Please re-authenticate.")
        elif error.resp.status == 404:
            raise ValueError(f"Spreadsheet not found: {spreadsheet_id}")
        raise ValueError(f"Google Sheets API error: {error}")
