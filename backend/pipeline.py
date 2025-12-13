import pandas as pd
import numpy as np
import ast
from sklearn.base import BaseEstimator, TransformerMixin
from scipy.stats import yeojohnson
from sklearn.preprocessing import TargetEncoder

class SmoothedLOOTargetEncoder(BaseEstimator, TransformerMixin):
    """
    Smoothed Leave-One-Out category target encoder.
    Prevents target leakage during training by using leave-one-out target means,
    and applies smoothed group means during inference.
    """
    def __init__(self, smoothing=10.0):
        self.smoothing = smoothing
        self.global_mean_ = 0.0
        self.category_sums_ = {}
        self.category_counts_ = {}

    def fit(self, X, y):
        y_arr = np.asarray(y)
        self.global_mean_ = float(y_arr.mean()) if len(y_arr) > 0 else 0.0
        col_vals = np.asarray(X).ravel()
        
        self.category_sums_ = {}
        self.category_counts_ = {}
        unique_cats = np.unique(col_vals)
        for cat in unique_cats:
            mask = (col_vals == cat)
            self.category_sums_[cat] = float(y_arr[mask].sum())
            self.category_counts_[cat] = int(mask.sum())
        return self

    def transform(self, X, y=None):
        col_vals = np.asarray(X).ravel()
        encoded = np.empty_like(col_vals, dtype=float)
        
        if y is not None and len(y) == len(col_vals):
            # Training time LOO
            y_arr = np.asarray(y)
            for i, val in enumerate(col_vals):
                sum_val = self.category_sums_.get(val, 0.0)
                count_val = self.category_counts_.get(val, 0)
                y_i = y_arr[i]
                if count_val > 1:
                    encoded[i] = (sum_val - y_i + self.smoothing * self.global_mean_) / (count_val - 1 + self.smoothing)
                else:
                    encoded[i] = self.global_mean_
        else:
            # Inference time smoothed mean
            for i, val in enumerate(col_vals):
                sum_val = self.category_sums_.get(val, 0.0)
                count_val = self.category_counts_.get(val, 0)
                if count_val > 0:
                    encoded[i] = (sum_val + self.smoothing * self.global_mean_) / (count_val + self.smoothing)
                else:
                    encoded[i] = self.global_mean_
        return encoded

