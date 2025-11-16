import os
import httpx
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load env variables
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def call_openrouter(messages: List[Dict[str, str]], max_tokens: int = 500) -> str:
    """
    Calls the OpenRouter API with the given messages.
    If no key is configured, returns a warning message.
    """
    if not OPENROUTER_API_KEY or "your_openrouter" in OPENROUTER_API_KEY.lower():
        return "[OpenRouter API Key not configured. Please add it to your .env file to enable LLM-generated commentary.]"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/shiva/auraeda",
        "X-Title": "AuraEDA Data Quality Report"
    }
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(OPENROUTER_URL, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
                # Handle error states
            else:
                return f"[LLM Error: Received HTTP {response.status_code} - {response.text}]"
    except Exception as e:
        return f"[LLM Connection Error: Could not reach OpenRouter - {str(e)}]"

def generate_so_what_commentary(module_name: str, module_data: Dict[str, Any], target_column: str = None) -> str:
    """
    Generates a concise 2-3 sentence data science "so what" commentary for a specific module's results.
    """
    # 1. Fallback / Mock Commentary if no API Key
    if not OPENROUTER_API_KEY or "your_openrouter" in OPENROUTER_API_KEY.lower():
        return get_mock_commentary(module_name, module_data, target_column)

    # 2. Build system and user prompts
    system_prompt = (
        "You are an expert senior data scientist and ML architect. "
        "Analyze the provided statistical findings and write a concise, professional 2-3 sentence 'so what' commentary. "
        "Explain: 1. What does this mean for downstream modeling? 2. What action should be taken? "
        "Be direct, highly technical, and avoid fluff. Do not use emojis, introductory phrases, or bullet points."
    )

    user_prompt = ""
    if module_name == "alerts":
        alerts = module_data.get("alerts", [])
        score = module_data.get("health_score", 100)
        user_prompt = f"Dataset Health Score: {score}/100. Anomalies detected: {alerts[:5]} (showing up to 5)."
    
    elif module_name == "missingness":
        overall = module_data.get("overall_missing_rate", 0.0)
        cols_missing = module_data.get("columns_with_missing_count", 0)
        summary = [{x["column"]: f"{x['missing_rate']*100:.1f}% missing"} for x in module_data.get("summary", []) if x["missing_count"] > 0][:5]
        user_prompt = f"Overall cell missingness rate: {overall*100:.1f}%. {cols_missing} columns have missing values. Top missing: {summary}."
    
    elif module_name == "distributions":
        features = module_data.get("features", {})
        skewed = []
        outliers = []
        for name, meta in features.items():
            stats = meta.get("stats", {})
            if stats.get("skewness", 0.0) > 1.5 or stats.get("skewness", 0.0) < -1.5:
                skewed.append(name)
            if stats.get("outlier_rate", 0.0) > 0.05:
                outliers.append(name)
        user_prompt = f"Highly skewed columns: {skewed[:5]}. Columns with outlier ratios > 5%: {outliers[:5]}."
    
    elif module_name == "correlations":
        pairs = module_data.get("high_correlation_pairs", [])
        vifs = {k: v for k, v in module_data.get("vif_scores", {}).items() if v > 5.0}
        user_prompt = f"High correlation feature pairs: {pairs[:5]}. Multicollinear features (VIF > 5): {vifs}."
    
    elif module_name == "leakage":
        if module_data.get("status") == "waiting":
            return "Leakage analysis pending selection of target column."
        features = module_data.get("leakage_features", [])
        high_risk = [x["column"] for x in features if x["risk"] == "high"]
        user_prompt = f"Target Leakage detection (Target: {target_column}). High-risk leaking columns: {high_risk}. Full details: {features[:3]}."
    
    elif module_name == "drift":
        if module_data.get("status") == "waiting":
            return "Drift sensitivity analysis pending selection of target column."
        features = module_data.get("drift_features", [])
        sensitive = [x["column"] for x in features if x["sensitivity"] == "high"]
        user_prompt = f"Feature drift validation (Target: {target_column}, baseline CV score: {module_data.get('baseline_score', 0.0)}). Features highly sensitive to 10% perturbation (inducing high metric drops): {sensitive}."
    
    else:
        return "Analysis completed successfully."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    return call_openrouter(messages, max_tokens=150)

def chat_about_data(history: List[Dict[str, str]], context_summary: Dict[str, Any]) -> str:
    """
    Handles context-aware chat conversation about the dataset.
    """
    if not OPENROUTER_API_KEY or "your_openrouter" in OPENROUTER_API_KEY.lower():
        return "I'm sorry, I cannot chat right now because the OpenRouter API Key is not configured. Please add your key to `.env` to start an interactive analysis."

    system_prompt = (
        "You are an elite senior data science advisor and ML architect named AuraEDA Copilot.\n"
        "You are discussing the user's dataset which has the following metadata:\n"
        f"Schema/Dtypes: {context_summary.get('dtypes')}\n"
        f"Row count: {context_summary.get('n_rows')}, Columns count: {context_summary.get('n_columns')}\n"
        f"Quality Alerts: {context_summary.get('alerts')[:10] if context_summary.get('alerts') else 'None'}\n\n"
        "### CORE GUIDELINES & CAPABILITIES:\n"
        "1. AuraEDA already performs fuzzy duplicate detection internally. Never recommend the user install fuzzywuzzy or run external deduplication tools — instead direct them to the Alerts tab where duplicates are already flagged, or the Data Wrangler where they can drop duplicates. The copilot must know its own capabilities.\n"
        "2. When recommending IterativeImputer, always use BayesianRidge as the default estimator, not RandomForestRegressor. Mention that RandomForestRegressor is more accurate but significantly slower — only recommend it for datasets under 10,000 rows.\n"
        "3. If no target is selected (e.g. if the user hasn't explicitly set one or asks leakage questions without selecting a target), you must NOT infer or assume a target variable. Instead say: 'I notice no target variable is selected. To give you leakage-specific advice, please select your target from the dropdown. I can see SurvivalLeak and Survived are identical — if Survived is your target, select it to enable leakage detection.' Do not treat domain knowledge (Titanic dataset) as a substitute for the user's explicit target selection.\n"
        "4. If you suggest droppable or transformable actions like dropping a column or imputing missing cells, output a hidden or visible structured JSON block at the very end of your response inside ```json and ``` format containing the key actions so that the user can apply them directly. Example:\n"
        "```json\n"
        "{\n"
        "  \"action\": \"drop_column\",\n"
        "  \"column\": \"SurvivalLeak\"\n"
        "}\n"
        "```\n"
        "Provide extremely detailed, mathematically sound, and actionable suggestions. "
        "Avoid fluff, maintain a highly professional tone, and write clear code snippets (Python/Pandas/Scikit-Learn) where appropriate."
    )

    messages = [{"role": "system", "content": system_prompt}] + history
    return call_openrouter(messages, max_tokens=2000)

def get_mock_commentary(module_name: str, module_data: Dict[str, Any], target_column: str = None) -> str:
    """
    A smart mock system fallback that reads computed statistics and returns a realistic commentary.
    """
    if module_name == "alerts":
        score = module_data.get("health_score", 100)
        alerts = module_data.get("alerts", [])
        if score > 90:
            return f"The dataset exhibits excellent structural integrity with a health score of {score}/100. No major anomalies were identified, making it suitable for immediate baseline modeling."
        elif score > 70:
            return f"Moderate anomalies have compromised the dataset's quality (health score: {score}/100), primarily driven by {len(alerts)} alerts. Address skewed distributions and moderate missingness before training models."
        else:
            return f"Significant data quality issues exist (health score: {score}/100) across {len(alerts)} alerts. Resolving duplicates, constant columns, and target imbalances is critical to prevent garbage-in-garbage-out model performance."

    elif module_name == "missingness":
        overall = module_data.get("overall_missing_rate", 0.0)
        cols_count = module_data.get("columns_with_missing_count", 0)
        if cols_count == 0:
            return "The dataset has zero missing values. Imputation is not required, preserving the natural sample distribution for downstream validation."
        else:
            return f"Missing values occupy {overall*100:.1f}% of total data, affecting {cols_count} features. For highly missing features, consider dropping or flag-and-imputing; for numerical columns, use median imputation for skewed targets and mean for normal distributions."

    elif module_name == "distributions":
        features = module_data.get("features", {})
        skewed = []
        outliers = []
        for name, meta in features.items():
            stats = meta.get("stats", {})
            if abs(stats.get("skewness", 0.0)) > 2.0:
                skewed.append(name)
            if stats.get("outlier_rate", 0.0) > 0.05:
                outliers.append(name)
        if not skewed and not outliers:
            return "All features exhibit stable, symmetric distributions with negligible outlier densities, indicating standard linear modeling assumptions will hold."
        else:
            msg = "Statistical variances are uneven. "
            if skewed:
                msg += f"Columns {skewed[:3]} show strong skewness, necessitating log-transforms. "
            if outliers:
                msg += f"Features {outliers[:3]} contain outlier densities above 5%; use robust scaling or tree-based algorithms."
            return msg

    elif module_name == "correlations":
        pairs = module_data.get("high_correlation_pairs", [])
        vifs = [k for k, v in module_data.get("vif_scores", {}).items() if v > 10.0]
        if not pairs and not vifs:
            return "Pairwise correlations are low, and multicollinearity is absent. Independent variable assumptions hold, making this dataset safe for ordinary least squares (OLS) regression."
        else:
            msg = f"Multi-variable dependency detected. "
            if pairs:
                msg += f"Strong pairwise correlation found between {pairs[0]['feature_1']} and {pairs[0]['feature_2']} ({pairs[0]['correlation']:.2f}). "
            if vifs:
                msg += f"High VIF scores (>10) for {vifs[:3]} suggest high multicollinearity; consider dropping or PCA reduction."
            return msg

    elif module_name == "leakage":
        if module_data.get("status") == "waiting":
            return "Target leakage analysis requires selecting a target variable."
        features = module_data.get("leakage_features", [])
        high_risk = [x["column"] for x in features if x["risk"] == "high"]
        if not high_risk:
            return f"No target leakage detected. Features show standard, safe predictive boundaries with respect to target '{target_column}'."
        else:
            return f"High risk of target leakage detected in feature(s): {high_risk[:2]}. These features exhibit suspiciously high predictive metrics (e.g. cross-validated AUC/R² > 0.95) and must be excluded from modeling to avoid optimistic generalization."

    elif module_name == "drift":
        if module_data.get("status") == "waiting":
            return "Drift sensitivity analysis requires selecting a target variable."
        features = module_data.get("drift_features", [])
        high_sensitive = [x["column"] for x in features if x["sensitivity"] == "high"]
        if not high_sensitive:
            return f"Surrogate model performance is robust; no individual feature shows excessive sensitivity to a 10% value shift."
        else:
            return f"Surrogate model is highly sensitive to shifts in: {high_sensitive[:2]}. A 10% value perturbation in these columns causes significant performance degradation, highlighting them as critical targets for monitoring in production."

    return "Analysis complete."
