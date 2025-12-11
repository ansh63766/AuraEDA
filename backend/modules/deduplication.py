import pandas as pd
import numpy as np
import json
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class DeduplicationModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "deduplication"

    @property
    def display_name(self) -> str:
        return "Deduplication & Record Linkage"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        """
        Calculates exact duplicate counts and registers basic catalog summaries.
        """
        try:
            n_rows = len(df)
            if n_rows == 0:
                return {"status": "bypassed", "message": "Dataset is empty."}

            exact_dup = int(df.duplicated().sum())
            exact_pct = float(exact_dup / n_rows * 100)

            # Suggest candidates for record linkage (string/categorical columns)
            linkage_candidates = []
            for col in df.columns:
                if col == target_column:
                    continue
                if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
                    uniq = df[col].nunique()
                    if 1 < uniq < n_rows:
                        linkage_candidates.append(col)

            return {
                "status": "success",
                "exact_duplicates_count": exact_dup,
                "exact_duplicates_pct": exact_pct,
                "linkage_candidates": linkage_candidates
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Deduplication diagnostic failed: {str(e)}"
            }

def scan_duplicates(df: pd.DataFrame, columns: List[str], threshold: float = 0.85) -> List[Dict[str, Any]]:
    """
    Scans the dataset for suspected near-duplicate rows using the Sorted Neighborhood Method (SNM).
    1. Concatenates string representations of the specified columns.
    2. Sorts rows by this concatenated key.
    3. Scans with a sliding window of size 15.
    4. Runs TF-IDF character vectorizer + Cosine Similarity on candidates in the window.
    """
    n_rows = len(df)
    if n_rows < 2 or not columns:
        return []

    # Filter columns to only those that exist in df
    cols = [c for c in columns if c in df.columns]
    if not cols:
        return []

    # 1. Build concatenated key series, maintaining original index mapping
    keys = df[cols].astype(str).agg(" ".join, axis=1).str.strip().str.lower()
    
    # Store indices along with keys
    records = [{"index": idx, "key": key} for idx, key in zip(df.index, keys)]
    
    # 2. Sort by the concatenated key
    records.sort(key=lambda x: x["key"])

    matches = []
    seen_pairs = set()

    # Sliding window configuration
    window_size = 15

    # Group records by key length or compare within window
    for i in range(n_rows):
        # Determine current window boundary
        end_idx = min(i + window_size, n_rows)
        if i == end_idx - 1:
            break

        # Vectorize candidates in the current window together
        window_records = records[i:end_idx]
        window_keys = [rec["key"] for rec in window_records]

        # Ignore completely blank rows
        if not any(window_keys):
            continue

        try:
            vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(3, 4), min_df=1)
            tfidf_matrix = vectorizer.fit_transform(window_keys)
            sim_matrix = cosine_similarity(tfidf_matrix)

            # Compare pairs in the window
            for r1 in range(len(window_records)):
                for r2 in range(r1 + 1, len(window_records)):
                    score = float(sim_matrix[r1, r2])
                    if score >= threshold:
                        idx1 = window_records[r1]["index"]
                        idx2 = window_records[r2]["index"]

                        # Ensure consistent ordering of indices to avoid duplicate pairs
                        pair = (min(idx1, idx2), max(idx1, idx2))
                        if pair in seen_pairs:
                            continue

                        # Extract full row values (replace nan with "")
                        row1_data = df.loc[idx1].fillna("").to_dict()
                        row2_data = df.loc[idx2].fillna("").to_dict()

                        # Convert non-serializable objects to string
                        row1_clean = {k: (str(v) if not isinstance(v, (int, float, str, bool)) else v) for k, v in row1_data.items()}
                        row2_clean = {k: (str(v) if not isinstance(v, (int, float, str, bool)) else v) for k, v in row2_data.items()}

                        matches.append({
                            "similarity_score": round(score, 4),
                            "row1": {
                                "row_index": int(idx1),
                                "values": row1_clean
                            },
                            "row2": {
                                "row_index": int(idx2),
                                "values": row2_clean
                            }
                        })
                        seen_pairs.add(pair)
        except Exception:
            # Fallback to exact comparison if vectorizer fails (e.g. no terms found)
            for r1 in range(len(window_records)):
                for r2 in range(r1 + 1, len(window_records)):
                    if window_keys[r1] == window_keys[r2] and window_keys[r1]:
                        idx1 = window_records[r1]["index"]
                        idx2 = window_records[r2]["index"]
                        pair = (min(idx1, idx2), max(idx1, idx2))
                        if pair in seen_pairs:
                            continue
                        
                        row1_clean = df.loc[idx1].fillna("").to_dict()
                        row2_clean = df.loc[idx2].fillna("").to_dict()
                        
                        matches.append({
                            "similarity_score": 1.0,
                            "row1": {"row_index": int(idx1), "values": row1_clean},
                            "row2": {"row_index": int(idx2), "values": row2_clean}
                        })
                        seen_pairs.add(pair)

    # Sort matches by similarity score descending, return top 50
    matches.sort(key=lambda x: -x["similarity_score"])
    return matches[:50]

def get_cosine_clusters(df: pd.DataFrame, column: str, threshold: float = 0.8) -> List[Dict[str, Any]]:
    """
    Finds unique values in a column, groups them into similarity clusters using TF-IDF + Cosine,
    and returns suggested canonical values based on original value frequencies.
    """
    if column not in df.columns:
        return []

    # Get non-null, non-blank unique values
    series_clean = df[column].dropna().astype(str).str.strip()
    series_clean = series_clean[series_clean != ""]
    if len(series_clean) == 0:
        return []

    # Value frequencies
    freq_map = series_clean.value_counts().to_dict()
    unique_vals = list(freq_map.keys())
    if len(unique_vals) < 2:
        return []

    try:
        # Vectorize unique values
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), min_df=1)
        tfidf_matrix = vectorizer.fit_transform(unique_vals)
        sim_matrix = cosine_similarity(tfidf_matrix)

        # Build graph edges where similarity is greater than or equal to threshold
        edges = []
        n_unique = len(unique_vals)
        for i in range(n_unique):
            for j in range(i + 1, n_unique):
                if sim_matrix[i, j] >= threshold:
                    edges.append((i, j))

        # Run Breadth-First Search (BFS) to find connected components
        visited = set()
        adj = {node: [] for node in range(n_unique)}
        for u, v in edges:
            adj[u].append(v)
            adj[v].append(u)

        components = []
        for node in range(n_unique):
            if node not in visited:
                component = []
                queue = [node]
                visited.add(node)
                while queue:
                    curr = queue.pop(0)
                    component.append(curr)
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                components.append(component)

        # Build final cluster payloads
        clusters = []
        for idxs in components:
            # Exclude clusters of size 1 (no near-duplicates found)
            if len(idxs) <= 1:
                continue

            members = [{"value": unique_vals[i], "frequency": int(freq_map[unique_vals[i]])} for i in idxs]
            # Sort members by frequency descending, then string length ascending
            members.sort(key=lambda x: (-x["frequency"], len(x["value"])))

            # Canonical proposed is the first member (highest frequency)
            canonical = members[0]["value"]

            clusters.append({
                "canonical": canonical,
                "members": members
            })

        # Sort clusters by size (largest clusters first)
        clusters.sort(key=lambda x: -len(x["members"]))
        return clusters

    except Exception:
        return []
