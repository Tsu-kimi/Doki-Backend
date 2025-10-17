from typing import List, Dict


def list_sheets() -> List[Dict[str, object]]:
    # Dummy schema for confirmation/testing purposes
    return [
        {
            "spreadsheet_id": "dummy-spreadsheet",
            "title": "Demo Sheet",
            "sheets": [
                {"name": "Users", "columns": [{"name": "id", "type": "STRING"}, {"name": "email", "type": "STRING"}]},
                {"name": "Orders", "columns": [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "NUMBER"}]},
            ],
        }
    ]