class CustomFormulaParser:
    """
    AST-based sandboxed parser that securely compiles and evaluates custom arithmetic expressions.
    Only allows basic arithmetic operations, constants, column variables, and whitelisted math functions.
    No access to OS, builtins, loops, attribute accesses, or arbitrary statements.

    ### WHITELIST SPECIFICATION
    - **Syntax Nodes**: Constant, Num, Name, BinOp, UnaryOp, Call
    - **Operators**: Add (+), Sub (-), Mult (*), Div (/), Pow (**), Mod (%), USub (-x), UAdd (+x)
    - **Math Functions**:
      - `sin(x)`: Trigonometric sine
      - `cos(x)`: Trigonometric cosine
      - `log(x)`: Natural log (using log1p on positive clipped x)
      - `exp(x)`: Exponential (capped at e^50)
      - `sqrt(x)`: Square root (on positive clipped x)
      - `abs(x)`: Absolute value
      - `pow(x, y)`: Raise x to power y
      - `round(x, [decimals])`: Round x to specified decimals
      - `min(x, y, ...)`: Element-wise minimum
      - `max(x, y, ...)`: Element-wise maximum
      - `floor(x)`: Largest integer <= x
      - `ceil(x)`: Smallest integer >= x
    """
    def __init__(self, allowed_columns):
        self.allowed_columns = set(allowed_columns)
        self.whitelisted_functions = {
            'sin', 'cos', 'log', 'exp', 'sqrt', 'abs', 
            'pow', 'round', 'min', 'max', 'floor', 'ceil'
        }

    def validate(self, expr_str: str) -> bool:
        try:
            tree = ast.parse(expr_str, mode='eval')
            return self._check_node(tree.body)
        except Exception:
            return False

    def _check_node(self, node) -> bool:
        # Allow numbers
        if isinstance(node, (ast.Num, ast.Constant)):
            return True
        # Allow column names if they exist in the dataset columns
        elif isinstance(node, ast.Name):
            return node.id in self.allowed_columns
        # Allow basic binary operations (+, -, *, /, **, %)
        elif isinstance(node, ast.BinOp):
            return self._check_node(node.left) and self._check_node(node.right)
        # Allow basic unary operations (-x, +x)
        elif isinstance(node, ast.UnaryOp):
            return self._check_node(node.operand)
        # Allow specific whitelisted math calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in self.whitelisted_functions:
                return all(self._check_node(arg) for arg in node.args)
            return False
        return False

    def evaluate(self, df: pd.DataFrame, expr_str: str) -> pd.Series:
        if not self.validate(expr_str):
            raise ValueError(f"Formula '{expr_str}' failed AST safety checks (forbidden syntax or invalid columns).")
        
        # Parse tree
        tree = ast.parse(expr_str, mode='eval')
        return self._eval_ast_node(tree.body, df)

    def _eval_ast_node(self, node, df: pd.DataFrame) -> pd.Series:
        if isinstance(node, ast.Constant):
            return pd.Series(node.value, index=df.index)
        elif isinstance(node, ast.Num):  # compatibility for python <3.8
            return pd.Series(node.n, index=df.index)
        elif isinstance(node, ast.Name):
            return df[node.id]
        elif isinstance(node, ast.BinOp):
            left = self._eval_ast_node(node.left, df)
            right = self._eval_ast_node(node.right, df)
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                # Avoid divide by zero
                return left / right.replace({0: np.nan})
            elif isinstance(node.op, ast.Pow):
                return left ** right
            elif isinstance(node.op, ast.Mod):
                return left % right
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_ast_node(node.operand, df)
            if isinstance(node.op, ast.USub):
                return -operand
            elif isinstance(node.op, ast.UAdd):
                return +operand
        elif isinstance(node, ast.Call):
            func_name = node.func.id
            if func_name == 'sin':
                return np.sin(self._eval_ast_node(node.args[0], df))
            elif func_name == 'cos':
                return np.cos(self._eval_ast_node(node.args[0], df))
            elif func_name == 'log':
                return np.log1p(self._eval_ast_node(node.args[0], df).clip(lower=0))
            elif func_name == 'exp':
                return np.exp(self._eval_ast_node(node.args[0], df).clip(upper=50))
            elif func_name == 'sqrt':
                return np.sqrt(self._eval_ast_node(node.args[0], df).clip(lower=0))
            elif func_name == 'abs':
                return np.abs(self._eval_ast_node(node.args[0], df))
            elif func_name == 'pow':
                x = self._eval_ast_node(node.args[0], df)
                y = self._eval_ast_node(node.args[1], df)
                return x ** y
            elif func_name == 'round':
                val = self._eval_ast_node(node.args[0], df)
                decimals = int(node.args[1].value) if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else (int(node.args[1].n) if len(node.args) > 1 and isinstance(node.args[1], ast.Num) else 0)
                return np.round(val, decimals)
            elif func_name == 'min':
                vals = [self._eval_ast_node(arg, df) for arg in node.args]
                res = vals[0]
                for v in vals[1:]:
                    res = np.minimum(res, v)
                return res
            elif func_name == 'max':
                vals = [self._eval_ast_node(arg, df) for arg in node.args]
                res = vals[0]
                for v in vals[1:]:
                    res = np.maximum(res, v)
                return res
            elif func_name == 'floor':
                return np.floor(self._eval_ast_node(node.args[0], df))
            elif func_name == 'ceil':
                return np.ceil(self._eval_ast_node(node.args[0], df))
                
        raise ValueError("Unsupported mathematical node in formula.")


