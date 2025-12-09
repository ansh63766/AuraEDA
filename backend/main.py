import os
import shutil
import tempfile
import pickle
import json
import uuid
import sqlite3
import io
import httpx
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from scipy.stats import ks_2samp, chi2_contingency, yeojohnson

# Imports from backend
from backend.orchestrator import AnalyzerOrchestrator
from backend.sql_sandbox import run_sql_query
from backend.llm import generate_so_what_commentary, chat_about_data, call_openrouter
from backend.pdf_generator import create_pdf_report
from backend.html_generator import generate_html_report
from backend.pipeline import AuraEDAPipeline, CustomFormulaParser
from backend.config import FEATURES
from backend.sample_generator import get_sample_dataset

app = FastAPI(title="AuraEDA Server v3.0", version="3.0.0")

# Enable CORS for local cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory dataset state for multi-dataset workspaces
DATASETS: Dict[str, Dict[str, Any]] = {}
ACTIVE_DATASET_ID: Optional[str] = None
CURRENT_DF: Optional[pd.DataFrame] = None

def update_dataset_views(ds_id: str):
    global DATASETS
    state = DATASETS[ds_id]
    df_full = state["df_full"]
    if state["downsample_enabled"] and len(df_full) > 50000:
        state["df"] = df_full.sample(n=50000, random_state=42).copy()
        state["is_downsampled"] = True
    else:
        state["df"] = df_full.copy()
        state["is_downsampled"] = False


class QueryRequest(BaseModel):
    query: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

class WrangleStep(BaseModel):
    action: str         
    column: str
    strategy: Optional[str] = None 

class WrangleRequest(BaseModel):
    target_column: Optional[str] = None
    steps: List[WrangleStep]

class ConfigUpdateRequest(BaseModel):
    features: Dict[str, bool]

@app.get("/api/config")
async def get_config():
    return {"features": FEATURES}

