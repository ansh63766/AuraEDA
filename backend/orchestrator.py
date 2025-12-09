import pandas as pd
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule
from backend.modules.alerts import AlertsModule
from backend.modules.missingness import MissingnessModule
from backend.modules.distributions import DistributionModule
from backend.modules.correlations import CorrelationModule
from backend.modules.leakage import LeakageModule
from backend.modules.drift import DriftSensitivityModule
from backend.modules.pca import PcaModule
from backend.modules.importance import ImportanceModule
from backend.modules.datetime_eda import DatetimeEdaModule
from backend.modules.text_eda import TextEdaModule
from backend.modules.outliers import OutlierModule
from backend.modules.geospatial import GeospatialModule

class AnalyzerOrchestrator:
    def __init__(self):
        # Register modules in a structured list
        self.modules: List[BaseAnalyzerModule] = [
            AlertsModule(),
            MissingnessModule(),
            DistributionModule(),
            CorrelationModule(),
            LeakageModule(),
            DriftSensitivityModule(),
            PcaModule(),
            ImportanceModule(),
            DatetimeEdaModule(),
            TextEdaModule(),
            OutlierModule(),
            GeospatialModule()
        ]

    def run_all(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        """
        Executes all registered analysis modules on the dataset.
        
        Args:
            df (pd.DataFrame): The dataset loaded in memory.
            target_column (str, optional): User-selected target variable.

        Returns:
            Dict[str, Any]: Unified analysis payload.
        """
        n_rows = len(df)
        n_columns = len(df.columns)
        
        # Calculate dataset memory usage
        try:
            mem_bytes = int(df.memory_usage(deep=True).sum())
        except Exception:
            mem_bytes = 0

        # General metadata
        summary = {
            "n_rows": n_rows,
            "n_columns": n_columns,
            "size_bytes": mem_bytes,
            "columns": df.columns.tolist(),
            "dtypes": {col: str(df[col].dtype) for col in df.columns}
        }

        # Run registered modules
        results = {}
        for module in self.modules:
            try:
                results[module.name] = module.run(df, target_column)
            except Exception as e:
                # Ensure one module crash doesn't fail the whole analysis
                results[module.name] = {
                    "status": "error",
                    "message": f"Module '{module.name}' execution failed: {str(e)}"
                }

        return {
            "dataset_summary": summary,
            "results": results
        }
