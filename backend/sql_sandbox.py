import sqlite3
import pandas as pd
import time
from typing import Dict, Any, List

def run_sql_query(df: pd.DataFrame, query: str) -> Dict[str, Any]:
    """
    Loads a Pandas DataFrame into an in-memory SQLite database and executes a SQL query.
    The table is named 'data'.
    
    Args:
        df (pd.DataFrame): The dataset dataframe.
        query (str): The SQL query string.

    Returns:
        Dict[str, Any]: Dict containing columns, rows, execution time, row count, and error if any.
    """
    if df is None or len(df) == 0:
        return {"error": "Dataset is empty or not loaded."}
        
    if not query.strip():
        return {"error": "Query string is empty."}

    conn = sqlite3.connect(":memory:")
    start_time = time.perf_counter()
    
    try:
        # Load df into SQLite under table name 'data'
        df.to_sql("data", conn, index=False, if_exists="replace")
        
        # Execute query
        cursor = conn.cursor()
        cursor.execute(query)
        
        # Get column names
        columns = [description[0] for description in cursor.description] if cursor.description else []
        
        # Fetch first 1000 rows (limit to prevent memory blowup)
        rows = cursor.fetchmany(1000)
        
        # Convert rows (tuples) to list of lists for easy JSON serialization
        rows_list = [list(row) for row in rows]
        
        # Check if there are more rows
        has_more = len(cursor.fetchall()) > 0
        
        execution_time = (time.perf_counter() - start_time) * 1000 # milliseconds

        return {
            "success": True,
            "columns": columns,
            "rows": rows_list,
            "row_count": len(rows_list),
            "execution_time_ms": float(f"{execution_time:.2f}"),
            "has_more": has_more
        }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"SQLite Error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Execution Error: {str(e)}"
        }
    finally:
        conn.close()