class AuraEDAPipeline(BaseEstimator, TransformerMixin):
    """
    A custom Scikit-Learn compatible transformer that executes
    sequential data wrangling and feature engineering operations.
    Fits parameters on training data and applies them consistently.
    """
    def __init__(self, steps=None):
        self.steps = steps if steps is not None else []
        self.fitted_params_ = {}

    def fit(self, X, y=None):
        X_temp = X.copy()
        self.fitted_params_ = {}

        for i, step in enumerate(self.steps):
            col = step.get("column")
            action = step.get("action")
            strat = step.get("strategy")
            step_key = f"step_{i}_{col}_{action}"
            params = {}

            if col not in X_temp.columns and action not in ["drop", "custom_formula", "feature_cross"]:
                continue

            if action == "drop":
                X_temp = X_temp.drop(columns=[col], errors="ignore")
                
            elif action == "impute":
                non_null = X_temp[col].dropna()
                if len(non_null) > 0:
                    if strat == "mean":
                        params["fill_value"] = float(non_null.mean())
                    elif strat == "median":
                        params["fill_value"] = float(non_null.median())
                    elif strat == "mode":
                        params["fill_value"] = non_null.mode()[0]
                    elif strat == "constant":
                        params["fill_value"] = -999 if pd.api.types.is_numeric_dtype(X_temp[col]) else "Missing"
                else:
                    params["fill_value"] = -999 if pd.api.types.is_numeric_dtype(X_temp[col]) else "Missing"
                
                X_temp[col] = X_temp[col].fillna(params["fill_value"])
                
            elif action == "scale":
                if pd.api.types.is_numeric_dtype(X_temp[col]):
                    non_null = X_temp[col].dropna()
                    if len(non_null) > 0:
                        if strat == "standard":
                            params["mean"] = float(non_null.mean())
                            params["std"] = float(non_null.std()) if non_null.std() > 0 else 1.0
                            X_temp[col] = (X_temp[col] - params["mean"]) / params["std"]
                        elif strat == "minmax":
                            params["min"] = float(non_null.min())
                            params["max"] = float(non_null.max())
                            diff = params["max"] - params["min"]
                            params["range"] = diff if diff > 0 else 1.0
                            X_temp[col] = (X_temp[col] - params["min"]) / params["range"]
                        elif strat == "robust":
                            params["median"] = float(non_null.median())
                            q25 = float(non_null.quantile(0.25))
                            q75 = float(non_null.quantile(0.75))
                            diff = q75 - q25
                            params["iqr"] = diff if diff > 0 else 1.0
                            X_temp[col] = (X_temp[col] - params["median"]) / params["iqr"]
                        elif strat == "maxabs":
                            params["maxabs"] = float(non_null.abs().max())
                            params["maxabs"] = params["maxabs"] if params["maxabs"] > 0 else 1.0
                            X_temp[col] = X_temp[col] / params["maxabs"]

            elif action == "clip":
                if pd.api.types.is_numeric_dtype(X_temp[col]):
                    params["q_low"] = float(X_temp[col].quantile(0.01))
                    params["q_high"] = float(X_temp[col].quantile(0.99))
                    X_temp[col] = X_temp[col].clip(params["q_low"], params["q_high"])

            elif action == "replace_cell":
                parts = strat.split(",", 1)
                row_idx = int(parts[0])
                val = parts[1]
                target_dtype = X_temp[col].dtype
                try:
                    if pd.api.types.is_numeric_dtype(target_dtype):
                        val = float(val) if "." in val else int(val)
                except Exception:
                    pass
                if row_idx in X_temp.index:
                    X_temp.at[row_idx, col] = val
                else:
                    X_temp.iloc[row_idx, X_temp.columns.get_loc(col)] = val

            elif action == "drop_row":
                indices = [int(idx.strip()) for idx in strat.split(",") if idx.strip()]
                X_temp = X_temp.drop(index=indices, errors="ignore")

            elif action == "winsorize":
                if pd.api.types.is_numeric_dtype(X_temp[col]):
                    q_low_pct, q_high_pct = map(float, strat.split(","))
                    params["q_low"] = float(X_temp[col].quantile(q_low_pct))
                    params["q_high"] = float(X_temp[col].quantile(q_high_pct))
                    X_temp[col] = X_temp[col].clip(params["q_low"], params["q_high"])

            elif action == "knn_impute":
                from sklearn.impute import KNNImputer
                n_neighbors = int(strat) if strat else 5
                num_cols = [c for c in X_temp.columns if pd.api.types.is_numeric_dtype(X_temp[c])]
                if len(num_cols) > 0:
                    imputer = KNNImputer(n_neighbors=n_neighbors)
                    imputer.fit(X_temp[num_cols])
                    params["imputer"] = imputer
                    params["num_cols"] = num_cols
                    X_temp[num_cols] = imputer.transform(X_temp[num_cols])

            elif action == "mice_impute":
                from sklearn.experimental import enable_iterative_imputer
                from sklearn.impute import IterativeImputer
                from sklearn.linear_model import BayesianRidge
                num_cols = [c for c in X_temp.columns if pd.api.types.is_numeric_dtype(X_temp[c])]
                if len(num_cols) > 0:
                    imputer = IterativeImputer(estimator=BayesianRidge(), max_iter=10, random_state=42)
                    imputer.fit(X_temp[num_cols])
                    params["imputer"] = imputer
                    params["num_cols"] = num_cols
                    X_temp[num_cols] = imputer.transform(X_temp[num_cols])

            elif action == "cosine_standardize":
                import json
                try:
                    mapping = json.loads(strat)
                    X_temp[col] = X_temp[col].astype(str).map(mapping).fillna(X_temp[col])
                except Exception:
                    pass

            elif action == "transform":
                if pd.api.types.is_numeric_dtype(X_temp[col]):
                    if strat == "log":
                        params["shift"] = float(max(0, -X_temp[col].min()) + 1)
                        X_temp[col] = np.log1p(X_temp[col] + (params["shift"] - 1))
                    elif strat == "yeojohnson":
                        med = X_temp[col].median()
                        params["median_fallback"] = float(med) if pd.notnull(med) else 0.0
                        filled = X_temp[col].fillna(params["median_fallback"])
                        _, lmbda = yeojohnson(filled)
                        params["lmbda"] = float(lmbda)
                        X_temp[col], _ = yeojohnson(filled, lmbda=lmbda)

            elif action == "onehot":
                cats = list(X_temp[col].dropna().unique())
                params["categories"] = cats
                for cat in cats:
                    new_col = f"{col}_{cat}"
                    X_temp[new_col] = (X_temp[col] == cat).astype(float)
                X_temp = X_temp.drop(columns=[col], errors="ignore")

            elif action == "bin":
                if pd.api.types.is_numeric_dtype(X_temp[col]):
                    non_null = X_temp[col].dropna()
                    if len(non_null) > 0:
                        _, bins = pd.cut(non_null, bins=5, retbins=True, labels=False)
                        params["bin_edges"] = [float(b) for b in bins]
                        X_temp[col] = pd.cut(X_temp[col], bins=bins, labels=False, include_lowest=True).astype(float).fillna(-1)

            # --- Target Encoding ---
            elif action == "target_encode":
                if y is not None:
                    # Simple k-fold Target Encoder
                    from sklearn.preprocessing import TargetEncoder
                    te = TargetEncoder(cv=3, random_state=42)
                    te.fit(X_temp[[col]], y)
                    params["target_encoder"] = te
                    X_temp[col] = te.transform(X_temp[[col]])

            # --- Smoothed Leave-One-Out Target Encoding ---
            elif action == "loo_target_encode":
                if y is not None:
                    smoothing_factor = 10.0
                    try:
                        if strat:
                            smoothing_factor = float(strat)
                    except Exception:
                        smoothing_factor = 10.0
                    te = SmoothedLOOTargetEncoder(smoothing=smoothing_factor)
                    te.fit(X_temp[[col]], y)
                    params["encoder"] = te
                    X_temp[col] = te.transform(X_temp[[col]], y)

            # --- TF-IDF Word Metrics Extraction ---
            elif action == "tfidf_encode":
                from sklearn.feature_extraction.text import TfidfVectorizer
                max_feats = 5
                try:
                    if strat:
                        max_feats = int(strat)
                except Exception:
                    max_feats = 5
                vec = TfidfVectorizer(max_features=max_feats, stop_words="english")
                non_null_text = X_temp[col].astype(str).fillna("")
                vec.fit(non_null_text)
                params["vectorizer"] = vec
                params["max_features"] = max_feats
                tfidf_mat = vec.transform(non_null_text).toarray()
                words = vec.get_feature_names_out()
                params["words"] = words
                for j, word in enumerate(words):
                    new_col = f"tfidf_{col}_{word}"
                    X_temp[new_col] = tfidf_mat[:, j]
                X_temp = X_temp.drop(columns=[col], errors="ignore")

            # --- Frequency Encoding ---
            elif action == "frequency_encode":
                freqs = X_temp[col].value_counts(normalize=True).to_dict()
                params["frequencies"] = freqs
                X_temp[col] = X_temp[col].map(freqs).fillna(0.0)

            # --- Binary Encoding ---
            elif action == "binary_encode":
                cats = sorted(list(X_temp[col].dropna().unique()))
                params["categories"] = cats
                # Convert category names to binary column assignments
                max_bits = len(bin(len(cats))) - 2
                params["max_bits"] = max_bits
                for bit in range(max_bits):
                    X_temp[f"{col}_bit_{bit}"] = 0.0
                X_temp = X_temp.drop(columns=[col], errors="ignore")

            # --- Rare Label Grouping ---
            elif action == "rare_label":
                threshold = float(strat) if strat else 0.05
                freqs = X_temp[col].value_counts(normalize=True)
                frequent = list(freqs[freqs >= threshold].index)
                params["frequent_categories"] = frequent
                X_temp[col] = X_temp[col].apply(lambda x: x if x in frequent else "Other")

            # --- Ordinal Encoding ---
            elif action == "ordinal_encode":
                # strat contains ordered list comma-separated, e.g. "Low,Medium,High"
                ordered_list = [k.strip() for k in strat.split(",") if k.strip()]
                order_map = {val: idx for idx, val in enumerate(ordered_list)}
                params["order_map"] = order_map
                X_temp[col] = X_temp[col].map(order_map).fillna(-1.0)

            # --- Polynomial Features ---
            elif action == "polynomial":
                # degree is parsed from strat, e.g., "2" or "3"
                deg = int(strat) if strat in ["2", "3"] else 2
                params["degree"] = deg
                if pd.api.types.is_numeric_dtype(X_temp[col]):
                    for d in range(2, deg + 1):
                        X_temp[f"{col}_power_{d}"] = X_temp[col] ** d

            # --- Group Level Aggregation ---
            elif action == "group_aggregate":
                # strat is e.g. "target_col,agg_func"
                group_col = col
                target_agg_col, func = strat.split(",")
                params["group_col"] = group_col
                params["target_agg_col"] = target_agg_col
                params["func"] = func
                grouped = X_temp.groupby(group_col)[target_agg_col].agg(func).to_dict()
                params["grouped_values"] = grouped

            self.fitted_params_[step_key] = params

        return self

    def transform(self, X):
        X_out = X.copy()

        for i, step in enumerate(self.steps):
            col = step.get("column")
            action = step.get("action")
            strat = step.get("strategy")
            step_key = f"step_{i}_{col}_{action}"
            params = self.fitted_params_.get(step_key, {})

            if col not in X_out.columns and action not in ["drop", "custom_formula", "feature_cross"]:
                continue

            if action == "drop":
                X_out = X_out.drop(columns=[col], errors="ignore")

            elif action == "impute":
                fill_val = params.get("fill_value", -999)
                X_out[col] = X_out[col].fillna(fill_val)

            elif action == "scale":
                if pd.api.types.is_numeric_dtype(X_out[col]):
                    if strat == "standard" and "mean" in params:
                        X_out[col] = (X_out[col] - params["mean"]) / params["std"]
                    elif strat == "minmax" and "min" in params:
                        X_out[col] = (X_out[col] - params["min"]) / params["range"]
                    elif strat == "robust" and "median" in params:
                        X_out[col] = (X_out[col] - params["median"]) / params["iqr"]
                    elif strat == "maxabs" and "maxabs" in params:
                        X_out[col] = X_out[col] / params["maxabs"]

            elif action == "clip":
                if pd.api.types.is_numeric_dtype(X_out[col]) and "q_low" in params:
                    X_out[col] = X_out[col].clip(params["q_low"], params["q_high"])

            elif action == "replace_cell":
                parts = strat.split(",", 1)
                row_idx = int(parts[0])
                val = parts[1]
                target_dtype = X_out[col].dtype
                try:
                    if pd.api.types.is_numeric_dtype(target_dtype):
                        val = float(val) if "." in val else int(val)
                except Exception:
                    pass
                if row_idx in X_out.index:
                    X_out.at[row_idx, col] = val
                else:
                    X_out.iloc[row_idx, X_out.columns.get_loc(col)] = val

            elif action == "drop_row":
                indices = [int(idx.strip()) for idx in strat.split(",") if idx.strip()]
                X_out = X_out.drop(index=indices, errors="ignore")

            elif action == "winsorize" and "q_low" in params:
                X_out[col] = X_out[col].clip(params["q_low"], params["q_high"])

            elif action == "knn_impute" and "imputer" in params:
                imputer = params["imputer"]
                num_cols = params["num_cols"]
                X_out[num_cols] = imputer.transform(X_out[num_cols])

            elif action == "mice_impute" and "imputer" in params:
                imputer = params["imputer"]
                num_cols = params["num_cols"]
                X_out[num_cols] = imputer.transform(X_out[num_cols])

            elif action == "cosine_standardize":
                import json
                try:
                    mapping = json.loads(strat)
                    X_out[col] = X_out[col].astype(str).map(mapping).fillna(X_out[col])
                except Exception:
                    pass

            elif action == "transform":
                if pd.api.types.is_numeric_dtype(X_out[col]):
                    if strat == "log" and "shift" in params:
                        X_out[col] = np.log1p(X_out[col] + (params["shift"] - 1))
                    elif strat == "yeojohnson" and "lmbda" in params:
                        filled = X_out[col].fillna(params.get("median_fallback", 0.0))
                        X_out[col] = yeojohnson(filled, lmbda=params["lmbda"])

            elif action == "onehot" and "categories" in params:
                cats = params["categories"]
                for cat in cats:
                    new_col = f"{col}_{cat}"
                    X_out[new_col] = (X_out[col] == cat).astype(float)
                X_out = X_out.drop(columns=[col], errors="ignore")

            elif action == "bin" and "bin_edges" in params:
                bins = params["bin_edges"]
                X_out[col] = pd.cut(X_out[col], bins=bins, labels=False, include_lowest=True).astype(float).fillna(-1)

            # --- Target Encoding ---
            elif action == "target_encode" and "target_encoder" in params:
                te = params["target_encoder"]
                X_out[col] = te.transform(X_out[[col]])

            # --- Smoothed Leave-One-Out Target Encoding ---
            elif action == "loo_target_encode" and "encoder" in params:
                te = params["encoder"]
                X_out[col] = te.transform(X_out[[col]])

            # --- TF-IDF Word Metrics Extraction ---
            elif action == "tfidf_encode" and "vectorizer" in params:
                vec = params["vectorizer"]
                words = params["words"]
                non_null_text = X_out[col].astype(str).fillna("")
                tfidf_mat = vec.transform(non_null_text).toarray()
                for j, word in enumerate(words):
                    new_col = f"tfidf_{col}_{word}"
                    X_out[new_col] = tfidf_mat[:, j]
                X_out = X_out.drop(columns=[col], errors="ignore")

            # --- Frequency Encoding ---
            elif action == "frequency_encode" and "frequencies" in params:
                freqs = params["frequencies"]
                X_out[col] = X_out[col].map(freqs).fillna(0.0)

            # --- Binary Encoding ---
            elif action == "binary_encode" and "categories" in params:
                cats = params["categories"]
                max_bits = params["max_bits"]
                cat_indices = {cat: idx for idx, cat in enumerate(cats)}
                for bit in range(max_bits):
                    bit_col = f"{col}_bit_{bit}"
                    X_out[bit_col] = X_out[col].apply(lambda val: float((cat_indices.get(val, 0) >> bit) & 1) if val in cat_indices else 0.0)
                X_out = X_out.drop(columns=[col], errors="ignore")

            # --- Rare Label Grouping ---
            elif action == "rare_label" and "frequent_categories" in params:
                frequent = params["frequent_categories"]
                X_out[col] = X_out[col].apply(lambda x: x if x in frequent else "Other")

            # --- Ordinal Encoding ---
            elif action == "ordinal_encode" and "order_map" in params:
                order_map = params["order_map"]
                X_out[col] = X_out[col].map(order_map).fillna(-1.0)

            # --- Polynomial Features ---
            elif action == "polynomial" and "degree" in params:
                deg = params["degree"]
                if pd.api.types.is_numeric_dtype(X_out[col]):
                    for d in range(2, deg + 1):
                        X_out[f"{col}_power_{d}"] = X_out[col] ** d

            # --- Group Level Aggregation ---
            elif action == "group_aggregate" and "grouped_values" in params:
                grouped = params["grouped_values"]
                group_col = params["group_col"]
                target_agg_col = params["target_agg_col"]
                func = params["func"]
                col_name = f"{target_agg_col}_{func}_by_{group_col}"
                # Handle collisions
                if col_name in X_out.columns:
                    col_name = f"{col_name}_2"
                X_out[col_name] = X_out[group_col].map(grouped).fillna(0.0)

            # --- Custom Formulas ---
            elif action == "custom_formula":
                # strat contains the arithmetic formula, e.g. "Age / Fare"
                parser = CustomFormulaParser(allowed_columns=X_out.columns)
                col_name = col  # destination column name
                X_out[col_name] = parser.evaluate(X_out, strat)

            # --- Feature Cross ---
            elif action == "feature_cross":
                # col is the new crossed name, strat is "col1,col2"
                c1, c2 = strat.split(",")
                X_out[col] = X_out[c1].astype(str) + "_" + X_out[c2].astype(str)

            # --- Time ordering Imputation fill ---
            elif action == "time_impute":
                # strat contains sorting datetime feature and fill method, e.g. "Date,ffill"
                date_col, method = strat.split(",")
                if date_col in X_out.columns:
                    X_out = X_out.sort_values(by=date_col)
                    if method == "ffill":
                        X_out[col] = X_out[col].ffill()
                    else:
                        X_out[col] = X_out[col].bfill()

            elif action == "cyclical_time":
                parsed = pd.to_datetime(X_out[col], errors="coerce")
                h = parsed.dt.hour.fillna(0)
                X_out[f"{col}_hour_sin"] = np.sin(2 * np.pi * h / 24.0)
                X_out[f"{col}_hour_cos"] = np.cos(2 * np.pi * h / 24.0)
                d = parsed.dt.dayofweek.fillna(0)
                X_out[f"{col}_dow_sin"] = np.sin(2 * np.pi * d / 7.0)
                X_out[f"{col}_dow_cos"] = np.cos(2 * np.pi * d / 7.0)
                m = parsed.dt.month.fillna(1)
                X_out[f"{col}_month_sin"] = np.sin(2 * np.pi * (m - 1) / 12.0)
                X_out[f"{col}_month_cos"] = np.cos(2 * np.pi * (m - 1) / 12.0)

            elif action == "extract_datetime":
                parsed = pd.to_datetime(X_out[col], errors="coerce")
                X_out[f"{col}_year"] = parsed.dt.year.fillna(0).astype(float)
                X_out[f"{col}_month"] = parsed.dt.month.fillna(0).astype(float)
                X_out[f"{col}_day"] = parsed.dt.day.fillna(0).astype(float)
                X_out[f"{col}_hour"] = parsed.dt.hour.fillna(0).astype(float)
                X_out[f"{col}_weekday"] = parsed.dt.dayofweek.fillna(0).astype(float)
                X_out[f"{col}_is_weekend"] = (parsed.dt.dayofweek >= 5).astype(float)
                X_out = X_out.drop(columns=[col], errors="ignore")

            elif action == "text_length":
                strs = X_out[col].astype(str).fillna("")
                X_out[f"{col}_char_count"] = strs.str.len().astype(float)
                X_out[f"{col}_word_count"] = strs.str.split().str.len().astype(float)
                X_out = X_out.drop(columns=[col], errors="ignore")

            elif action == "add_missing_indicator":
                X_out[f"{col}_is_null"] = X_out[col].isnull().astype(float)

            # --- Row Normalization ---
            elif action == "row_normalize":
                # scales rows to unit norm
                num_cols = [c for c in X_out.columns if pd.api.types.is_numeric_dtype(X_out[c])]
                row_norms = np.sqrt((X_out[num_cols] ** 2).sum(axis=1))
                row_norms = row_norms.replace({0: 1.0})
                X_out[num_cols] = X_out[num_cols].div(row_norms, axis=0)

        return X_out