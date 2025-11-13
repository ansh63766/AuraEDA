from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any

class BaseAnalyzerModule(ABC):
    """
    Abstract base class for all AuraEDA analysis modules.
    Any new analysis feature should subclass this and implement all methods.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique string identifier for the module.
        Used as the key in the final output JSON.
        """
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Human-readable title of the module.
        Used in UI headers and PDF section headings.
        """
        pass

    @abstractmethod
    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        """
        Run the analysis on the dataframe.
        
        Args:
            df (pd.DataFrame): The uploaded and parsed dataset.
            target_column (str, optional): The target column name, if specified by the user.

        Returns:
            Dict[str, Any]: A JSON-serializable dictionary containing computed statistics,
                           alerts, lists, or matrix data to be rendered by the UI.
        """
        pass
