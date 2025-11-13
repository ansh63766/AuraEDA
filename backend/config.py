# AuraEDA Global Configuration & Feature Flags

import os

FEATURES = {
    "smote": True,
    "mcar_test": True,
    "language_detection": True,
    "interaction_effects": True,
    "partial_correlation": True,
    "tfidf_nlp": True,
    "report_footer": os.getenv("REPORT_FOOTER", "")
}
