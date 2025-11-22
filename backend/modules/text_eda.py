import pandas as pd
import numpy as np
import re
from typing import Dict, Any, List
from collections import Counter
from backend.analyzer_base import BaseAnalyzerModule

STOPWORDS = {
    "the", "and", "is", "of", "to", "in", "a", "for", "on", "with", "as", "at", 
    "by", "an", "it", "that", "this", "was", "be", "or", "from", "i", "you", 
    "he", "she", "they", "we", "but", "not", "with", "his", "her", "your", "my", "me"
}

class TextEdaModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "text_eda"

    @property
    def display_name(self) -> str:
        return "NLP Text Feature Profiling"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        text_features = {}
        n_rows = len(df)

        for col in df.columns:
            series = df[col]
            
            # Must be object/string type and not all missing
            if pd.api.types.is_numeric_dtype(series) or series.isnull().all():
                continue
                
            non_null = series.dropna().astype(str)
            if len(non_null) < 10:
                continue

            # Compute average character length
            avg_len = non_null.str.len().mean()
            unique_ratio = non_null.nunique() / len(non_null)
            
            # Text conditions: average length > 15 characters and unique ratio > 0.4 (excludes labels/ids)
            if avg_len > 15 and unique_ratio > 0.4:
                # 1. Compute Lengths and Word Counts
                char_lengths = non_null.str.len()
                word_counts = non_null.str.split().str.len()

                stats = {
                    "avg_characters": float(char_lengths.mean()),
                    "max_characters": int(char_lengths.max()),
                    "min_characters": int(char_lengths.min()),
                    "avg_words": float(word_counts.mean()),
                    "max_words": int(word_counts.max()),
                    "median_words": float(word_counts.median())
                }

                # 2. Tokenize and Count N-Grams
                words_list = []
                bigrams_list = []

                for text in non_null.values:
                    # Clean text
                    clean_text = re.sub(r"[^\w\s]", "", text.lower())
                    tokens = [t for t in clean_text.split() if t and t not in STOPWORDS]
                    
                    # Unigrams
                    words_list.extend(tokens)
                    
                    # Bigrams
                    for i in range(len(tokens) - 1):
                        bigrams_list.append(f"{tokens[i]} {tokens[i+1]}")

                unigram_counts = Counter(words_list).most_common(10)
                bigram_counts = Counter(bigrams_list).most_common(10)

                unigram_data = {
                    "labels": [x[0] for x in unigram_counts],
                    "counts": [int(x[1]) for x in unigram_counts]
                }
                
                bigram_data = {
                    "labels": [x[0] for x in bigram_counts],
                    "counts": [int(x[1]) for x in bigram_counts]
                }

                text_features[col] = {
                    "column": col,
                    "stats": stats,
                    "unigrams": unigram_data,
                    "bigrams": bigram_data
                }

        if not text_features:
            return {
                "status": "bypassed",
                "message": "No text/NLP columns detected in the dataset."
            }

        return {
            "status": "success",
            "features": text_features
        }