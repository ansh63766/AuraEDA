import pandas as pd
import numpy as np
import re
import os
import json
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule

class AlertsModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "alerts"

    @property
    def display_name(self) -> str:
        return "Data Quality & Health Alerts"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        alerts = []
        n_rows = len(df)
        n_cols = len(df.columns)
        
        if n_rows == 0:
            return {
                "health_score": 0,
                "alerts": [{"severity": "high", "message": "Dataset is empty.", "category": "General", "column": "N/A"}],
                "integrity_breakdown": {
                    "Completeness": 0,
                    "Uniqueness": 0,
                    "Consistency": 0,
                    "Validity": 0,
                    "Timeliness": 0,
                    "Accuracy": 0
                },
                "semantic_types": {},
                "gdpr_pii": [],
                "benford_law": {},
                "ram_optimization": {"recommendations": [], "total_savings_bytes": 0}
            }

        # Deductions tracking for health score
        score_deductions = 0
        
        # 1. Duplicate Rows Check
        dup_rows = int(df.duplicated().sum())
        if dup_rows > 0:
            dup_percentage = (dup_rows / n_rows) * 100
            severity = "high" if dup_percentage > 10 else "medium"
            deduction = 10 if severity == "high" else 5
            score_deductions += deduction
            alerts.append({
                "column": "Dataset-wide",
                "metric": "duplicate_rows",
                "value": dup_rows,
                "severity": severity,
                "message": f"Dataset contains {dup_rows} duplicate rows ({dup_percentage:.1f}%).",
                "category": "Duplicates"
            })

        # 1.1 Near-Duplicate Rows (Fuzzy Check on Categoricals)
        categorical_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() > 1]
        near_dups = 0
        if len(categorical_cols) >= 2 and n_rows >= 5:
            # Check a sample of max 500 rows for performance
            sample_size = min(500, n_rows)
            sample_df = df[categorical_cols].sample(n=sample_size, random_state=42).astype(str)
            concat_rows = sample_df.agg(' '.join, axis=1).tolist()
            
            def lev_dist(s1, s2):
                if len(s1) < len(s2):
                    return lev_dist(s2, s1)
                if len(s2) == 0:
                    return len(s1)
                previous_row = range(len(s2) + 1)
                for i, c1 in enumerate(s1):
                    current_row = [i + 1]
                    for j, c2 in enumerate(s2):
                        insertions = previous_row[j + 1] + 1
                        deletions = current_row[j] + 1
                        substitutions = previous_row[j] + (c1 != c2)
                        current_row.append(min(insertions, deletions, substitutions))
                    previous_row = current_row
                return previous_row[-1]

            # Compare subset pairs
            comp_limit = min(150, len(concat_rows))
            for i in range(comp_limit):
                for j in range(i + 1, min(comp_limit, i + 30)):
                    s1, s2 = concat_rows[i], concat_rows[j]
                    max_len = max(len(s1), len(s2), 1)
                    dist = lev_dist(s1, s2)
                    similarity = 1.0 - (dist / max_len)
                    if similarity > 0.92 and similarity < 1.0:
                        near_dups += 1
            
            if near_dups > 0:
                score_deductions += 5
                alerts.append({
                    "column": "Dataset-wide",
                    "metric": "near_duplicate_rows",
                    "value": near_dups,
                    "severity": "medium",
                    "message": f"Detected near-duplicate records (approx. {near_dups} pairs with >92% textual similarity). Suggests fuzzy duplicates.",
                    "category": "Duplicates"
                })

        # 1.2 Contradictory Rows Check
        rules_path = os.path.join("config", "contradiction_rules.json")
        rules = []
        if os.path.exists(rules_path):
            try:
                with open(rules_path, "r", encoding="utf-8") as f:
                    rules = json.load(f)
            except Exception as e:
                print(f"Error loading contradiction rules: {e}")
        
        if not rules:
            # Fallback default rules
            rules = [
                {"if": "Age < 12", "then_not": "Married == 'Yes' or Married == 'Married' or Married == 'Y'", "label": "Underage marriage"},
                {"if": "Age < 0", "then_not": "Age < 0", "label": "Negative age"},
                {"if": "Salary < 0 or Income < 0", "then_not": "Salary < 0 or Income < 0", "label": "Negative salary/income"},
                {"if": "BirthYear > 2026 or Year > 2026", "then_not": "BirthYear > 2026 or Year > 2026", "label": "Future birth/event dates"},
                {"if": "Height < 30 or Weight < 2", "then_not": "Height < 30 or Weight < 2", "label": "Height/Weight impossibilities"}
            ]

        synonyms = {
            "Age": ["age", "yrs", "years"],
            "Married": ["married", "marry", "marital", "marital_status"],
            "Salary": ["salary", "income", "wage", "earnings", "pay"],
            "Income": ["income", "revenue", "earnings"],
            "BirthYear": ["birthyear", "birth_year", "yob", "year_of_birth"],
            "Height": ["height", "ht"],
            "Weight": ["weight", "wt"]
        }

        def resolve_query_string(expr, df_cols):
            resolved = expr
            sorted_cols = sorted(df_cols, key=len, reverse=True)
            matched_cols = set()
            for col in sorted_cols:
                pattern = re.compile(r'\b' + re.escape(col) + r'\b', re.IGNORECASE)
                if pattern.search(resolved):
                    resolved = pattern.sub(f"`{col}`", resolved)
                    matched_cols.add(col)

            for std_key, syn_list in synonyms.items():
                pattern = re.compile(r'\b' + re.escape(std_key) + r'\b', re.IGNORECASE)
                if pattern.search(resolved):
                    found_col = None
                    for syn in syn_list:
                        for col in df_cols:
                            if col.lower() == syn.lower() or syn.lower() in col.lower():
                                found_col = col
                                break
                        if found_col:
                            break
                    if found_col:
                        resolved = pattern.sub(f"`{found_col}`", resolved)
                        matched_cols.add(found_col)
                    else:
                        return None, None
            
            found_cols = re.findall(r'`([^`]+)`', resolved)
            for c in found_cols:
                if c not in df_cols:
                    return None, None

            return resolved, found_cols

        contradictory_rows_total = 0
        for rule in rules:
            if_expr = rule.get("if", "")
            then_not_expr = rule.get("then_not", "")
            label = rule.get("label", "Contradictory rows")
            
            if_resolved, cols_if = resolve_query_string(if_expr, df.columns)
            then_not_resolved, cols_then = resolve_query_string(then_not_expr, df.columns)
            
            if if_resolved and then_not_resolved:
                try:
                    query_expr = f"({if_resolved}) & ({then_not_resolved})"
                    contradictory_rows = df.query(query_expr)
                    contradiction_count = len(contradictory_rows)
                    if contradiction_count > 0:
                        contradictory_rows_total += contradiction_count
                        score_deductions += 8
                        all_involved_cols = list(set(cols_if + cols_then))
                        alerts.append({
                            "column": " & ".join(all_involved_cols),
                            "metric": "contradictory_rows",
                            "value": contradiction_count,
                            "severity": "high",
                            "message": f"Found {contradiction_count} logically contradictory rows ({label}: where {if_expr} and {then_not_expr}).",
                            "category": "Data Quality"
                        })
                except Exception:
                    pass

        # 2. Identical & Near-Duplicate Columns Check (>99% Similarity)
        dup_cols = []
        columns = df.columns.tolist()
        for i in range(len(columns)):
            for j in range(i + 1, len(columns)):
                col1, col2 = columns[i], columns[j]
                
                # Check absolute identical first
                if df[col1].equals(df[col2]):
                    dup_cols.append((col1, col2))
                    score_deductions += 10
                    alerts.append({
                        "column": f"{col1} & {col2}",
                        "metric": "duplicate_columns",
                        "value": col2,
                        "severity": "high",
                        "message": f"Columns '{col1}' and '{col2}' are identical.",
                        "category": "Duplicates"
                    })
                else:
                    # Check near-duplicate numeric correlations
                    if pd.api.types.is_numeric_dtype(df[col1]) and pd.api.types.is_numeric_dtype(df[col2]):
                        try:
                            corr = abs(df[col1].corr(df[col2]))
                            if corr > 0.99:
                                dup_cols.append((col1, col2))
                                score_deductions += 5
                                alerts.append({
                                    "column": f"{col1} & {col2}",
                                    "metric": "correlated_columns",
                                    "value": float(corr),
                                    "severity": "medium",
                                    "message": f"Columns '{col1}' and '{col2}' are extremely correlated (r = {corr:.4f} > 99%). Recommend dropping one.",
                                    "category": "Duplicates"
                                })
                        except Exception:
                            pass
                    # Check near-duplicate categorical values
                    else:
                        aligned = df[[col1, col2]].dropna()
                        if len(aligned) > 20:
                            match_rate = (aligned[col1] == aligned[col2]).mean()
                            if match_rate > 0.99:
                                dup_cols.append((col1, col2))
                                score_deductions += 5
                                alerts.append({
                                    "column": f"{col1} & {col2}",
                                    "metric": "correlated_columns",
                                    "value": float(match_rate),
                                    "severity": "medium",
                                    "message": f"Columns '{col1}' and '{col2}' contain matching text values in {match_rate*100:.1f}% of observations. Suggests duplicate features.",
                                    "category": "Duplicates"
                                })

        # 3. Column-specific quality audits
        total_nulls = 0
        total_invalid_positives = 0
        total_skewed_cols = 0
        total_mixed_types = 0
        total_outliers = 0
        
        for col in df.columns:
            null_count = int(df[col].isnull().sum())
            total_nulls += null_count
            null_rate = null_count / n_rows
            
            if null_rate == 1.0:
                score_deductions += 10
                alerts.append({
                    "column": col,
                    "metric": "all_missing",
                    "value": 1.0,
                    "severity": "high",
                    "message": f"Column '{col}' is entirely empty (100% missing values).",
                    "category": "Missing Data"
                })
                continue

            if null_rate > 0.5:
                score_deductions += 8
                alerts.append({
                    "column": col,
                    "metric": "high_missing",
                    "value": float(null_rate),
                    "severity": "high",
                    "message": f"Column '{col}' has {null_rate*100:.1f}% missing values.",
                    "category": "Missing Data"
                })
            elif null_rate > 0.05:
                score_deductions += 3
                alerts.append({
                    "column": col,
                    "metric": "moderate_missing",
                    "value": float(null_rate),
                    "severity": "medium",
                    "message": f"Column '{col}' has {null_rate*100:.1f}% missing values.",
                    "category": "Missing Data"
                })

            unique_count = df[col].nunique()
            if unique_count == 1:
                score_deductions += 8
                alerts.append({
                    "column": col,
                    "metric": "constant_column",
                    "value": 1,
                    "severity": "high",
                    "message": f"Column '{col}' has only one unique value (constant feature).",
                    "category": "Cardinality"
                })
                continue

            most_freq = df[col].value_counts().iloc[0]
            most_freq_rate = most_freq / n_rows
            if most_freq_rate > 0.95 and unique_count > 1:
                score_deductions += 6
                alerts.append({
                    "column": col,
                    "metric": "quasi_constant",
                    "value": float(most_freq_rate),
                    "severity": "high",
                    "message": f"Column '{col}' is quasi-constant (single value dominates representing {most_freq_rate*100:.1f}% of rows).",
                    "category": "Cardinality"
                })
            elif most_freq_rate > 0.90 and unique_count > 1:
                score_deductions += 3
                alerts.append({
                    "column": col,
                    "metric": "imbalanced_feature",
                    "value": float(most_freq_rate),
                    "severity": "medium",
                    "message": f"Column '{col}' is dominated by a single value representing {most_freq_rate*100:.1f}% of data.",
                    "category": "Imbalance"
                })

            # Check mixed-types
            if df[col].dtype == object:
                types_series = df[col].dropna().apply(lambda x: type(x).__name__)
                unique_types = list(types_series.unique())
                has_str = any(t in ['str'] for t in unique_types)
                has_num = any(t in ['int', 'float'] for t in unique_types)
                if len(unique_types) > 1 and has_str and has_num:
                    total_mixed_types += 1
                    score_deductions += 5
                    alerts.append({
                        "column": col,
                        "metric": "mixed_types",
                        "value": len(unique_types),
                        "severity": "medium",
                        "message": f"Column '{col}' contains mixed data types ({', '.join(unique_types)}).",
                        "category": "Data Type"
                    })

            # Check numeric features
            if pd.api.types.is_numeric_dtype(df[col]):
                col_data = df[col].dropna()
                
                # Check negative values on business sensitive columns
                col_lower = col.lower()
                if any(k in col_lower for k in ["age", "price", "fare", "cost", "salary", "quantity", "count", "income"]):
                    neg_count = int((col_data < 0).sum())
                    if neg_count > 0:
                        total_invalid_positives += neg_count
                        score_deductions += 5
                        alerts.append({
                            "column": col,
                            "metric": "negative_values",
                            "value": neg_count,
                            "severity": "high",
                            "message": f"Column '{col}' should not contain negatives but has {neg_count} negative entries.",
                            "category": "Data Quality"
                        })

                # High Skewness Check
                if len(col_data) > 2:
                    skew_val = col_data.skew()
                    if abs(skew_val) > 2.0:
                        total_skewed_cols += 1
                        score_deductions += 3
                        alerts.append({
                            "column": col,
                            "metric": "high_skew",
                            "value": float(skew_val),
                            "severity": "medium",
                            "message": f"Column '{col}' is highly skewed (skewness: {skew_val:.2f}).",
                            "category": "Distribution"
                        })

                # Outlier Check (IQR)
                if len(col_data) > 5:
                    q25, q75 = np.percentile(col_data, [25, 75])
                    iqr = q75 - q25
                    if iqr > 0:
                        lower_bound = q25 - 1.5 * iqr
                        upper_bound = q75 + 1.5 * iqr
                        outliers = col_data[(col_data < lower_bound) | (col_data > upper_bound)]
                        outlier_rate = len(outliers) / len(col_data)
                        if outlier_rate > 0.05:
                            total_outliers += len(outliers)
                            score_deductions += 4
                            alerts.append({
                                "column": col,
                                "metric": "high_outliers",
                                "value": float(outlier_rate),
                                "severity": "medium",
                                "message": f"Column '{col}' has {outlier_rate*100:.1f}% outliers (IQR method).",
                                "category": "Outliers"
                            })
            else:
                if unique_count > 100 and unique_count < n_rows:
                    score_deductions += 3
                    alerts.append({
                        "column": col,
                        "metric": "high_cardinality",
                        "value": unique_count,
                        "severity": "medium",
                        "message": f"Column '{col}' is categorical with high cardinality ({unique_count} unique values).",
                        "category": "Cardinality"
                    })

        # 4. Target Class Imbalance Check
        if target_column and target_column in df.columns:
            target_series = df[target_column].dropna()
            if target_series.nunique() > 1 and target_series.nunique() < 20:
                class_counts = target_series.value_counts(normalize=True)
                min_class_rate = class_counts.min()
                if min_class_rate < 0.10:
                    score_deductions += 10
                    alerts.append({
                        "column": target_column,
                        "metric": "class_imbalance",
                        "value": float(min_class_rate),
                        "severity": "high",
                        "message": f"Target column '{target_column}' is highly imbalanced. Minority class frequency: {min_class_rate*100:.1f}%.",
                        "category": "Imbalance"
                    })

        # Calculate final health score
        health_score = max(0, 100 - score_deductions)

        # 5. Radar Integrity Score Breakdown (Completeness, Uniqueness, Consistency, Validity, Timeliness, Accuracy)
        # Completeness
        completeness_raw = (1.0 - (total_nulls / (n_rows * n_cols))) if (n_rows * n_cols) > 0 else 1.0
        completeness = int(completeness_raw * 100)

        # Uniqueness
        uniqueness_raw = (1.0 - (dup_rows / n_rows)) if n_rows > 0 else 1.0
        uniqueness_score = uniqueness_raw * 100 - (len(dup_cols) * 5) - (near_dups * 2)
        uniqueness = int(max(0, min(100, uniqueness_score)))

        # Consistency
        consistency_score = 100 - (total_mixed_types * 8) - (contradictory_rows_total * 4)
        consistency = int(max(0, min(100, consistency_score)))

        # Validity
        # Deduct for invalid negative values and constant columns
        invalidity_penalty = (total_invalid_positives * 2) + sum(15 for c in df.columns if df[c].nunique() == 1)
        validity = int(max(0, 100 - invalidity_penalty))

        # Timeliness
        # Look for date columns and future years
        timeliness_penalty = 0
        for col in df.columns:
            if "year" in col.lower() or "date" in col.lower():
                try:
                    num_col = pd.to_numeric(df[col], errors="coerce").dropna()
                    future_count = (num_col > 2026).sum()
                    if future_count > 0:
                        timeliness_penalty += 15
                except Exception:
                    pass
        timeliness = int(max(0, 100 - timeliness_penalty))

        # Accuracy
        # Deduct for outliers and high skew
        accuracy_score = 100 - (total_skewed_cols * 6) - (total_outliers * 0.1)
        accuracy = int(max(0, min(100, accuracy_score)))

        integrity_breakdown = {
            "Completeness": completeness,
            "Uniqueness": uniqueness,
            "Consistency": consistency,
            "Validity": validity,
            "Timeliness": timeliness,
            "Accuracy": accuracy
        }

        # 6. Semantic Type Inference
        semantic_types = {}
        email_regex = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
        zip_regex = re.compile(r'^\d{5}(-\d{4})?$')
        uuid_regex = re.compile(r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$')
        phone_regex = re.compile(r'^\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$')

        for col in df.columns:
            col_lower = col.lower()
            if pd.api.types.is_numeric_dtype(df[col]):
                if any(k in col_lower for k in ["latitude", "longitude", "lat", "lon"]):
                    semantic_types[col] = "Coordinate"
                else:
                    semantic_types[col] = "Numeric"
                continue

            non_null = df[col].dropna().astype(str).str.strip()
            if len(non_null) == 0:
                semantic_types[col] = "N/A"
                continue

            sample_vals = non_null.sample(n=min(200, len(non_null)), random_state=42).tolist()
            matches = {"Email": 0, "ZIP": 0, "UUID": 0, "Phone": 0}

            for val in sample_vals:
                if email_regex.match(val):
                    matches["Email"] += 1
                elif zip_regex.match(val):
                    matches["ZIP"] += 1
                elif uuid_regex.match(val):
                    matches["UUID"] += 1
                elif phone_regex.match(val):
                    matches["Phone"] += 1

            total = len(sample_vals)
            matched = False
            for sem_type, match_count in matches.items():
                if match_count / total > 0.5:
                    semantic_types[col] = sem_type
                    matched = True
                    break

            if not matched:
                # Coordinate string checks ("lat, lon")
                coord_matches = 0
                for val in sample_vals:
                    if "," in val:
                        parts = [p.strip() for p in val.split(",")]
                        if len(parts) == 2:
                            try:
                                float(parts[0])
                                float(parts[1])
                                coord_matches += 1
                            except ValueError:
                                pass
                if coord_matches / total > 0.5:
                    semantic_types[col] = "Coordinate"
                else:
                    semantic_types[col] = "Categorical"

        # 7. GDPR Scanner (PII Flagging)
        gdpr_pii = []
        for col, sem_type in semantic_types.items():
            col_lower = col.lower()
            is_pii = False
            reason = ""
            
            if sem_type in ["Email", "Phone"]:
                is_pii = True
                reason = f"Contains semantic type '{sem_type}' values"
            elif any(k in col_lower for k in ["ssn", "social_security", "credit_card", "cc_num", "passport"]):
                is_pii = True
                reason = "Matches sensitive identifier column pattern"
            elif any(k in col_lower for k in ["fullname", "first_name", "last_name", "surname"]) and sem_type == "Categorical":
                is_pii = True
                reason = "Potential personal name values"

            if is_pii:
                gdpr_pii.append({
                    "column": col,
                    "reason": reason,
                    "suggested_action": "Mask" if sem_type == "Phone" else ("Hash" if sem_type == "Email" else "Drop")
                })

        # 8. Benford's Law Analysis
        benford_law = {}
        for col in df.select_dtypes(include=[np.number]).columns:
            col_data = df[col].dropna()
            if len(col_data) < 50:
                continue
            pos_data = col_data[col_data > 0]
            if len(pos_data) / len(col_data) < 0.9:
                continue
            p_min, p_max = pos_data.min(), pos_data.max()
            if p_min == 0 or (p_max / p_min) < 10:
                continue

            # First digit extraction (ignore leading zeros)
            first_digits = pos_data.astype(str).str.lstrip('0.').str.slice(0, 1)
            valid_digits = first_digits[first_digits.isin([str(d) for d in range(1, 10)])].astype(int)
            
            if len(valid_digits) >= 30:
                counts = valid_digits.value_counts(normalize=True).reindex(range(1, 10), fill_value=0.0).to_dict()
                theoretical = {d: float(np.log10(1.0 + 1.0 / d)) for d in range(1, 10)}
                
                benford_law[col] = {
                    "actual": {str(k): float(v) for k, v in counts.items()},
                    "theoretical": {str(k): float(v) for k, v in theoretical.items()}
                }

        # 9. RAM Memory Downcasting advisor
        ram_recommendations = []
        total_savings_bytes = 0
        for col in df.columns:
            col_data = df[col]
            current_dtype = str(col_data.dtype)
            suggested_dtype = None
            
            try:
                current_mem = int(col_data.memory_usage(deep=True))
            except Exception:
                current_mem = 0

            if pd.api.types.is_integer_dtype(col_data):
                c_min, c_max = col_data.min(), col_data.max()
                if not pd.isnull(c_min) and not pd.isnull(c_max):
                    if c_min >= -128 and c_max <= 127:
                        suggested_dtype = "int8"
                    elif c_min >= -32768 and c_max <= 32767:
                        suggested_dtype = "int16"
                    elif c_min >= -2147483648 and c_max <= 2147483647:
                        suggested_dtype = "int32"
            elif pd.api.types.is_float_dtype(col_data):
                if current_dtype == "float64":
                    suggested_dtype = "float32"
            elif current_dtype == "object":
                nunique = col_data.nunique()
                if 0 < nunique < 50 and (nunique / n_rows) < 0.2:
                    suggested_dtype = "category"

            if suggested_dtype and current_dtype != suggested_dtype:
                try:
                    if suggested_dtype == "category":
                        new_mem = int(df[col].astype("category").memory_usage(deep=True))
                    else:
                        new_mem = int(df[col].astype(suggested_dtype).memory_usage(deep=True))
                    savings = max(0, current_mem - new_mem)
                except Exception:
                    savings = 0

                if savings > 100:
                    total_savings_bytes += savings
                    ram_recommendations.append({
                        "column": col,
                        "current_dtype": current_dtype,
                        "suggested_dtype": suggested_dtype,
                        "savings_bytes": savings,
                        "message": f"Downcast '{col}' from {current_dtype} to {suggested_dtype} (est. savings: {savings / 1024:.1f} KB)"
                    })

        ram_optimization = {
            "recommendations": ram_recommendations,
            "total_savings_bytes": total_savings_bytes
        }

        return {
            "health_score": int(health_score),
            "alerts": alerts,
            "integrity_breakdown": integrity_breakdown,
            "semantic_types": semantic_types,
            "gdpr_pii": gdpr_pii,
            "benford_law": benford_law,
            "ram_optimization": ram_optimization
        }