@app.post("/api/config/update")
async def update_config(request: ConfigUpdateRequest):
    global FEATURES
    for k, v in request.features.items():
        if k in FEATURES:
            FEATURES[k] = v
    return {"success": True, "features": FEATURES}

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    delimiter: str = Form(","),
    quotechar: str = Form('"'),
    encoding: str = Form("utf-8"),
    sheet_name: Optional[str] = Form(None),
    table_name: Optional[str] = Form(None)
):
    global DATASETS, ACTIVE_DATASET_ID
    
    if len(DATASETS) >= 5:
        raise HTTPException(
            status_code=400, 
            detail="Maximum limit of 5 datasets reached. Please close an existing dataset tab before uploading a new one."
        )
    
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        ext = os.path.splitext(file.filename)[1].lower()
        df = None
        
        # 1. Excel files (.xlsx, .xls)
        if ext in [".xlsx", ".xls"]:
            try:
                excel_file = pd.ExcelFile(temp_file_path)
                sheets = excel_file.sheet_names
                if not sheet_name and len(sheets) > 1:
                    return {
                        "success": True,
                        "requires_sheet_select": True,
                        "sheets": sheets,
                        "filename": file.filename
                    }
                selected_sheet = sheet_name or sheets[0]
                df = pd.read_excel(temp_file_path, sheet_name=selected_sheet)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to parse Excel file: {str(e)}")
                
        # 2. Parquet files (.parquet)
        elif ext == ".parquet":
            try:
                df = pd.read_parquet(temp_file_path)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to parse Parquet file: {str(e)}")
                
        # 3. JSON files (.json)
        elif ext == ".json":
            try:
                # Try parsing as standard JSON, if it fails, parse as JSON lines
                try:
                    df = pd.read_json(temp_file_path)
                except Exception:
                    df = pd.read_json(temp_file_path, lines=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to parse JSON file: {str(e)}")
                
        # 4. SQLite databases (.db, .sqlite, .sqlite3)
        elif ext in [".db", ".sqlite", ".sqlite3"]:
            try:
                conn = sqlite3.connect(temp_file_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                conn.close()
                
                if not tables:
                    raise HTTPException(status_code=400, detail="The SQLite database contains no tables.")
                
                if not table_name and len(tables) > 1:
                    return {
                        "success": True,
                        "requires_table_select": True,
                        "tables": tables,
                        "filename": file.filename
                    }
                
                selected_table = table_name or tables[0]
                conn = sqlite3.connect(temp_file_path)
                df = pd.read_sql_query(f"SELECT * FROM `{selected_table}`", conn)
                conn.close()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to parse SQLite file: {str(e)}")
                
        # 5. Default: CSV/TSV/text files
        else:
            try:
                df = pd.read_csv(
                    temp_file_path,
                    sep=delimiter,
                    quotechar=quotechar,
                    encoding=encoding
                )
            except UnicodeDecodeError:
                df = pd.read_csv(
                    temp_file_path,
                    sep=delimiter,
                    quotechar=quotechar,
                    encoding="ISO-8859-1"
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

        if df is None or len(df) == 0:
            raise HTTPException(status_code=400, detail="The uploaded dataset is empty or invalid.")

        # Generate isolated state for the dataset
        dataset_id = str(uuid.uuid4())[:8]
        DATASETS[dataset_id] = {
            "df_full": df.copy(),
            "df_original": df.copy(),
            "filename": file.filename,
            "analysis": None,
            "chat_history": [],
            "wrangle_steps": [],
            "undo_stack": [],
            "redo_stack": [],
            "snapshots": {},
            "pipeline_object_path": None,
            "target_column": None,
            "downsample_enabled": True,
            "is_downsampled": False
        }
        
        update_dataset_views(dataset_id)
        ACTIVE_DATASET_ID = dataset_id

        state = DATASETS[dataset_id]
        preview_rows = state["df"].head(10).fillna("").to_dict(orient="records")

        return {
            "success": True,
            "dataset_id": dataset_id,
            "filename": file.filename,
            "n_rows": len(state["df_full"]),
            "n_columns": len(state["df_full"].columns),
            "columns": state["df_full"].columns.tolist(),
            "dtypes": {col: str(state["df_full"][col].dtype) for col in state["df_full"].columns},
            "preview": preview_rows,
            "is_downsampled": state["is_downsampled"],
            "downsample_enabled": state["downsample_enabled"]
        }
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        shutil.rmtree(temp_dir)

@app.post("/api/analyze")
async def analyze_dataset(target_column: Optional[str] = Form(None), x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset has been uploaded yet.")
    state = DATASETS[ds_id]
    
    if target_column and target_column not in state["df"].columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_column}' not found in dataset.")

    state["target_column"] = target_column
    orchestrator = AnalyzerOrchestrator()
    analysis = orchestrator.run_all(state["df"], target_column)
    
    results = analysis.get("results", {})
    for module_name, module_data in results.items():
        if "status" in module_data and module_data["status"] == "waiting":
            continue
        try:
            commentary = generate_so_what_commentary(module_name, module_data, target_column)
            module_data["so_what"] = commentary
        except Exception as e:
            module_data["so_what"] = f"[Failed to generate commentary: {str(e)}]"

    state["analysis"] = analysis
    return analysis

@app.get("/api/datasets")
async def list_datasets():
    global DATASETS, ACTIVE_DATASET_ID
    return {
        "active_id": ACTIVE_DATASET_ID,
        "datasets": [
            {
                "id": ds_id,
                "filename": ds["filename"],
                "n_rows": len(ds["df_full"]),
                "n_columns": len(ds["df_full"].columns),
                "is_downsampled": ds["is_downsampled"],
                "downsample_enabled": ds["downsample_enabled"]
            }
            for ds_id, ds in DATASETS.items()
        ]
    }

@app.post("/api/datasets/active")
async def set_active_dataset(dataset_id: str = Form(...)):
    global ACTIVE_DATASET_ID, DATASETS
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    ACTIVE_DATASET_ID = dataset_id
    return {"success": True, "active_id": ACTIVE_DATASET_ID}

@app.delete("/api/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    global ACTIVE_DATASET_ID, DATASETS
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    del DATASETS[dataset_id]
    if ACTIVE_DATASET_ID == dataset_id:
        if DATASETS:
            ACTIVE_DATASET_ID = list(DATASETS.keys())[0]
        else:
            ACTIVE_DATASET_ID = None
    return {"success": True, "active_id": ACTIVE_DATASET_ID}

@app.post("/api/datasets/toggle-downsample")
async def toggle_downsample(dataset_id: str = Form(...), enabled: bool = Form(...)):
    global DATASETS
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    state = DATASETS[dataset_id]
    state["downsample_enabled"] = enabled
    update_dataset_views(dataset_id)
    
    # Re-run analysis automatically if analysis already exists
    if state["analysis"]:
        orchestrator = AnalyzerOrchestrator()
        target_col = state.get("target_column")
        analysis = orchestrator.run_all(state["df"], target_col)
        
        results = analysis.get("results", {})
        for module_name, module_data in results.items():
            if "status" in module_data and module_data["status"] == "waiting":
                continue
            try:
                commentary = generate_so_what_commentary(module_name, module_data, target_col)
                module_data["so_what"] = commentary
            except Exception:
                pass
        state["analysis"] = analysis
    else:
        state["analysis"] = None
    
    return {
        "success": True, 
        "is_downsampled": state["is_downsampled"], 
        "analysis": state["analysis"],
        "n_rows": len(state["df"]),
        "n_columns": len(state["df"].columns)
    }

@app.post("/api/datasets/undo")
async def undo_dataset_step(x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No active dataset.")
    state = DATASETS[ds_id]
    if not state["undo_stack"]:
        raise HTTPException(status_code=400, detail="No steps to undo.")
    
    # Save current state to redo stack
    state["redo_stack"].append({
        "df_full": state["df_full"].copy(),
        "wrangle_steps": list(state["wrangle_steps"])
    })
    if len(state["redo_stack"]) > 10:
        state["redo_stack"].pop(0)
        
    # Restore from undo stack
    prev_state = state["undo_stack"].pop()
    state["df_full"] = prev_state["df_full"]
    state["wrangle_steps"] = prev_state["wrangle_steps"]
    
    # Update df view
    update_dataset_views(ds_id)
    
    # Re-run analysis
    orchestrator = AnalyzerOrchestrator()
    target_col = state.get("target_column")
    analysis = orchestrator.run_all(state["df"], target_col)
    results = analysis.get("results", {})
    for module_name, module_data in results.items():
        if "status" in module_data and module_data["status"] == "waiting":
            continue
        try:
            commentary = generate_so_what_commentary(module_name, module_data, target_col)
            module_data["so_what"] = commentary
        except Exception:
            pass
    state["analysis"] = analysis
    
    return {
        "success": True,
        "wrangle_steps": state["wrangle_steps"],
        "analysis": analysis,
        "n_rows": len(state["df"]),
        "n_columns": len(state["df"].columns)
    }

@app.post("/api/datasets/redo")
async def redo_dataset_step(x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No active dataset.")
    state = DATASETS[ds_id]
    if not state["redo_stack"]:
        raise HTTPException(status_code=400, detail="No steps to redo.")
        
    # Save current state to undo stack
    state["undo_stack"].append({
        "df_full": state["df_full"].copy(),
        "wrangle_steps": list(state["wrangle_steps"])
    })
    if len(state["undo_stack"]) > 10:
        state["undo_stack"].pop(0)
        
    # Restore from redo stack
    next_state = state["redo_stack"].pop()
    state["df_full"] = next_state["df_full"]
    state["wrangle_steps"] = next_state["wrangle_steps"]
    
    # Update df view
    update_dataset_views(ds_id)
    
    # Re-run analysis
    orchestrator = AnalyzerOrchestrator()
    target_col = state.get("target_column")
    analysis = orchestrator.run_all(state["df"], target_col)
    results = analysis.get("results", {})
    for module_name, module_data in results.items():
        if "status" in module_data and module_data["status"] == "waiting":
            continue
        try:
            commentary = generate_so_what_commentary(module_name, module_data, target_col)
            module_data["so_what"] = commentary
        except Exception:
            pass
    state["analysis"] = analysis
    
    return {
        "success": True,
        "wrangle_steps": state["wrangle_steps"],
        "analysis": analysis,
        "n_rows": len(state["df"]),
        "n_columns": len(state["df"].columns)
    }

@app.post("/api/datasets/snapshot")
async def create_snapshot(
    name: str = Form(...),
    x_dataset_id: Optional[str] = Header(None)
):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No active dataset.")
    state = DATASETS[ds_id]
    
    evicted_warning = None
    if len(state["snapshots"]) >= 10:
        oldest_key = list(state["snapshots"].keys())[0]
        del state["snapshots"][oldest_key]
        evicted_warning = f"Evicted oldest snapshot '{oldest_key}' to fit limit of 10."
        
    state["snapshots"][name] = {
        "df": state["df_full"].copy(),
        "wrangle_steps": list(state["wrangle_steps"]),
        "timestamp": pd.Timestamp.now().isoformat()
    }
    
    return {
        "success": True,
        "message": f"Snapshot '{name}' saved successfully.",
        "warning": evicted_warning
    }

@app.get("/api/datasets/snapshots")
async def list_snapshots(x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No active dataset.")
    state = DATASETS[ds_id]
    return {
        "snapshots": [
            {
                "name": name,
                "timestamp": snap["timestamp"],
                "n_rows": len(snap["df"]),
                "n_columns": len(snap["df"].columns)
            }
            for name, snap in state["snapshots"].items()
        ]
    }

@app.post("/api/datasets/snapshots/restore")
async def restore_snapshot(
    name: str = Form(...),
    x_dataset_id: Optional[str] = Header(None)
):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No active dataset.")
    state = DATASETS[ds_id]
    if name not in state["snapshots"]:
        raise HTTPException(status_code=404, detail=f"Snapshot '{name}' not found.")
        
    # Push current state to undo stack
    state["undo_stack"].append({
        "df_full": state["df_full"].copy(),
        "wrangle_steps": list(state["wrangle_steps"])
    })
    if len(state["undo_stack"]) > 10:
        state["undo_stack"].pop(0)
        
    snap = state["snapshots"][name]
    state["df_full"] = snap["df"].copy()
    state["wrangle_steps"] = list(snap["wrangle_steps"])
    
    # Update df view
    update_dataset_views(ds_id)
    
    # Re-run analysis
    orchestrator = AnalyzerOrchestrator()
    target_col = state.get("target_column")
    analysis = orchestrator.run_all(state["df"], target_col)
    results = analysis.get("results", {})
    for module_name, module_data in results.items():
        if "status" in module_data and module_data["status"] == "waiting":
            continue
        try:
            commentary = generate_so_what_commentary(module_name, module_data, target_col)
            module_data["so_what"] = commentary
        except Exception:
            pass
    state["analysis"] = analysis
    
    return {
        "success": True,
        "wrangle_steps": state["wrangle_steps"],
        "analysis": analysis,
        "n_rows": len(state["df"]),
        "n_columns": len(state["df"].columns)
    }

@app.get("/api/datasets/snapshots/compare")
async def compare_snapshots(
    snapshot_a: str,
    snapshot_b: Optional[str] = None,
    x_dataset_id: Optional[str] = Header(None)
):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No active dataset.")
    state = DATASETS[ds_id]
    
    if snapshot_a not in state["snapshots"]:
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_a}' not found.")
    
    df_a = state["snapshots"][snapshot_a]["df"]
    
    if snapshot_b:
        if snapshot_b not in state["snapshots"]:
            raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_b}' not found.")
        df_b = state["snapshots"][snapshot_b]["df"]
        name_b = snapshot_b
    else:
        df_b = state["df_full"]
        name_b = "Current Data"
        
    cols_a = set(df_a.columns)
    cols_b = set(df_b.columns)
    
    added_cols = list(cols_b - cols_a)
    removed_cols = list(cols_a - cols_b)
    
    dtype_changes = {}
    null_changes = {}
    
    shared_cols = cols_a.intersection(cols_b)
    for col in shared_cols:
        type_a = str(df_a[col].dtype)
        type_b = str(df_b[col].dtype)
        if type_a != type_b:
            dtype_changes[col] = {"from": type_a, "to": type_b}
            
        null_a = int(df_a[col].isnull().sum())
        null_b = int(df_b[col].isnull().sum())
        if null_a != null_b:
            null_changes[col] = {"from": null_a, "to": null_b}
            
    return {
        "snapshot_a": snapshot_a,
        "snapshot_b": name_b,
        "rows_a": len(df_a),
        "rows_b": len(df_b),
        "added_columns": added_cols,
        "removed_columns": removed_cols,
        "dtype_changes": dtype_changes,
        "null_changes": null_changes
    }

@app.get("/api/datasets/samples")
async def list_sample_gallery():
    return {
        "samples": [
            {"name": "Titanic Survival", "description": "Classic classification dataset with demographic metadata.", "badge": "Classification", "cols": 8},
            {"name": "Iris Flower", "description": "Three species of flowers with sepal and petal measures.", "badge": "Classification", "cols": 5},
            {"name": "World Population", "description": "Global country population growth indicators (2010-2025).", "badge": "Time Series", "cols": 4},
            {"name": "Text Reviews", "description": "NLP text dataset containing customer reviews and scores.", "badge": "NLP Text", "cols": 4},
            {"name": "Climate Change", "description": "Historical temperature anomalies and carbon metrics.", "badge": "Time Series", "cols": 4},
            {"name": "California Housing", "description": "Median values, household parameters, and coordinates.", "badge": "Geospatial", "cols": 5},
            {"name": "Customer Churn", "description": "Telecom customer metrics with status labels.", "badge": "Classification", "cols": 6},
            {"name": "Penguins Size", "description": "Adult foraging penguins physical dimensions.", "badge": "Classification", "cols": 7},
            {"name": "Diamonds Pricing", "description": "Physical cuts, color grades, and price points.", "badge": "Regression", "cols": 4},
            {"name": "Air Quality Index", "description": "Chemical composition readings and AQI categories.", "badge": "Regression", "cols": 5},
            {"name": "Weather Forecast", "description": "Daily meteorological readings and rainfall outcomes.", "badge": "Classification", "cols": 5},
            {"name": "Retail Sales", "description": "E-commerce transaction categories and transaction yields.", "badge": "Regression", "cols": 5}
        ]
    }

@app.post("/api/datasets/samples/load")
async def load_sample_gallery_dataset(name: str = Form(...)):
    global DATASETS, ACTIVE_DATASET_ID
    if len(DATASETS) >= 5:
        raise HTTPException(
            status_code=400, 
            detail="Maximum limit of 5 datasets reached. Close an active tab before loading a sample."
        )
    try:
        df = get_sample_dataset(name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    dataset_id = str(uuid.uuid4())[:8]
    DATASETS[dataset_id] = {
        "df_full": df.copy(),
        "df_original": df.copy(),
        "filename": f"sample_{name.lower().replace(' ', '_')}.csv",
        "analysis": None,
        "chat_history": [],
        "wrangle_steps": [],
        "undo_stack": [],
        "redo_stack": [],
        "snapshots": {},
        "pipeline_object_path": None,
        "target_column": None,
        "downsample_enabled": True,
        "is_downsampled": False
    }
    
    update_dataset_views(dataset_id)
    ACTIVE_DATASET_ID = dataset_id

    state = DATASETS[dataset_id]
    preview_rows = state["df"].head(10).fillna("").to_dict(orient="records")

    return {
        "success": True,
        "dataset_id": dataset_id,
        "filename": state["filename"],
        "n_rows": len(state["df_full"]),
        "n_columns": len(state["df_full"].columns),
        "columns": state["df_full"].columns.tolist(),
        "dtypes": {col: str(state["df_full"][col].dtype) for col in state["df_full"].columns},
        "preview": preview_rows,
        "is_downsampled": state["is_downsampled"],
        "downsample_enabled": state["downsample_enabled"]
    }

class DbConnectRequest(BaseModel):
    db_type: str
    host: str
    port: int
    username: str
    password: str
    database: str
    query: str

@app.post("/api/datasets/db-connect")
async def load_db_connection(req: DbConnectRequest):
    global DATASETS, ACTIVE_DATASET_ID
    if len(DATASETS) >= 5:
        raise HTTPException(status_code=400, detail="Maximum limit of 5 datasets reached.")
        
    try:
        from sqlalchemy import create_engine
        if req.db_type == "postgresql":
            url = f"postgresql://{req.username}:{req.password}@{req.host}:{req.port}/{req.database}"
        elif req.db_type == "mysql":
            url = f"mysql+pymysql://{req.username}:{req.password}@{req.host}:{req.port}/{req.database}"
        else:
            raise HTTPException(status_code=400, detail="Unsupported database engine type.")
            
        engine = create_engine(url)
        df = pd.read_sql_query(req.query, engine)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Database query failed: {str(e)}")
        
    if len(df) == 0:
        raise HTTPException(status_code=400, detail="Query returned zero records.")
        
    dataset_id = str(uuid.uuid4())[:8]
    DATASETS[dataset_id] = {
        "df_full": df.copy(),
        "df_original": df.copy(),
        "filename": f"db_query_{dataset_id}.csv",
        "analysis": None,
        "chat_history": [],
        "wrangle_steps": [],
        "undo_stack": [],
        "redo_stack": [],
        "snapshots": {},
        "pipeline_object_path": None,
        "target_column": None,
        "downsample_enabled": True,
        "is_downsampled": False
    }
    
    update_dataset_views(dataset_id)
    ACTIVE_DATASET_ID = dataset_id

    state = DATASETS[dataset_id]
    preview_rows = state["df"].head(10).fillna("").to_dict(orient="records")

    return {
        "success": True,
        "dataset_id": dataset_id,
        "filename": state["filename"],
        "n_rows": len(state["df_full"]),
        "n_columns": len(state["df_full"].columns),
        "columns": state["df_full"].columns.tolist(),
        "dtypes": {col: str(state["df_full"][col].dtype) for col in state["df_full"].columns},
        "preview": preview_rows,
        "is_downsampled": state["is_downsampled"],
        "downsample_enabled": state["downsample_enabled"]
    }

class UrlLoadRequest(BaseModel):
    url: str
    jsonpath: Optional[str] = None

@app.post("/api/datasets/url-load")
async def load_rest_url(req: UrlLoadRequest):
    global DATASETS, ACTIVE_DATASET_ID
    if len(DATASETS) >= 5:
        raise HTTPException(status_code=400, detail="Maximum limit of 5 datasets reached.")
        
    try:
        response = httpx.get(req.url, follow_redirects=True, timeout=15.0)
        response.raise_for_status()
        
        # Try checking content type or extensions
        data = response.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch REST URL: {str(e)}")
        
    try:
        # Simple parser to traverse JSONpath-like dot-notation structures (e.g. data.records)
        if req.jsonpath:
            clean_path = req.jsonpath.replace("$.", "").strip()
            if clean_path:
                parts = clean_path.split(".")
                for part in parts:
                    if isinstance(data, dict) and part in data:
                        data = data[part]
                    else:
                        break
        
        # Re-verify and load into DataFrame
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            # Check if dict of lists
            if any(isinstance(v, list) for v in data.values()):
                df = pd.DataFrame(data)
            else:
                df = pd.DataFrame([data])
        else:
            raise ValueError("Parsed REST JSON payload is not represented as a tabular list or dictionary.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse JSON path structure into tabular schema: {str(e)}")

    if len(df) == 0:
        raise HTTPException(status_code=400, detail="URL API returned zero records.")

    dataset_id = str(uuid.uuid4())[:8]
    DATASETS[dataset_id] = {
        "df_full": df.copy(),
        "df_original": df.copy(),
        "filename": "api_stream_data.csv",
        "analysis": None,
        "chat_history": [],
        "wrangle_steps": [],
        "undo_stack": [],
        "redo_stack": [],
        "snapshots": {},
        "pipeline_object_path": None,
        "target_column": None,
        "downsample_enabled": True,
        "is_downsampled": False
    }
    
    update_dataset_views(dataset_id)
    ACTIVE_DATASET_ID = dataset_id

    state = DATASETS[dataset_id]
    preview_rows = state["df"].head(10).fillna("").to_dict(orient="records")

    return {
        "success": True,
        "dataset_id": dataset_id,
        "filename": state["filename"],
        "n_rows": len(state["df_full"]),
        "n_columns": len(state["df_full"].columns),
        "columns": state["df_full"].columns.tolist(),
        "dtypes": {col: str(state["df_full"][col].dtype) for col in state["df_full"].columns},
        "preview": preview_rows,
        "is_downsampled": state["is_downsampled"],
        "downsample_enabled": state["downsample_enabled"]
    }

@app.post("/api/datasets/clipboard-load")
async def load_clipboard_text(
    text: str = Form(...),
    delimiter: Optional[str] = Form(None)
):
    global DATASETS, ACTIVE_DATASET_ID
    if len(DATASETS) >= 5:
        raise HTTPException(status_code=400, detail="Maximum limit of 5 datasets reached.")
        
    try:
        # Auto-detect separator
        sep = delimiter
        if not sep:
            if "\t" in text:
                sep = "\t"
            elif ";" in text:
                sep = ";"
            else:
                sep = ","
                
        df = pd.read_csv(io.StringIO(text), sep=sep)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse pasted text: {str(e)}")

    if len(df) == 0:
        raise HTTPException(status_code=400, detail="Tabular text contained no rows.")

    dataset_id = str(uuid.uuid4())[:8]
    DATASETS[dataset_id] = {
        "df_full": df.copy(),
        "df_original": df.copy(),
        "filename": "clipboard_pasted_data.csv",
        "analysis": None,
        "chat_history": [],
        "wrangle_steps": [],
        "undo_stack": [],
        "redo_stack": [],
        "snapshots": {},
        "pipeline_object_path": None,
        "target_column": None,
        "downsample_enabled": True,
        "is_downsampled": False
    }
    
    update_dataset_views(dataset_id)
    ACTIVE_DATASET_ID = dataset_id

    state = DATASETS[dataset_id]
    preview_rows = state["df"].head(10).fillna("").to_dict(orient="records")

    return {
        "success": True,
        "dataset_id": dataset_id,
        "filename": state["filename"],
        "n_rows": len(state["df_full"]),
        "n_columns": len(state["df_full"].columns),
        "columns": state["df_full"].columns.tolist(),
        "dtypes": {col: str(state["df_full"][col].dtype) for col in state["df_full"].columns},
        "preview": preview_rows,
        "is_downsampled": state["is_downsampled"],
        "downsample_enabled": state["downsample_enabled"]
    }

class MergeWizardRequest(BaseModel):
    dataset_a_id: str
    dataset_b_id: str
    merge_type: str # "join" or "stack"
    join_how: Optional[str] = "inner" # "inner", "left", "right", "outer"
    left_on: Optional[str] = None
    right_on: Optional[str] = None

@app.post("/api/datasets/merge")
async def merge_datasets(req: MergeWizardRequest):
    global DATASETS, ACTIVE_DATASET_ID
    if len(DATASETS) >= 5:
        raise HTTPException(status_code=400, detail="Maximum limit of 5 datasets reached.")
        
    if req.dataset_a_id not in DATASETS or req.dataset_b_id not in DATASETS:
        raise HTTPException(status_code=404, detail="One of the selected datasets is not loaded.")
        
    state_a = DATASETS[req.dataset_a_id]
    state_b = DATASETS[req.dataset_b_id]
    
    df_a = state_a["df_full"]
    df_b = state_b["df_full"]
    
    try:
        if req.merge_type == "stack":
            # Align columns and stack vertically
            df = pd.concat([df_a, df_b], ignore_index=True)
            filename = f"stacked_{state_a['filename']}_{state_b['filename']}"
        else:
            # Column-wise joins
            if not req.left_on or not req.right_on:
                raise HTTPException(status_code=400, detail="Joining datasets requires matching key variables.")
            df = pd.merge(
                df_a, df_b,
                how=req.join_how,
                left_on=req.left_on,
                right_on=req.right_on,
                suffixes=("_a", "_b")
            )
            filename = f"joined_{state_a['filename']}_{state_b['filename']}"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Merge operations failed: {str(e)}")

    dataset_id = str(uuid.uuid4())[:8]
    DATASETS[dataset_id] = {
        "df_full": df.copy(),
        "df_original": df.copy(),
        "filename": filename,
        "analysis": None,
        "chat_history": [],
        "wrangle_steps": [],
        "undo_stack": [],
        "redo_stack": [],
        "snapshots": {},
        "pipeline_object_path": None,
        "target_column": None,
        "downsample_enabled": True,
        "is_downsampled": False
    }
    
    update_dataset_views(dataset_id)
    ACTIVE_DATASET_ID = dataset_id

    state = DATASETS[dataset_id]
    preview_rows = state["df"].head(10).fillna("").to_dict(orient="records")

    return {
        "success": True,
        "dataset_id": dataset_id,
        "filename": state["filename"],
        "n_rows": len(state["df_full"]),
        "n_columns": len(state["df_full"].columns),
        "columns": state["df_full"].columns.tolist(),
        "dtypes": {col: str(state["df_full"][col].dtype) for col in state["df_full"].columns},
        "preview": preview_rows,
        "is_downsampled": state["is_downsampled"],
        "downsample_enabled": state["downsample_enabled"]
    }

@app.post("/api/wrangle")
async def wrangle_dataset(request: WrangleRequest, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]

    # Save current state to undo stack
    state["undo_stack"].append({
        "df_full": state["df_full"].copy(),
        "wrangle_steps": list(state["wrangle_steps"])
    })
    if len(state["undo_stack"]) > 10:
        state["undo_stack"].pop(0)
    # Clear redo stack
    state["redo_stack"].clear()

    df = state["df_original"].copy()
    code_lines = [
        "import pandas as pd",
        "import numpy as np",
        "from scipy.stats import yeojohnson",
        "from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler",
        "from sklearn.preprocessing import TargetEncoder",
        "",
        "# Load original dataset",
        f"df = pd.read_csv('{state['filename']}')",
        ""
    ]

    for step in request.steps:
        col = step.column
        action = step.action
        strat = step.strategy

        if col not in df.columns and action not in ["drop", "custom_formula", "feature_cross"]:
            continue

        if action == "drop":
            if col in df.columns:
                df = df.drop(columns=[col])
                code_lines.append(f"df = df.drop(columns=['{col}'])")
        
        elif action == "impute":
            if strat == "mean":
                mean_val = df[col].mean()
                df[col] = df[col].fillna(mean_val)
                code_lines.append(f"df['{col}'] = df['{col}'].fillna(df['{col}'].mean())")
            elif strat == "median":
                med_val = df[col].median()
                df[col] = df[col].fillna(med_val)
                code_lines.append(f"df['{col}'] = df['{col}'].fillna(df['{col}'].median())")
            elif strat == "mode":
                mode_val = df[col].mode()[0]
                df[col] = df[col].fillna(mode_val)
                code_lines.append(f"df['{col}'] = df['{col}'].fillna(df['{col}'].mode()[0])")
            elif strat == "constant":
                fill_val = -999 if pd.api.types.is_numeric_dtype(df[col]) else "Missing"
                df[col] = df[col].fillna(fill_val)
                code_lines.append(f"df['{col}'] = df['{col}'].fillna({repr(fill_val)})")
                
        elif action == "scale":
            if strat == "standard" and df[col].std() > 0:
                mean_val, std_val = df[col].mean(), df[col].std()
                df[col] = (df[col] - mean_val) / std_val
                code_lines.append(f"df['{col}'] = (df['{col}'] - df['{col}'].mean()) / df['{col}'].std()")
            elif strat == "minmax" and (df[col].max() - df[col].min()) > 0:
                min_val, max_val = df[col].min(), df[col].max()
                df[col] = (df[col] - min_val) / (max_val - min_val)
                code_lines.append(f"df['{col}'] = (df['{col}'] - df['{col}'].min()) / (df['{col}'].max() - df['{col}'].min())")
            elif strat == "robust":
                med = df[col].median()
                q25 = df[col].quantile(0.25)
                q75 = df[col].quantile(0.75)
                iqr = q75 - q25
                iqr_val = iqr if iqr > 0 else 1.0
                df[col] = (df[col] - med) / iqr_val
                code_lines.append(f"q25, q75 = df['{col}'].quantile(0.25), df['{col}'].quantile(0.75)\niqr = q75 - q25 if q75 - q25 > 0 else 1.0\ndf['{col}'] = (df['{col}'] - df['{col}'].median()) / iqr")
            elif strat == "maxabs":
                maxabs_val = df[col].abs().max()
                maxabs_val = maxabs_val if maxabs_val > 0 else 1.0
                df[col] = df[col] / maxabs_val
                code_lines.append(f"df['{col}'] = df['{col}'] / df['{col}'].abs().max()")
                
        elif action == "clip":
            q_low = df[col].quantile(0.01)
            q_high = df[col].quantile(0.99)
            df[col] = df[col].clip(q_low, q_high)
            code_lines.append(f"df['{col}'] = df['{col}'].clip(df['{col}'].quantile(0.01), df['{col}'].quantile(0.99))")
            
        elif action == "transform":
            if strat == "log":
                shift = max(0, -df[col].min()) + 1 if len(df[col]) > 0 else 1
                df[col] = np.log1p(df[col] + (shift - 1))
                code_lines.append(f"df['{col}'] = np.log1p(df['{col}'] + {shift - 1})")
            elif strat == "yeojohnson":
                df_filled = df[col].fillna(df[col].median())
                df[col], _ = yeojohnson(df_filled)
                code_lines.append(f"df['{col}'] = df['{col}'].fillna(df['{col}'].median())\ndf['{col}'], _ = yeojohnson(df['{col}'])")

        elif action == "onehot":
            if col in df.columns:
                cats = list(df[col].dropna().unique())
                for cat in cats:
                    df[f"{col}_{cat}"] = (df[col] == cat).astype(float)
                df = df.drop(columns=[col])
                code_lines.append(f"# One-hot encode '{col}'\nfor cat in {repr(cats)}:\n    df[f'{col}_{{cat}}'] = (df['{col}'] == cat).astype(float)\ndf = df.drop(columns=['{col}'])")

        elif action == "bin":
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                _, bins = pd.cut(df[col].dropna(), bins=5, retbins=True, labels=False)
                df[col] = pd.cut(df[col], bins=bins, labels=False, include_lowest=True).astype(float).fillna(-1)
                code_lines.append(f"_, bins = pd.cut(df['{col}'].dropna(), bins=5, retbins=True, labels=False)\ndf['{col}'] = pd.cut(df['{col}'], bins=bins, labels=False, include_lowest=True).astype(float).fillna(-1)")

        # --- Target Encoding ---
        elif action == "target_encode" and request.target_column:
            from sklearn.preprocessing import TargetEncoder
            te = TargetEncoder(cv=3, random_state=42)
            y_col = df[request.target_column].dropna()
            valid_idx = y_col.index
            X_encoded = te.fit_transform(df.loc[valid_idx, [col]], y_col)
            # Reindex fill
            encoded_series = pd.Series(X_encoded.flatten(), index=valid_idx)
            df[col] = encoded_series.reindex(df.index).fillna(encoded_series.mean())
            code_lines.append(f"# Target encode '{col}'\nfrom sklearn.preprocessing import TargetEncoder\nte = TargetEncoder(cv=3, random_state=42)\ndf['{col}'] = te.fit_transform(df[[col]], df['{request.target_column}'])")

        # --- Frequency Encoding ---
        elif action == "frequency_encode":
            freqs = df[col].value_counts(normalize=True).to_dict()
            df[col] = df[col].map(freqs).fillna(0.0)
            code_lines.append(f"# Frequency encode '{col}'\nfreqs = df['{col}'].value_counts(normalize=True).to_dict()\ndf['{col}'] = df['{col}'].map(freqs).fillna(0.0)")

        # --- Binary Encoding ---
        elif action == "binary_encode":
            cats = sorted(list(df[col].dropna().unique()))
            max_bits = len(bin(len(cats))) - 2
            cat_indices = {cat: idx for idx, cat in enumerate(cats)}
            for bit in range(max_bits):
                bit_col = f"{col}_bit_{bit}"
                df[bit_col] = df[col].apply(lambda val: float((cat_indices.get(val, 0) >> bit) & 1) if val in cat_indices else 0.0)
            df = df.drop(columns=[col])
            code_lines.append(f"# Binary encode '{col}'\ncats = sorted(list(df['{col}'].dropna().unique()))\nmax_bits = len(bin(len(cats))) - 2\ncat_indices = {{cat: idx for idx, cat in enumerate(cats)}}\nfor bit in range(max_bits):\n    df[f'{col}_bit_{{bit}}'] = df['{col}'].apply(lambda val: float((cat_indices.get(val, 0) >> bit) & 1) if val in cat_indices else 0.0)\ndf = df.drop(columns=['{col}'])")

        # --- Rare Label Grouping ---
        elif action == "rare_label":
            threshold = float(strat) if strat else 0.05
            freqs = df[col].value_counts(normalize=True)
            frequent = list(freqs[freqs >= threshold].index)
            df[col] = df[col].apply(lambda x: x if x in frequent else "Other")
            code_lines.append(f"# Rare label grouping for '{col}' (threshold={threshold})\nfreqs = df['{col}'].value_counts(normalize=True)\nfrequent = list(freqs[freqs >= {threshold}].index)\ndf['{col}'] = df['{col}'].apply(lambda x: x if x in frequent else 'Other')")

        # --- Ordinal Encoding ---
        elif action == "ordinal_encode":
            ordered_list = [k.strip() for k in strat.split(",") if k.strip()]
            order_map = {val: idx for idx, val in enumerate(ordered_list)}
            df[col] = df[col].map(order_map).fillna(-1.0)
            code_lines.append(f"# Ordinal encode '{col}'\norder_map = {repr(order_map)}\ndf['{col}'] = df['{col}'].map(order_map).fillna(-1.0)")

        # --- Polynomial Features ---
        elif action == "polynomial":
            deg = int(strat) if strat in ["2", "3"] else 2
            if pd.api.types.is_numeric_dtype(df[col]):
                for d in range(2, deg + 1):
                    df[f"{col}_power_{d}"] = df[col] ** d
                    code_lines.append(f"df['{col}_power_{d}'] = df['{col}'] ** {d}")

        # --- Group Level Aggregation ---
        elif action == "group_aggregate":
            group_col = col
            target_agg_col, func = strat.split(",")
            col_name = f"{target_agg_col}_{func}_by_{group_col}"
            if col_name in df.columns:
                col_name = f"{col_name}_2"
            grouped = df.groupby(group_col)[target_agg_col].agg(func).to_dict()
            df[col_name] = df[group_col].map(grouped).fillna(0.0)
            code_lines.append(f"# Group aggregate '{target_agg_col}' by '{group_col}' using '{func}'\ngrouped = df.groupby('{group_col}')['{target_agg_col}'].agg('{func}').to_dict()\ndf['{col_name}'] = df['{group_col}'].map(grouped).fillna(0.0)")

        # --- Custom Formula ---
        elif action == "custom_formula":
            parser = CustomFormulaParser(allowed_columns=df.columns)
            df[col] = parser.evaluate(df, strat)
            code_lines.append(f"# Custom AST formula evaluated: '{strat}'\ndf['{col}'] = {strat} # secure sandbox checked")

        # --- Feature Cross ---
        elif action == "feature_cross":
            c1, c2 = strat.split(",")
            df[col] = df[c1].astype(str) + "_" + df[c2].astype(str)
            code_lines.append(f"df['{col}'] = df['{c1}'].astype(str) + '_' + df['{c2}'].astype(str)")

        # --- Time Ordering Imputation Fill ---
        elif action == "time_impute":
            date_col, method = strat.split(",")
            df = df.sort_values(by=date_col)
            if method == "ffill":
                df[col] = df[col].ffill()
            else:
                df[col] = df[col].bfill()
            code_lines.append(f"# Time impute '{col}' sorted by '{date_col}' using '{method}'\ndf = df.sort_values(by='{date_col}')\ndf['{col}'] = df['{col}'].{method}()")

        elif action == "cyclical_time":
            parsed = pd.to_datetime(df[col], errors="coerce")
            h = parsed.dt.hour.fillna(0)
            d = parsed.dt.dayofweek.fillna(0)
            m = parsed.dt.month.fillna(1)
            df[f"{col}_hour_sin"] = np.sin(2 * np.pi * h / 24.0)
            df[f"{col}_hour_cos"] = np.cos(2 * np.pi * h / 24.0)
            df[f"{col}_dow_sin"] = np.sin(2 * np.pi * d / 7.0)
            df[f"{col}_dow_cos"] = np.cos(2 * np.pi * d / 7.0)
            df[f"{col}_month_sin"] = np.sin(2 * np.pi * (m - 1) / 12.0)
            df[f"{col}_month_cos"] = np.cos(2 * np.pi * (m - 1) / 12.0)
            code_lines.append(f"# Cyclical temporal features for '{col}'\nparsed = pd.to_datetime(df['{col}'], errors='coerce')\ndf['{col}_hour_sin'] = np.sin(2 * np.pi * parsed.dt.hour.fillna(0) / 24.0)\ndf['{col}_hour_cos'] = np.cos(2 * np.pi * parsed.dt.hour.fillna(0) / 24.0)\ndf['{col}_dow_sin'] = np.sin(2 * np.pi * parsed.dt.dayofweek.fillna(0) / 7.0)\ndf['{col}_dow_cos'] = np.cos(2 * np.pi * parsed.dt.dayofweek.fillna(0) / 7.0)\ndf['{col}_month_sin'] = np.sin(2 * np.pi * (parsed.dt.month.fillna(1) - 1) / 12.0)\ndf['{col}_month_cos'] = np.cos(2 * np.pi * (parsed.dt.month.fillna(1) - 1) / 12.0)")

        elif action == "extract_datetime":
            parsed = pd.to_datetime(df[col], errors="coerce")
            df[f"{col}_year"] = parsed.dt.year.fillna(0).astype(float)
            df[f"{col}_month"] = parsed.dt.month.fillna(0).astype(float)
            df[f"{col}_day"] = parsed.dt.day.fillna(0).astype(float)
            df[f"{col}_hour"] = parsed.dt.hour.fillna(0).astype(float)
            df[f"{col}_weekday"] = parsed.dt.dayofweek.fillna(0).astype(float)
            df[f"{col}_is_weekend"] = (parsed.dt.dayofweek >= 5).astype(float)
            df = df.drop(columns=[col])
            code_lines.append(f"# Extract components from datetime '{col}'\nparsed = pd.to_datetime(df['{col}'], errors='coerce')\ndf['{col}_year'] = parsed.dt.year.fillna(0).astype(float)\ndf['{col}_month'] = parsed.dt.month.fillna(0).astype(float)\ndf['{col}_day'] = parsed.dt.day.fillna(0).astype(float)\ndf['{col}_hour'] = parsed.dt.hour.fillna(0).astype(float)\ndf['{col}_weekday'] = parsed.dt.dayofweek.fillna(0).astype(float)\ndf['{col}_is_weekend'] = (parsed.dt.dayofweek >= 5).astype(float)\ndf = df.drop(columns=['{col}'])")

        elif action == "text_length":
            strs = df[col].astype(str).fillna("")
            df[f"{col}_char_count"] = strs.str.len().astype(float)
            df[f"{col}_word_count"] = strs.str.split().str.len().astype(float)
            df = df.drop(columns=[col])
            code_lines.append(f"# Extract text length features from '{col}'\ndf['{col}_char_count'] = df['{col}'].astype(str).fillna('').str.len().astype(float)\ndf['{col}_word_count'] = df['{col}'].astype(str).fillna('').str.split().str.len().astype(float)\ndf = df.drop(columns=['{col}'])")

        elif action == "add_missing_indicator":
            df[f"{col}_is_null"] = df[col].isnull().astype(float)
            code_lines.append(f"df['{col}_is_null'] = df['{col}'].isnull().astype(float)")

        elif action == "cast":
            df[col] = df[col].astype(strat)
            code_lines.append(f"df['{col}'] = df['{col}'].astype('{strat}')")

        elif action == "mask_pii":
            df[col] = df[col].astype(str).apply(lambda val: "****" if val not in ["nan", "None", ""] else val)
            code_lines.append(f"df['{col}'] = df['{col}'].astype(str).apply(lambda val: '****' if val not in ['nan', 'None', ''] else val)")

        elif action == "hash_pii":
            import hashlib
            df[col] = df[col].astype(str).apply(lambda val: hashlib.sha256(val.encode('utf-8')).hexdigest() if val not in ["nan", "None", ""] else val)
            code_lines.append(f"import hashlib\ndf['{col}'] = df['{col}'].astype(str).apply(lambda val: hashlib.sha256(val.encode('utf-8')).hexdigest() if val not in ['nan', 'None', ''] else val)")

    state["df_full"] = df
    state["wrangle_steps"] = [{"column": s.column, "action": s.action, "strategy": s.strategy} for s in request.steps]
    
    try:
        pipe = AuraEDAPipeline(steps=state["wrangle_steps"])
        pipe.fit(state["df_original"])
        
        temp_dir = tempfile.mkdtemp()
        state["pipeline_object_path"] = os.path.join(temp_dir, "pipeline.pkl")
        with open(state["pipeline_object_path"], "wb") as f:
            pickle.dump(pipe, f)
    except Exception as e:
        print(f"Failed to compile SKLearn Pipeline: {str(e)}")

    # Update df view (applies downsampling if enabled)
    update_dataset_views(ds_id)

    # Re-run full audit on updated dataset
    orchestrator = AnalyzerOrchestrator()
    analysis = orchestrator.run_all(state["df"], request.target_column)
    
    results = analysis.get("results", {})
    for module_name, module_data in results.items():
        if "status" in module_data and module_data["status"] == "waiting":
            continue
        try:
            commentary = generate_so_what_commentary(module_name, module_data, request.target_column)
            module_data["so_what"] = commentary
        except Exception:
            pass

    state["analysis"] = analysis
    state["target_column"] = request.target_column
    pipeline_code = "\n".join(code_lines)

    return {
        "analysis": analysis,
        "pipeline_code": pipeline_code,
        "n_rows": len(state["df"]),
        "n_columns": len(state["df"].columns)
    }

@app.post("/api/split-data")
async def split_data(
    ratio: float = Form(0.7),
    target_column: Optional[str] = Form(None),
    x_dataset_id: Optional[str] = Header(None)
):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df_active = state["df"]

    is_classification = False
    if target_column and target_column in df_active.columns:
        y_nonnull = df_active[target_column].dropna()
        if y_nonnull.nunique() > 1 and y_nonnull.nunique() < 20:
            is_classification = True

    if is_classification:
        df_clean = df_active.dropna(subset=[target_column])
        try:
            from sklearn.model_selection import train_test_split
            train_df, test_df = train_test_split(df_clean, test_size=(1 - ratio), stratify=df_clean[target_column], random_state=42)
        except Exception:
            from sklearn.model_selection import train_test_split
            train_df, test_df = train_test_split(df_clean, test_size=(1 - ratio), random_state=42)
    else:
        np.random.seed(42)
        mask = np.random.rand(len(df_active)) < ratio
        train_df = df_active[mask].copy()
        test_df = df_active[~mask].copy()

    drift_report = []
    for col in df_active.columns:
        if col == target_column:
            continue
            
        p_val = 1.0
        test_name = "N/A"
        drifted = False
        
        if pd.api.types.is_numeric_dtype(df_active[col]) and df_active[col].nunique() > 1:
            test_name = "Kolmogorov-Smirnov"
            train_vals = train_df[col].dropna()
            test_vals = test_df[col].dropna()
            if len(train_vals) > 5 and len(test_vals) > 5:
                stat, p_val = ks_2samp(train_vals, test_vals)
                drifted = p_val < 0.05
                
        elif not pd.api.types.is_numeric_dtype(df_active[col]) and df_active[col].nunique() > 1:
            test_name = "Chi-Square"
            all_cats = list(df_active[col].dropna().unique())
            train_counts = train_df[col].value_counts().reindex(all_cats, fill_value=0)
            test_counts = test_df[col].value_counts().reindex(all_cats, fill_value=0)
            
            contingency = np.array([train_counts.values, test_counts.values])
            if contingency.shape[0] >= 2 and contingency.shape[1] >= 2:
                try:
                    res = chi2_contingency(contingency)
                    p_val = res.pvalue
                    drifted = p_val < 0.05
                except Exception:
                    pass

        drift_report.append({
            "column": col,
            "test_name": test_name,
            "p_value": float(p_val) if not np.isnan(p_val) else 1.0,
            "drift_detected": bool(drifted)
        })

    train_nulls = int(train_df.isnull().sum().sum())
    test_nulls = int(test_df.isnull().sum().sum())

    baseline_dummy_score = 0.0
    baseline_model_score = 0.0
    baseline_metric_name = "Accuracy" if is_classification else "R² Score"
    has_benchmark = False

    if target_column and target_column in df_active.columns:
        train_clean = train_df.dropna(subset=[target_column])
        test_clean = test_df.dropna(subset=[target_column])
        
        if len(train_clean) > 10 and len(test_clean) > 5:
            X_train_raw = train_clean.drop(columns=[target_column])
            y_train = train_clean[target_column]
            X_test_raw = test_clean.drop(columns=[target_column])
            y_test = test_clean[target_column]
            
            from sklearn.preprocessing import LabelEncoder
            from sklearn.dummy import DummyClassifier, DummyRegressor
            from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
            
            X_train = pd.DataFrame()
            X_test = pd.DataFrame()
            categorical_mask = []
            
            for col in X_train_raw.columns:
                if X_train_raw[col].nunique() <= 1:
                    continue
                if pd.api.types.is_numeric_dtype(X_train_raw[col]):
                    med_v = X_train_raw[col].median()
                    med_v = med_v if pd.notnull(med_v) else 0.0
                    X_train[col] = X_train_raw[col].fillna(med_v).astype(float)
                    X_test[col] = X_test_raw[col].fillna(med_v).astype(float)
                    categorical_mask.append(False)
                else:
                    le = LabelEncoder()
                    filled_train = X_train_raw[col].astype(str).fillna("Missing")
                    filled_test = X_test_raw[col].astype(str).fillna("Missing")
                    all_cats = list(set(filled_train).union(set(filled_test)))
                    le.fit(all_cats)
                    X_train[col] = le.transform(filled_train)
                    X_test[col] = le.transform(filled_test)
                    categorical_mask.append(True)
            
            if len(X_train.columns) > 0:
                try:
                    if is_classification:
                        le_y = LabelEncoder()
                        y_tr = le_y.fit_transform(y_train.astype(str))
                        y_te = le_y.transform(y_test.astype(str))
                        
                        dummy = DummyClassifier(strategy="most_frequent")
                        dummy.fit(X_train, y_tr)
                        baseline_dummy_score = float(dummy.score(X_test, y_te))
                        
                        model = HistGradientBoostingClassifier(max_depth=3, max_iter=20, random_state=42, categorical_features=categorical_mask)
                        model.fit(X_train, y_tr)
                        baseline_model_score = float(model.score(X_test, y_te))
                        has_benchmark = True
                    else:
                        y_tr = y_train.values.astype(float)
                        y_te = y_test.values.astype(float)
                        
                        dummy = DummyRegressor(strategy="mean")
                        dummy.fit(X_train, y_tr)
                        baseline_dummy_score = float(dummy.score(X_test, y_te))
                        
                        model = HistGradientBoostingRegressor(max_depth=3, max_iter=20, random_state=42, categorical_features=categorical_mask)
                        model.fit(X_train, y_tr)
                        baseline_model_score = float(model.score(X_test, y_te))
                        has_benchmark = True
                    
                    # Apply SMOTE oversampling on Train split if active classification target
                    if FEATURES["smote"] and is_classification:
                        # Fallback pure python oversampler if imblearn is not found
                        try:
                            from imblearn.over_sampling import SMOTE
                            smote = SMOTE(random_state=42)
                            X_train_res, y_train_res = smote.fit_resample(X_train, y_tr)
                            print("SMOTE oversampling applied on train split!")
                        except Exception:
                            # Python fallback random oversampler
                            print("imbalanced-learn missing. Applying random oversampling fallback on train split.")
                            from collections import Counter
                            counter = Counter(y_tr)
                            max_class_count = max(counter.values())
                            X_res_list, y_res_list = [], []
                            for cls in counter.keys():
                                cls_indices = np.where(y_tr == cls)[0]
                                choices = np.random.choice(cls_indices, max_class_count, replace=True)
                                X_res_list.append(X_train.iloc[choices])
                                y_res_list.append(y_tr[choices])
                            X_train_res = pd.concat(X_res_list, axis=0)
                            y_train_res = np.concatenate(y_res_list)
                except Exception as ex:
                    print(f"Benchmark model failed: {str(ex)}")

    return {
        "train_size": len(train_df),
        "test_size": len(test_df),
        "train_nulls": train_nulls,
        "test_nulls": test_nulls,
        "drift_report": drift_report,
        "benchmark": {
            "has_benchmark": has_benchmark,
            "metric_name": baseline_metric_name,
            "dummy_score": baseline_dummy_score,
            "model_score": baseline_model_score
        }
    }

@app.post("/api/feature-selection")
async def feature_selection(target_column: str = Form(...), x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df_active = state["df"]
    
    if target_column not in df_active.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_column}' not found.")

    # Drop null rows in target
    df_clean = df_active.dropna(subset=[target_column])
    X_raw = df_clean.drop(columns=[target_column])
    y_raw = df_clean[target_column]

    is_classification = False
    if not pd.api.types.is_numeric_dtype(y_raw) or y_raw.nunique() < 15:
        is_classification = True

    # Preprocess
    from sklearn.preprocessing import LabelEncoder
    X = pd.DataFrame()
    for col in X_raw.columns:
        if X_raw[col].nunique() <= 1:
            continue
        if pd.api.types.is_numeric_dtype(X_raw[col]):
            X[col] = X_raw[col].fillna(X_raw[col].median()).astype(float)
        else:
            le = LabelEncoder()
            X[col] = le.fit_transform(X_raw[col].astype(str).fillna("Missing"))

    if len(X.columns) == 0:
        return {"scores": {}, "optimal_k": 0, "selected_features": []}

    # Target Label Encoding
    if is_classification:
        le_y = LabelEncoder()
        y = le_y.fit_transform(y_raw.astype(str))
    else:
        y = y_raw.values.astype(float)

    # 1. SelectKBest scores
    from sklearn.feature_selection import SelectKBest, f_classif, f_regression
    score_func = f_classif if is_classification else f_regression
    selector = SelectKBest(score_func=score_func, k="all")
    selector.fit(X, y)
    scores = {col: float(score) for col, score in zip(X.columns, selector.scores_) if not np.isnan(score)}

    # 2. RFECV automated feature selection
    from sklearn.feature_selection import RFECV
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    estimator = RandomForestClassifier(max_depth=3, n_estimators=10, random_state=42) if is_classification else RandomForestRegressor(max_depth=3, n_estimators=10, random_state=42)
    rfecv = RFECV(estimator=estimator, step=1, cv=3, min_features_to_select=1)
    rfecv.fit(X, y)
    
    selected_features = [col for col, supported in zip(X.columns, rfecv.support_) if supported]
    
    # Sanitize scores to ensure JSON compliance (replace NaN/Inf with 0.0)
    scores_sanitized = {}
    for col, val in scores.items():
        if np.isnan(val) or np.isinf(val):
            scores_sanitized[col] = 0.0
        else:
            scores_sanitized[col] = float(val)

    # Sanitize grid scores
    grid_scores_sanitized = []
    for s in rfecv.cv_results_["mean_test_score"]:
        if np.isnan(s) or np.isinf(s):
            grid_scores_sanitized.append(0.0)
        else:
            grid_scores_sanitized.append(float(s))

    return {
        "scores": scores_sanitized,
        "optimal_k": int(rfecv.n_features_),
        "selected_features": selected_features,
        "grid_scores": grid_scores_sanitized
    }

@app.get("/api/export/dictionary")
async def export_dictionary(x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df_active = state["df"]

    # Call LLM to Batch generate descriptions in one single API request
    col_metadata = []
    for col in df_active.columns:
        col_metadata.append({
            "name": col,
            "dtype": str(df_active[col].dtype),
            "null_pct": float(df_active[col].isnull().sum() / len(df_active)) * 100 if len(df_active) > 0 else 0.0,
            "unique_count": int(df_active[col].nunique())
        })

    prompt_msg = (
        "You are an expert data cataloger. Here is a list of dataset column metadata represented as JSON:\n"
        f"{json.dumps(col_metadata)}\n\n"
        "Generate a JSON object where each key is a column name and the value is a one-sentence descriptive "
        "summary of what that column likely represents in this dataset. Do not include formatting outside of raw JSON output."
    )

    descriptions = {}
    try:
        response = call_openrouter([{"role": "user", "content": prompt_msg}], max_tokens=1000)
        # Parse JSON
        start_idx = response.find("{")
        end_idx = response.rfind("}") + 1
        if start_idx != -1 and end_idx != -1:
            descriptions = json.loads(response[start_idx:end_idx])
    except Exception:
        # Fallback empty descriptions
        descriptions = {c["name"]: "Tabular dataset feature column." for c in col_metadata}

    # Build CSV contents
    csv_rows = ["Feature Name,Physical Dtype,Null Percentage,Unique Value Count,Automatic LLM Description"]
    for c in col_metadata:
        desc = descriptions.get(c["name"], "Tabular dataset feature column.").replace('"', '""')
        csv_rows.append(f"\"{c['name']}\",{c['dtype']},{c['null_pct']:.2f}%,{c['unique_count']},{desc}")

    csv_data = "\n".join(csv_rows)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=cleaned_{os.path.splitext(state['filename'])[0]}_dictionary.csv"}
    )

@app.get("/api/export/schema")
async def export_schema(x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df_active = state["df"]

    schema = {
        "n_rows": len(df_active),
        "n_columns": len(df_active.columns),
        "columns": []
    }

    for col in df_active.columns:
        schema["columns"].append({
            "name": col,
            "dtype": str(df_active[col].dtype),
            "null_count": int(df_active[col].isnull().sum()),
            "unique_values_count": int(df_active[col].nunique()),
            "variance": float(df_active[col].var()) if pd.api.types.is_numeric_dtype(df_active[col]) else None
        })

    return Response(
        content=json.dumps(schema, indent=4),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={os.path.splitext(state['filename'])[0]}_schema.json"}
    )

@app.get("/api/export/csv")
async def export_csv(x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df_full = state["df_full"]

    temp_dir = tempfile.mkdtemp()
    filename = f"cleaned_{state['filename']}"
    csv_path = os.path.join(temp_dir, filename)

    try:
        df_full.to_csv(csv_path, index=False)
        return FileResponse(
            csv_path,
            filename=filename,
            media_type="text/csv"
        )
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"CSV download failed: {str(e)}")

@app.get("/api/export/pipeline")
async def export_pipeline(x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    pipe_path = state["pipeline_object_path"]
    if pipe_path is None or not os.path.exists(pipe_path):
        raise HTTPException(status_code=400, detail="No pipeline fitted yet. Apply wrangler transformations first.")
    return FileResponse(
        pipe_path,
        filename=f"{os.path.splitext(state['filename'])[0]}_pipeline.pkl",
        media_type="application/octet-stream"
    )

@app.post("/api/query")
async def run_query(request: QueryRequest, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df_active = state["df"]
    
    result = run_sql_query(df_active, request.query)
    return result

@app.post("/api/chat", response_model=None)
async def run_chat(request: ChatRequest, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df_active = state["df"]

    alerts = []
    dtypes = {}
    if state["analysis"]:
        alerts = state["analysis"].get("results", {}).get("alerts", {}).get("alerts", [])
        dtypes = state["analysis"].get("dataset_summary", {}).get("dtypes", {})
    else:
        dtypes = {col: str(df_active[col].dtype) for col in df_active.columns}

    context_summary = {
        "n_rows": len(df_active),
        "n_columns": len(df_active.columns),
        "dtypes": dtypes,
        "alerts": alerts
    }

    history = []
    for msg in request.messages:
        history.append({"role": msg.role, "content": msg.content})

    # Omit max_tokens parameter to use model's actual maximum capacity
    response_text = chat_about_data(history, context_summary)
    
    # Save chat history to state
    state["chat_history"] = history + [{"role": "assistant", "content": response_text}]
    return {"response": response_text}

@app.get("/api/export/pdf")
async def export_pdf(target_column: Optional[str] = None, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    if state["analysis"] is None:
        raise HTTPException(status_code=400, detail="Please execute dataset analysis before exporting.")

    temp_dir = tempfile.mkdtemp()
    pdf_filename = f"{os.path.splitext(state['filename'])[0]}_quality_report.pdf"
    pdf_path = os.path.join(temp_dir, pdf_filename)

    try:
        create_pdf_report(state["analysis"], pdf_path, target_column)
        return FileResponse(
            pdf_path,
            filename=pdf_filename,
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

@app.get("/api/export/html")
async def export_html(target_column: Optional[str] = None, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    if state["analysis"] is None:
        raise HTTPException(status_code=400, detail="Please execute dataset analysis before exporting.")

    try:
        html_content = generate_html_report(state["analysis"], target_column)
        html_filename = f"{os.path.splitext(state['filename'])[0]}_quality_report.html"
        
        headers = {
            "Content-Disposition": f"attachment; filename={html_filename}"
        }
        return Response(content=html_content, media_type="text/html", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HTML report generation failed: {str(e)}")

class HypothesisRequest(BaseModel):
    test_type: str
    col1: str
    col2: Optional[str] = None
    pop_mean: float = 0.0
    alpha: float = 0.05

@app.get("/api/features/distribution-details")
async def get_distribution_details(column_name: str, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df = state["df"]
    
    if column_name not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column '{column_name}' not found.")
        
    series = df[column_name]
    non_null_series = series.dropna()
    
    if len(non_null_series) == 0:
        return {"type": "empty", "message": "Column has no non-null values."}
        
    is_numeric = pd.api.types.is_numeric_dtype(series)
    
    if is_numeric:
        # Sample and sort for ECDF & Q-Q plots
        sampled = non_null_series.sample(min(2000, len(non_null_series)), random_state=42).sort_values()
        n_samples = len(sampled)
        
        import scipy.stats as stats
        q_vals = (np.arange(1, n_samples + 1) - 0.5) / n_samples
        theoretical_quantiles = stats.norm.ppf(q_vals).tolist()
        actual_values = sampled.tolist()
        
        # Calculate percentiles
        quantiles = {
            "q25": float(np.percentile(non_null_series, 25)),
            "q50": float(np.percentile(non_null_series, 50)),
            "q75": float(np.percentile(non_null_series, 75)),
            "q95": float(np.percentile(non_null_series, 95))
        }
        
        # Calculate histogram and KDE
        counts, bin_edges = np.histogram(non_null_series, bins=20)
        bin_labels = []
        for i in range(len(bin_edges) - 1):
            bin_labels.append(float((bin_edges[i] + bin_edges[i+1]) / 2))
            
        # KDE estimate
        try:
            kde_func = stats.gaussian_kde(non_null_series)
            kde_x = np.linspace(float(non_null_series.min()), float(non_null_series.max()), 100)
            kde_y = [float(val) for val in kde_func(kde_x)]
            kde_data = {"x": kde_x.tolist(), "y": kde_y}
        except Exception:
            kde_data = {"x": [], "y": []}
            
        return {
            "type": "numerical",
            "values": actual_values,
            "theoretical_quantiles": theoretical_quantiles,
            "quantiles": quantiles,
            "histogram": {
                "bin_centers": bin_labels,
                "counts": counts.tolist(),
                "bin_edges": bin_edges.tolist()
            },
            "kde": kde_data
        }
    else:
        # Categorical
        val_counts = non_null_series.value_counts()
        max_cats = 15
        if len(val_counts) > max_cats:
            top_cats = val_counts.iloc[:max_cats]
            other_sum = val_counts.iloc[max_cats:].sum()
            labels = [str(x) for x in top_cats.index] + ["Other"]
            counts = [int(x) for x in top_cats.values] + [int(other_sum)]
        else:
            labels = [str(x) for x in val_counts.index]
            counts = [int(x) for x in val_counts.values]
            
        return {
            "type": "categorical",
            "labels": labels,
            "counts": counts
        }

@app.get("/api/bivariate")
async def get_bivariate(x_col: str, y_col: str, z_col: Optional[str] = None, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df = state["df"]
    
    if x_col not in df.columns or y_col not in df.columns:
        raise HTTPException(status_code=400, detail="Columns not found in dataset.")
        
    cols = [x_col, y_col]
    if z_col:
        cols.append(z_col)
        
    clean_df = df[cols].dropna()
    if len(clean_df) == 0:
        return {"type": "empty", "message": "No overlapping non-null rows."}
        
    is_num_x = pd.api.types.is_numeric_dtype(df[x_col])
    is_num_y = pd.api.types.is_numeric_dtype(df[y_col])
    
    if is_num_x and is_num_y:
        x_vals = clean_df[x_col].values
        y_vals = clean_df[y_col].values
        
        import scipy.stats as stats
        try:
            r_val, p_val = stats.pearsonr(x_vals, y_vals)
            r_val = float(r_val) if not np.isnan(r_val) else 0.0
            p_val = float(p_val) if not np.isnan(p_val) else 1.0
        except Exception:
            r_val, p_val = 0.0, 1.0
            
        # Fit regression
        try:
            lr = LinearRegression()
            lr.fit(x_vals.reshape(-1, 1), y_vals)
            slope = float(lr.coef_[0])
            intercept = float(lr.intercept_)
            r2 = float(lr.score(x_vals.reshape(-1, 1), y_vals))
        except Exception:
            slope, intercept, r2 = 0.0, 0.0, 0.0
            
        # Sample for plotting
        sample_size = min(2000, len(clean_df))
        sample_df = clean_df.sample(n=sample_size, random_state=42)
        x_sample = sample_df[x_col].values.tolist()
        y_sample = sample_df[y_col].values.tolist()
        
        if z_col and pd.api.types.is_numeric_dtype(df[z_col]):
            z_sample = sample_df[z_col].values.tolist()
            return {
                "type": "num-num-num",
                "x": x_sample,
                "y": y_sample,
                "z": z_sample,
                "r": r_val,
                "p_value": p_val
            }
            
        return {
            "type": "num-num",
            "x": x_sample,
            "y": y_sample,
            "r": r_val,
            "p_value": p_val,
            "r2": r2,
            "slope": slope,
            "intercept": intercept
        }
        
    elif is_num_x and not is_num_y:
        # Num-Cat
        grouped = {}
        for cat in clean_df[y_col].unique():
            vals = clean_df[clean_df[y_col] == cat][x_col].values
            grouped[str(cat)] = vals[:1000].tolist()
        return {
            "type": "num-cat",
            "x_name": x_col,
            "y_name": y_col,
            "groups": grouped
        }
        
    elif not is_num_x and is_num_y:
        # Cat-Num
        grouped = {}
        for cat in clean_df[x_col].unique():
            vals = clean_df[clean_df[x_col] == cat][y_col].values
            grouped[str(cat)] = vals[:1000].tolist()
        return {
            "type": "cat-num",
            "x_name": x_col,
            "y_name": y_col,
            "groups": grouped
        }
        
    else:
        # Cat-Cat
        contingency_tab = pd.crosstab(clean_df[x_col], clean_df[y_col])
        import scipy.stats as stats
        try:
            chi2, p_val, dof, expected = stats.chi2_contingency(contingency_tab)
            chi2, p_val, dof = float(chi2), float(p_val), int(dof)
        except Exception:
            chi2, p_val, dof = 0.0, 1.0, 0
            
        return {
            "type": "cat-cat",
            "x_name": x_col,
            "y_name": y_col,
            "x_labels": contingency_tab.index.tolist(),
            "y_labels": contingency_tab.columns.tolist(),
            "z_values": contingency_tab.values.tolist(),
            "chi2": chi2,
            "p_value": p_val,
            "dof": dof
        }

@app.post("/api/hypothesis/run")
async def run_hypothesis_test(request: HypothesisRequest, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df = state["df"]
    
    from backend.modules.hypothesis import HypothesisModule
    module = HypothesisModule()
    res = module.run_test(
        df=df,
        test_type=request.test_type,
        col1=request.col1,
        col2=request.col2,
        pop_mean=request.pop_mean,
        alpha=request.alpha
    )
    return res

@app.get("/api/timeseries/analyze")
async def timeseries_analyze(date_col: str, num_col: str, lag: int = 1, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df = state["df"]
    
    from backend.modules.datetime_eda import DatetimeEdaModule
    module = DatetimeEdaModule()
    res = module.analyze_time_series(df, date_col, num_col, lag)
    return res

@app.get("/api/geospatial/analyze")
async def geospatial_analyze(lat_col: str, lon_col: str, color_col: Optional[str] = None, eps: float = 0.5, min_samples: int = 5, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df = state["df"]
    
    from backend.modules.geospatial import GeospatialModule
    module = GeospatialModule()
    res = module.analyze_spatial(df, lat_col, lon_col, color_col, eps, min_samples)
    return res

@app.get("/api/geospatial/choropleth")
async def geospatial_choropleth(state_col: str, value_col: str, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df = state["df"]
    
    from backend.modules.geospatial import GeospatialModule
    module = GeospatialModule()
    res = module.analyze_choropleth(df, state_col, value_col)
    return res

@app.get("/api/nlp/analyze")
async def nlp_analyze(column_name: str, x_dataset_id: Optional[str] = Header(None)):
    global DATASETS, ACTIVE_DATASET_ID
    ds_id = x_dataset_id or ACTIVE_DATASET_ID
    if not ds_id or ds_id not in DATASETS:
        raise HTTPException(status_code=400, detail="No dataset loaded.")
    state = DATASETS[ds_id]
    df = state["df"]
    
    from backend.modules.text_eda import TextEdaModule
    module = TextEdaModule()
    res = module.analyze_text_nlp(df, column_name)
    return res

os.makedirs("frontend", exist_ok=True)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def read_index():
    index_path = "frontend/index.html"
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse(
        content="<h3>AuraEDA Frontend mounting... Please refresh in a moment.</h3>",
        status_code=200
    )
