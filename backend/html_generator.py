import os
import io
import base64
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from collections import Counter
from typing import Dict, Any
from backend.config import FEATURES

def get_base64_plot(fig) -> str:
    """
    Converts a matplotlib figure to a base64 encoded PNG string.
    """
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches='tight')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return f"data:image/png;base64,{img_str}"

def generate_html_report(analysis_results: Dict[str, Any], target_column: str = None) -> str:
    """
    Compiles analysis metrics and LLM commentary into a beautiful standalone HTML dashboard.
    """
    summary = analysis_results.get("dataset_summary", {})
    results = analysis_results.get("results", {})
    
    # Extract results
    alerts_data = results.get("alerts", {})
    missing_data = results.get("missingness", {})
    dist_data = results.get("distributions", {})
    corr_data = results.get("correlations", {})
    leakage_data = results.get("leakage", {})
    drift_data = results.get("drift", {})
    pca_data = results.get("pca", {})
    importance_data = results.get("importance", {})
    datetime_data = results.get("datetime_eda", {})
    text_data = results.get("text_eda", {})
    outlier_data = results.get("outliers", {})
    
    health_score = alerts_data.get("health_score", 100)
    n_rows = summary.get("n_rows", 0)
    n_cols = summary.get("n_columns", 0)
    
    # Pre-generate plots on the backend to embed as base64
    missing_plot_b64 = ""
    corr_plot_b64 = ""
    drift_plot_b64 = ""
    pca_plot_b64 = ""
    importance_plot_b64 = ""
    datetime_plots_html = ""
    text_plots_html = ""
    
    # 1. Missingness Correlation Plot
    missing_summary = missing_data.get("summary", [])
    missing_cols = [x["column"] for x in missing_summary if x["missing_count"] > 0]
    null_correlation = missing_data.get("null_correlation", {})
    
    if null_correlation and "matrix" in null_correlation:
        cols = null_correlation["columns"]
        matrix_data = np.array(null_correlation["matrix"])
        if len(cols) > 1:
            fig, ax = plt.subplots(figsize=(6, 3))
            mask = np.triu(np.ones_like(matrix_data, dtype=bool))
            sns.heatmap(
                matrix_data, xticklabels=cols, yticklabels=cols, mask=mask,
                cmap="coolwarm", vmin=-1, vmax=1, center=0, cbar=True,
                annot=True, fmt=".2f", annot_kws={"size": 8}, ax=ax
            )
            ax.set_title("Missingness Nullity Pearson Correlation", fontsize=10, weight="bold")
            plt.xticks(rotation=45, ha='right', fontsize=8)
            plt.yticks(fontsize=8)
            plt.tight_layout()
            missing_plot_b64 = get_base64_plot(fig)
            
    # 2. Correlation Plot
    num_corr = corr_data.get("numeric_correlation", {})
    if num_corr and "matrix" in num_corr:
        cols = num_corr["columns"]
        matrix_data = np.array(num_corr["matrix"])
        if len(cols) > 1:
            if len(cols) > 12:
                cols = cols[:12]
                matrix_data = matrix_data[:12, :12]
            fig, ax = plt.subplots(figsize=(6, 4))
            mask = np.triu(np.ones_like(matrix_data, dtype=bool))
            sns.heatmap(
                matrix_data, xticklabels=cols, yticklabels=cols, mask=mask,
                cmap="RdBu", vmin=-1, vmax=1, center=0, cbar=True,
                annot=True, fmt=".2f", annot_kws={"size": 7}, ax=ax
            )
            ax.set_title("Pairwise Pearson Correlation Heatmap", fontsize=10, weight="bold")
            plt.xticks(rotation=45, ha='right', fontsize=7.5)
            plt.yticks(fontsize=7.5)
            plt.tight_layout()
            corr_plot_b64 = get_base64_plot(fig)

    # 3. Drift Plot
    drift_feats = drift_data.get("drift_features", [])
    if drift_data.get("status") == "success" and drift_feats:
        fig, ax = plt.subplots(figsize=(6.5, 3))
        top_drift = drift_feats[:8]
        cols_names = [x["column"] for x in top_drift]
        drops = [x["score_drop"] for x in top_drift]
        colors_palette = sns.color_palette("flare", len(top_drift))
        sns.barplot(x=drops, y=cols_names, palette=colors_palette, ax=ax)
        ax.set_title("Model Metric Drop on 10% Feature Shift", fontsize=10, weight="bold")
        ax.set_xlabel("Score Decrease (Validation Set)", fontsize=8)
        ax.set_ylabel("Column Name", fontsize=8)
        plt.xticks(fontsize=8)
        plt.yticks(fontsize=8)
        plt.tight_layout()
        drift_plot_b64 = get_base64_plot(fig)

    # 4. PCA Plot
    if pca_data.get("status") == "success":
        points = pca_data.get("points", [])
        targets = pca_data.get("targets", [])
        explained = pca_data.get("explained_variance", [0.0, 0.0])
        if points:
            fig, ax = plt.subplots(figsize=(6, 4))
            pc1 = [p["pc1"] for p in points]
            pc2 = [p["pc2"] for p in points]
            if targets:
                sns.scatterplot(x=pc1, y=pc2, hue=targets, palette="viridis", alpha=0.8, s=15, ax=ax)
                ax.legend(title=target_column, fontsize=8, title_fontsize=8.5)
            else:
                sns.scatterplot(x=pc1, y=pc2, color="#0891b2", alpha=0.7, s=15, ax=ax)
            ax.set_title(f"PCA 2D Cluster Projection (PC1={explained[0]*100:.1f}%, PC2={explained[1]*100:.1f}%)", fontsize=10, weight="bold")
            ax.set_xlabel("PC1", fontsize=8.5)
            ax.set_ylabel("PC2", fontsize=8.5)
            plt.tight_layout()
            pca_plot_b64 = get_base64_plot(fig)

    # 5. Feature Importance Plot
    if importance_data.get("status") == "success":
        feature_scores = importance_data.get("feature_importance", [])
        if feature_scores:
            fig, ax = plt.subplots(figsize=(6.5, 3))
            top_scores = feature_scores[:10]
            cols_names = [x["column"] for x in top_scores]
            scores_val = [x["importance_mean"] for x in top_scores]
            sns.barplot(x=scores_val, y=cols_names, palette="mako", ax=ax)
            ax.set_title("Permutation Feature Importance (Surrogate Booster)", fontsize=10, weight="bold")
            ax.set_xlabel("Importance Metric Score", fontsize=8)
            plt.tight_layout()
            importance_plot_b64 = get_base64_plot(fig)

    # 6. Datetime Seasonality Plots
    if datetime_data.get("status") == "success":
        for col_name, col_meta in datetime_data.get("features", {}).items():
            fig, axes = plt.subplots(1, 2, figsize=(11, 3))
            timeline = col_meta["timeline"]
            x_trend = pd.to_datetime(timeline["labels"])
            y_trend = timeline["counts"]
            axes[0].plot(x_trend, y_trend, color="#0891b2", linewidth=1.5)
            axes[0].set_title(f"Timeline Trend: {col_name}", fontsize=10, weight="bold")
            axes[0].tick_params(axis='x', rotation=30)
            
            weekly = col_meta["weekly"]
            axes[1].bar(weekly["labels"], weekly["counts"], color="#6366f1", alpha=0.8)
            axes[1].set_title("Weekly Seasonality (Count per Day)", fontsize=10, weight="bold")
            
            plt.tight_layout()
            b64_str = get_base64_plot(fig)
            datetime_plots_html += f"""
            <div class="card" style="margin-bottom: 20px;">
                <h4>Feature: <span class="code">{col_name}</span> (Valid range: {col_meta['min_date']} to {col_meta['max_date']})</h4>
                <div class="plot-container" style="margin-top: 10px;">
                    <img src="{b64_str}" alt="Datetime timeline seasonality">
                </div>
            </div>
            """

    # 7. NLP Word Counts & N-Grams Charts
    if text_data.get("status") == "success":
        for col_name, col_meta in text_data.get("features", {}).items():
            fig, ax = plt.subplots(figsize=(6.5, 3))
            unigrams = col_meta["unigrams"]
            sns.barplot(x=unigrams["counts"], y=unigrams["labels"], palette="viridis", ax=ax)
            ax.set_title(f"Top NLP Word Frequencies (Unigrams): {col_name}", fontsize=10, weight="bold")
            
            plt.tight_layout()
            b64_str = get_base64_plot(fig)
            s = col_meta["stats"]
            stats_summary = f"Avg Words: {s['avg_words']:.1f} | Max Words: {s['max_words']} | Avg Chars: {s['avg_characters']:.1f}"
            
            text_plots_html += f"""
            <div class="card" style="margin-bottom: 20px;">
                <h4>Feature: <span class="code">{col_name}</span> &bull; <i>{stats_summary}</i></h4>
                <div class="plot-container" style="margin-top: 10px;">
                    <img src="{b64_str}" alt="Text unigram frequency chart">
                </div>
            </div>
            """

    gen_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Define color mappings for severity classes
    health_class = "success"
    if health_score < 70:
        health_class = "danger"
    elif health_score < 90:
        health_class = "warning"

    # Build Health Score Penalty Breakdown Table
    from backend.pdf_generator import get_penalty_breakdown
    alerts_list = alerts_data.get("alerts", [])
    penalty_breakdown = get_penalty_breakdown(alerts_list)
    
    penalty_rows = ""
    if not penalty_breakdown:
        penalty_rows = "<tr><td colspan='3' style='text-align: center; color: var(--slate-400);'>No penalties applied. Clean dataset profile.</td></tr>"
    else:
        for p in penalty_breakdown:
            penalty_rows += f"""
            <tr>
                <td><strong>{p['category']}</strong></td>
                <td>{p['count']} warnings</td>
                <td class="text-danger"><strong>-{p['penalty']} pts</strong></td>
            </tr>
            """

    # Build Alerts table HTML rows
    alerts_rows = ""
    for alert in alerts_list:
        sev = alert.get("severity", "medium")
        alerts_rows += f"""
        <tr class="severity-{sev}">
            <td><strong>{alert.get('column')}</strong></td>
            <td><span class="badge badge-{sev}">{sev.upper()}</span></td>
            <td>{alert.get('category')}</td>
            <td>{alert.get('message')}</td>
        </tr>
        """
    if not alerts_rows:
        alerts_rows = "<tr><td colspan='4' style='text-align: center; color: var(--slate-400);'>No quality warnings detected in this dataset.</td></tr>"

    # Build Missing Columns table HTML rows (ALL Columns shown)
    missing_rows = ""
    for item in missing_summary:
        missing_rows += f"""
        <tr>
            <td><strong>{item['column']}</strong></td>
            <td><span class="code">{item.get('data_type', 'N/A')}</span></td>
            <td>{item['missing_count']:,}</td>
            <td>{item['missing_rate']*100:.1f}%</td>
            <td>{item['advice']}</td>
        </tr>
        """

    # Build Correlation Pairs table HTML rows
    high_pairs = corr_data.get("high_correlation_pairs", [])
    corr_rows = ""
    for pair in high_pairs[:12]:
        val = pair.get("correlation", 0.0)
        strength = pair.get("strength", "moderate")
        badge_cls = "danger" if strength == "strong" else "warning"
        corr_rows += f"""
        <tr>
            <td><strong>{pair.get('feature_1')}</strong></td>
            <td><strong>{pair.get('feature_2')}</strong></td>
            <td class="text-{badge_cls}"><strong>{val:.3f}</strong></td>
            <td><span class="badge badge-{badge_cls}">{strength.upper()}</span></td>
        </tr>
        """
    if not corr_rows:
        corr_rows = "<tr><td colspan='4' style='text-align: center; color: var(--slate-400);'>No high pairwise correlations detected.</td></tr>"

    # Multicollinearity VIF rows (ALL columns displayed + color-coded)
    vif_scores = corr_data.get("vif_scores", {})
    vif_rows = ""
    for k, v in sorted(vif_scores.items(), key=lambda x: x[1], reverse=True):
        v_str = "Infinity" if v >= 999999.0 else f"{v:.2f}"
        if v > 10.0:
            badge_cls = "danger"
            lbl = "Critical redundancy."
        elif v > 5.0:
            badge_cls = "warning"
            lbl = "Moderate redundancy."
        else:
            badge_cls = "success"
            lbl = "Safe."
            
        vif_rows += f"""
        <tr>
            <td><strong>{k}</strong></td>
            <td class="text-{badge_cls}"><strong>{v_str}</strong></td>
            <td><span class="badge badge-{badge_cls}">{lbl}</span></td>
        </tr>
        """
    if not vif_rows:
        vif_rows = "<tr><td colspan='3' style='text-align: center; color: var(--slate-400);'>VIF multicollinearity diagnostics empty or not run.</td></tr>"

    # Target Leakage rows
    leakage_rows = ""
    leakage_features = leakage_data.get("leakage_features", [])
    for x in leakage_features:
        risk = x["risk"]
        badge_cls = "danger" if risk == "high" else ("warning" if risk == "medium" else "success")
        leakage_rows += f"""
        <tr class="severity-{risk}">
            <td><strong>{x['column']}</strong></td>
            <td>{x['mutual_info']:.3f}</td>
            <td>{x['cv_score']:.2f} ({x['metric_name']})</td>
            <td><span class="badge badge-{badge_cls}">{risk.upper()}</span></td>
            <td>{x['reason']}</td>
        </tr>
        """

    # Drift rows
    drift_rows = ""
    drift_features = drift_data.get("drift_features", [])
    for x in drift_features:
        sens = x["sensitivity"]
        badge_cls = "danger" if sens == "high" else ("warning" if sens == "medium" else "success")
        drift_rows += f"""
        <tr class="severity-{sens}">
            <td><strong>{x['column']}</strong></td>
            <td>{x['baseline_score']:.3f}</td>
            <td>{x['perturbed_score']:.3f}</td>
            <td class="text-danger">-{x['score_drop']:.3f}</td>
            <td><span class="badge badge-{badge_cls}">{sens.upper()}</span></td>
        </tr>
        """

    # Outliers rows (No truncation - print all audited variables)
    outliers_rows = ""
    anoms = outlier_data.get("anomalies", [])
    for a in anoms:
        # Full variable list without truncation
        val_summary = ", ".join([f"<strong>{k}</strong>: {v}" for k, v in a["values"].items()])
        outliers_rows += f"""
        <tr>
            <td><strong>{a['row_index']}</strong></td>
            <td class="text-danger"><strong>{a['anomaly_score']:.4f}</strong></td>
            <td style="font-size:12.5px; color:var(--slate-300);">{val_summary}</td>
        </tr>
        """

    # Feature Profile rows
    profile_rows = ""
    features_dist = dist_data.get("features", {})
    for name, meta in features_dist.items():
        t = meta["type"]
        null_rate = meta["null_rate"]
        unique_cnt = meta["unique_count"]
        
        stats = meta.get("stats", {})
        details = ""
        if t == "numerical":
            details = f"Mean: {stats.get('mean',0.0):.2f} | Median: {stats.get('median',0.0):.2f} | Std: {stats.get('std',0.0):.2f} | Skew: {stats.get('skewness',0.0):.2f}"
            if stats.get("outlier_count", 0) > 0:
                details += f" | Outliers: {stats.get('outlier_count')} ({stats.get('outlier_rate',0.0)*100:.1f}%)"
        else:
            details = f"Top Category: '{stats.get('top_category')}' ({stats.get('top_rate',0.0)*100:.1f}%) | Cardinality: {unique_cnt}"

        profile_rows += f"""
        <tr>
            <td><strong>{name}</strong></td>
            <td><span class="badge badge-info">{t.upper()}</span></td>
            <td>{null_rate*100:.1f}%</td>
            <td>{unique_cnt}</td>
            <td style="font-size: 13px; color: var(--slate-300);">{details}</td>
        </tr>
        """

    # Build Dedicated Categorical Feature Summary rows
    categorical_features = {k: v for k, v in features_dist.items() if v["type"] == "categorical"}
    cat_summary_rows = ""
    for name, meta in categorical_features.items():
        stats = meta.get("stats", {})
        completeness = (1.0 - meta.get("null_rate", 0.0)) * 100
        top_rate = stats.get("top_rate", 0.0) * 100
        cat_summary_rows += f"""
        <tr>
            <td><strong>{name}</strong></td>
            <td>{meta.get('unique_count', 0)} unique values</td>
            <td>{completeness:.1f}% complete</td>
            <td><span class="code">{stats.get('top_category', 'N/A')}</span></td>
            <td class="text-warning"><strong>{top_rate:.1f}% bias</strong></td>
        </tr>
        """
    if not cat_summary_rows:
        cat_summary_rows = "<tr><td colspan='5' style='text-align: center; color: var(--slate-400);'>No categorical variables detected.</td></tr>"

    # Executive Summary 3 Bullets HTML
    bullets = get_executive_summary(analysis_results, target_column)
    exec_summary_html = ""
    for b in bullets:
        exec_summary_html += f"<li>{b}</li>"

    # Configurable report footer text
    footer_text = FEATURES.get("report_footer", "Confidential - For Internal Use Only")

    # Build HTML string
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraEDA Quality & Features Audit Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --slate-950: #020617;
            --slate-900: #0f172a;
            --slate-800: #1e293b;
            --slate-700: #334155;
            --slate-400: #94a3b8;
            --slate-300: #cbd5e1;
            --slate-100: #f1f5f9;
            --cyan-500: #06b6d4;
            --indigo-500: #6366f1;
            --rose-500: #f43f5e;
            --amber-500: #f59e0b;
            --emerald-500: #10b981;
            --glass-bg: rgba(30, 41, 59, 0.6);
            --glass-border: rgba(51, 65, 85, 0.4);
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            background-color: var(--slate-950);
            color: var(--slate-100);
            font-family: 'Inter', sans-serif;
            line-height: 1.6;
            padding: 20px;
        }}
        
        .layout {{
            display: flex;
            gap: 25px;
            max-width: 1500px;
            margin: 0 auto;
        }}
        
        /* Sidebar Table of Contents */
        .sidebar {{
            width: 320px;
            position: sticky;
            top: 20px;
            height: calc(100vh - 40px);
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 25px;
            backdrop-filter: blur(12px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: flex-column;
            overflow-y: auto;
        }}
        
        .sidebar h3 {{
            font-family: 'Outfit', sans-serif;
            font-size: 18px;
            margin-bottom: 20px;
            color: #fff;
            border-bottom: 1px solid var(--slate-700);
            padding-bottom: 10px;
        }}
        
        .sidebar ul {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        
        .sidebar li a {{
            color: var(--slate-300);
            text-decoration: none;
            font-size: 13.5px;
            padding: 8px 12px;
            border-radius: 8px;
            display: block;
            transition: all 0.2s ease;
        }}
        
        .sidebar li a:hover {{
            background-color: rgba(6, 182, 212, 0.15);
            color: var(--cyan-500);
            transform: translateX(4px);
        }}
        
        .sidebar li.not-applicable a {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        
        .main-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 30px;
        }}
        
        /* Header glass card */
        header {{
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 30px;
            backdrop-filter: blur(12px);
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            position: relative;
            overflow: hidden;
        }}
        
        header::after {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, var(--cyan-500), var(--indigo-500));
        }}
        
        .header-left h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 32px;
            font-weight: 700;
            background: linear-gradient(135deg, #ffffff 30%, var(--cyan-500) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
        }}
        
        .header-left p {{
            color: var(--slate-400);
            font-size: 14px;
        }}
        
        .health-ring {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        
        .health-score-container {{
            position: relative;
            width: 80px;
            height: 80px;
        }}
        
        .health-svg {{
            transform: rotate(-90deg);
            width: 80px;
            height: 80px;
        }}
        
        .health-track {{
            fill: none;
            stroke: var(--slate-700);
            stroke-width: 8;
        }}
        
        .health-fill {{
            fill: none;
            stroke-width: 8;
            stroke-linecap: round;
            stroke-dasharray: 226;
            stroke-dashoffset: calc(226 - (226 * {health_score}) / 100);
        }}
        
        .health-text {{
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            font-family: 'Outfit', sans-serif;
            font-size: 20px;
            font-weight: 700;
        }}
        
        .health-label {{
            text-align: right;
        }}
        
        .health-label div:first-child {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--slate-400);
        }}
        
        .health-label div:last-child {{
            font-size: 16px;
            font-weight: 600;
        }}
        
        .health-success {{ stroke: var(--emerald-500); color: var(--emerald-500); }}
        .health-warning {{ stroke: var(--amber-500); color: var(--amber-500); }}
        .health-danger {{ stroke: var(--rose-500); color: var(--rose-500); }}
        
        /* Stats Grid */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}
        
        .stat-card {{
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }}
        
        .stat-card div:first-child {{
            font-size: 12px;
            color: var(--slate-400);
            text-transform: uppercase;
            margin-bottom: 5px;
            letter-spacing: 1px;
        }}
        
        .stat-card div:last-child {{
            font-size: 24px;
            font-weight: 700;
            font-family: 'Outfit', sans-serif;
            color: #fff;
        }}
        
        /* Main Layout Section */
        .section {{
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            scroll-margin-top: 20px;
        }}
        
        .section-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--slate-700);
            padding-bottom: 12px;
        }}
        
        .section-header h2 {{
            font-family: 'Outfit', sans-serif;
            font-size: 20px;
            font-weight: 600;
        }}
        
        /* LLM Commentary Callout */
        .commentary-box {{
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(99, 102, 241, 0.1) 100%);
            border-left: 4px solid var(--cyan-500);
            border-radius: 4px 12px 12px 4px;
            padding: 20px;
            margin-bottom: 25px;
            font-style: italic;
        }}
        
        .commentary-box strong {{
            font-style: normal;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 1px;
            display: block;
            margin-bottom: 5px;
            color: var(--cyan-500);
        }}
        
        .not-applicable-notice {{
            background: rgba(30, 41, 59, 0.3);
            border: 1px dashed var(--slate-700);
            border-radius: 8px;
            padding: 25px;
            text-align: center;
            color: var(--slate-400);
            font-style: italic;
        }}
        
        /* Table styles */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            margin-bottom: 15px;
        }}
        
        th {{
            background-color: rgba(15, 23, 42, 0.6);
            color: var(--slate-400);
            text-align: left;
            padding: 12px 16px;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid var(--slate-700);
        }}
        
        td {{
            padding: 12px 16px;
            font-size: 13.5px;
            border-bottom: 1px solid var(--slate-800);
            word-break: break-word;
        }}
        
        tr:hover td {{
            background-color: rgba(51, 65, 85, 0.2);
        }}
        
        /* Badges */
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .badge-high, .badge-danger {{ background-color: rgba(244, 63, 94, 0.2); color: var(--rose-500); border: 1px solid rgba(244, 63, 94, 0.3); }}
        .badge-medium, .badge-warning {{ background-color: rgba(245, 158, 11, 0.2); color: var(--amber-500); border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-low, .badge-success {{ background-color: rgba(16, 185, 129, 0.2); color: var(--emerald-500); border: 1px solid rgba(16, 185, 129, 0.3); }}
        .badge-info {{ background-color: rgba(6, 182, 212, 0.2); color: var(--cyan-500); border: 1px solid rgba(6, 182, 212, 0.3); }}
        
        .code {{
            font-family: monospace;
            background-color: var(--slate-900);
            padding: 2px 6px;
            border-radius: 4px;
            color: var(--cyan-500);
            font-size: 13px;
        }}
        
        .text-danger {{ color: var(--rose-500); }}
        .text-warning {{ color: var(--amber-500); }}
        .text-success {{ color: var(--emerald-500); }}
        
        /* Two Column layout for graphics */
        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            align-items: center;
        }}
        
        .plot-container {{
            background-color: rgba(15, 23, 42, 0.4);
            border: 1px solid var(--slate-800);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        
        .plot-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }}
        
        footer {{
            text-align: center;
            color: var(--slate-400);
            font-size: 12px;
            margin-top: 30px;
            padding: 20px;
            border-top: 1px solid var(--slate-800);
        }}
        
        @media (max-width: 1100px) {{
            .layout {{
                flex-direction: column;
            }}
            .sidebar {{
                width: 100%;
                position: relative;
                height: auto;
                top: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="layout">
        
        <!-- Table of Contents Sidebar -->
        <div class="sidebar">
            <h3>AuraEDA Directory</h3>
            <ul>
                <li><a href="#sec-executive">Executive Summary</a></li>
                <li><a href="#sec-1">1. Quality & Health Alerts</a></li>
                <li><a href="#sec-2">2. Schema & Distributions</a></li>
                <li><a href="#sec-3">3. Missing Value Analysis</a></li>
                <li><a href="#sec-4">4. Correlations & VIF</a></li>
                <li class="{'not-applicable' if not target_column else ''}"><a href="#sec-5">5. Target Leakage Detector</a></li>
                <li class="{'not-applicable' if not target_column else ''}"><a href="#sec-6">6. Drift Sensitivity Simulation</a></li>
                <li class="{'not-applicable' if not pca_plot_b64 else ''}"><a href="#sec-7">7. Dimensionality projections</a></li>
                <li class="{'not-applicable' if not importance_plot_b64 else ''}"><a href="#sec-8">8. Feature Importance</a></li>
                <li class="{'not-applicable' if not datetime_plots_html else ''}"><a href="#sec-9">9. Datetime Timelines</a></li>
                <li class="{'not-applicable' if not text_plots_html else ''}"><a href="#sec-10">10. NLP Text Word Profiles</a></li>
                <li class="{'not-applicable' if not anoms else ''}"><a href="#sec-11">11. Multivariate Outliers</a></li>
                <li><a href="#sec-12">12. Dedicated Categorical Audit</a></li>
            </ul>
        </div>
        
        <div class="main-content">
            <!-- Header -->
            <header>
                <div class="header-left">
                    <h1>AuraEDA Quality & Features Audit</h1>
                    <p>Automated Premium Diagnostics &bull; Compiled on {gen_date}</p>
                </div>
                
                <div class="health-ring">
                    <div class="health-label">
                        <div>Dataset Integrity</div>
                        <div>{ "EXCELLENT" if health_score >= 90 else ("WARN" if health_score >= 70 else "CRITICAL") }</div>
                    </div>
                    <div class="health-score-container">
                        <svg class="health-svg">
                            <circle class="health-track" cx="40" cy="40" r="36" />
                            <circle class="health-fill health-{health_class}" cx="40" cy="40" r="36" />
                        </svg>
                        <div class="health-text health-{health_class}">{health_score}</div>
                    </div>
                </div>
            </header>
            
            <!-- Summary Stats -->
            <div class="summary-grid">
                <div class="stat-card">
                    <div>Total Rows</div>
                    <div>{n_rows:,}</div>
                </div>
                <div class="stat-card">
                    <div>Total Columns</div>
                    <div>{n_cols}</div>
                </div>
                <div class="stat-card">
                    <div>Missing Cells</div>
                    <div>{missing_data.get('total_missing_cells', 0):,}</div>
                </div>
                <div class="stat-card">
                    <div>Memory Footprint</div>
                    <div>{f"{summary.get('size_bytes', 0) / 1024:.1f} KB" if summary.get('size_bytes', 0) < 1024*1024 else f"{summary.get('size_bytes', 0) / (1024*1024):.2f} MB"}</div>
                </div>
            </div>

            <!-- Health Penalty Breakdown & Executive Summary Box -->
            <div id="sec-executive" class="section">
                <div class="section-header">
                    <h2>Executive Summary & Health Deductions</h2>
                </div>
                <div class="two-col">
                    <div>
                        <h4 style="margin-bottom: 10px;">3-Point Technical Overview:</h4>
                        <ul style="padding-left: 20px; display: flex; flex-direction: column; gap: 8px; font-size: 14px;">
                            {exec_summary_html}
                        </ul>
                    </div>
                    <div>
                        <h4 style="margin-bottom: 10px;">Deductions Table:</h4>
                        <table>
                            <thead>
                                <tr>
                                    <th>Anomaly Category</th>
                                    <th>Warnings</th>
                                    <th>Penalty</th>
                                </tr>
                            </thead>
                            <tbody>
                                {penalty_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Section 1: Alerts -->
            <div id="sec-1" class="section">
                <div class="section-header">
                    <h2>1. Data Quality & Health Alerts</h2>
                </div>
                {"<div class='commentary-box'><strong>So What?</strong>" + alerts_data.get('so_what') + "</div>" if alerts_data.get('so_what') else ""}
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Feature</th>
                                <th>Severity</th>
                                <th>Category</th>
                                <th>Anomaly / Message</th>
                            </tr>
                        </thead>
                        <tbody>
                            {alerts_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Section 2: Schema Distributions -->
            <div id="sec-2" class="section">
                <div class="section-header">
                    <h2>2. Feature Schema & Distribution Summary</h2>
                </div>
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Column Name</th>
                                <th>Data Type</th>
                                <th>Missing Rate</th>
                                <th>Unique Values</th>
                                <th>Key Metrics & Properties</th>
                            </tr>
                        </thead>
                        <tbody>
                            {profile_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Section 3: Missing Value Analysis -->
            <div id="sec-3" class="section">
                <div class="section-header">
                    <h2>3. Missing Value Patterns & Imputation Advices</h2>
                </div>
                {"<div class='commentary-box'><strong>So What?</strong>" + missing_data.get('so_what') + "</div>" if missing_data.get('so_what') else ""}
                <div class="two-col">
                    <div style="overflow-x: auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Column</th>
                                    <th>Type</th>
                                    <th>Null Count</th>
                                    <th>Null Rate</th>
                                    <th>Advisor Imputation</th>
                                </tr>
                            </thead>
                            <tbody>
                                {missing_rows}
                            </tbody>
                        </table>
                    </div>
                    {f'<div class="plot-container"><img src="{missing_plot_b64}" alt="Null Correlation Heatmap"><div style="font-size: 11px; color: var(--slate-400); margin-top: 8px;">Figure 1: Missingness nullity correlation patterns</div></div>' if missing_plot_b64 else '<div style="text-align: center; color: var(--slate-400); padding: 20px;">No missing correlations to plot.</div>'}
                </div>
            </div>

            <!-- Section 4: Correlations -->
            <div id="sec-4" class="section">
                <div class="section-header">
                    <h2>4. Feature Correlations & Multicollinearity</h2>
                </div>
                {"<div class='commentary-box'><strong>So What?</strong>" + corr_data.get('so_what') + "</div>" if corr_data.get('so_what') else ""}
                <div class="two-col">
                    <div>
                        <h3>Top Highly Correlated Feature Pairs</h3>
                        <table>
                            <thead>
                                <tr>
                                    <th>Feature A</th>
                                    <th>Feature B</th>
                                    <th>Correlation</th>
                                    <th>Association</th>
                                </tr>
                            </thead>
                            <tbody>
                                {corr_rows}
                            </tbody>
                        </table>
                        
                        <h3 style="margin-top: 25px;">Multicollinearity - VIF Scores</h3>
                        <table>
                            <thead>
                                <tr>
                                    <th>Numeric Column</th>
                                    <th>VIF Score</th>
                                    <th>Diagnosis</th>
                                </tr>
                            </thead>
                            <tbody>
                                {vif_rows}
                            </tbody>
                        </table>
                    </div>
                    {f'<div class="plot-container"><img src="{corr_plot_b64}" alt="Correlation Heatmap"><div style="font-size: 11px; color: var(--slate-400); margin-top: 8px;">Figure 2: Pearson correlation coefficient matrix heatmap</div></div>' if corr_plot_b64 else '<div style="text-align: center; color: var(--slate-400); padding: 20px;">Insufficient numeric variables for correlation matrix plot.</div>'}
                </div>
            </div>

            <!-- Section 5: Target Leakage (Dynamic indexing / Not-applicable check) -->
            <div id="sec-5" class="section">
                <div class="section-header">
                    <h2>5. Target Leakage Detector</h2>
                </div>
                {f"""
                {"<div class='commentary-box'><strong>So What?</strong>" + leakage_data.get('so_what') + "</div>" if leakage_data.get('so_what') else ""}
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Feature Column</th>
                                <th>Mutual Info</th>
                                <th>Single CV Score (Metric)</th>
                                <th>Leakage Risk</th>
                                <th>Reasoning</th>
                            </tr>
                        </thead>
                        <tbody>
                            {leakage_rows}
                        </tbody>
                    </table>
                </div>
                """ if target_column and leakage_rows else f"""
                <div class="not-applicable-notice">
                    Not applicable. A target variable was not defined, limiting supervised modeling readiness checks. Define a target in the Features Explorer for predictive audits.
                </div>
                """}
            </div>

            <!-- Section 6: Drift Sensitivity -->
            <div id="sec-6" class="section">
                <div class="section-header">
                    <h2>6. Feature Drift & Model Sensitivity Simulation</h2>
                </div>
                {f"""
                {"<div class='commentary-box'><strong>So What?</strong>" + drift_data.get('so_what') + "</div>" if drift_data.get('so_what') else ""}
                <div class="two-col">
                    <div style="overflow-x: auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Column Perturbed</th>
                                    <th>Baseline Score</th>
                                    <th>Perturbed Score</th>
                                    <th>Score drop</th>
                                    <th>Model Sensitivity</th>
                                </tr>
                            </thead>
                            <tbody>
                                {drift_rows}
                            </tbody>
                        </table>
                    </div>
                    <div class="plot-container">
                        <img src="{drift_plot_b64}" alt="Feature Drift Barplot">
                        <div style="font-size: 11px; color: var(--slate-400); margin-top: 8px;">Figure 3: Degradation in surrogate model metrics on 10% column drift</div>
                    </div>
                </div>
                """ if target_column and drift_plot_b64 else f"""
                <div class="not-applicable-notice">
                    Not applicable. A target variable was not defined, limiting supervised modeling readiness checks. Define a target in the Features Explorer for predictive audits.
                </div>
                """}
            </div>

            <!-- Section 7: PCA Projections -->
            <div id="sec-7" class="section">
                <div class="section-header">
                    <h2>7. Dimensionality Projections (PCA 2D Cluster Map)</h2>
                </div>
                {f"""
                {"<div class='commentary-box'><strong>So What?</strong>" + pca_data.get('so_what') + "</div>" if pca_data.get('so_what') else ""}
                <div class="plot-container">
                    <img src="{pca_plot_b64}" alt="PCA Scatter Projection">
                    <div style="font-size: 11px; color: var(--slate-400); margin-top: 8px;">Figure 4: PCA projection mapping row distributions across the top two components.</div>
                </div>
                """ if pca_plot_b64 else f"""
                <div class="not-applicable-notice">
                    Not applicable. PCA analysis not executed or failed to run. Ensure sufficient numeric features exist.
                </div>
                """}
            </div>

            <!-- Section 8: Feature Importance -->
            <div id="sec-8" class="section">
                <div class="section-header">
                    <h2>8. Surrogate Model Feature Importance</h2>
                </div>
                {f"""
                {"<div class='commentary-box'><strong>So What?</strong>" + importance_data.get('so_what') + "</div>" if importance_data.get('so_what') else ""}
                <div class="plot-container">
                    <img src="{importance_plot_b64}" alt="Feature Importance barplot">
                    <div style="font-size: 11px; color: var(--slate-400); margin-top: 8px;">Figure 5: Permutation importance weights. Features with higher scores are model keystones.</div>
                </div>
                """ if importance_plot_b64 else f"""
                <div class="not-applicable-notice">
                    Not applicable. Feature importance assessment was not run or target variable was omitted.
                </div>
                """}
            </div>

            <!-- Section 9: Datetime Timelines -->
            <div id="sec-9" class="section">
                <div class="section-header">
                    <h2>9. Datetime Seasonality & Timelines</h2>
                </div>
                {datetime_plots_html if datetime_plots_html else """
                <div class="not-applicable-notice">
                    Not applicable. No valid timestamp/datetime feature parsed in this dataset.
                </div>
                """}
            </div>

            <!-- Section 10: NLP Text Profiles -->
            <div id="sec-10" class="section">
                <div class="section-header">
                    <h2>10. NLP Text Word & N-Gram Profiles</h2>
                </div>
                {text_plots_html if text_plots_html else """
                <div class="not-applicable-notice">
                    Not applicable. No high-cardinality textual comments or sentences detected for NLP profiling.
                </div>
                """}
            </div>

            <!-- Section 11: Multivariate Outliers -->
            <div id="sec-11" class="section">
                <div class="section-header">
                    <h2>11. Multivariate Outlier Diagnostics (Isolation Forest)</h2>
                </div>
                {f"""
                {"<div class='commentary-box'><strong>So What?</strong>" + outlier_data.get('so_what') + "</div>" if outlier_data.get('so_what') else ""}
                <p style="margin-bottom: 15px;">Top most anomalous records identified across all numerical features (full variables listed):</p>
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Row Index</th>
                                <th>Anomaly Score</th>
                                <th>Key Values Summary</th>
                            </tr>
                        </thead>
                        <tbody>
                            {outliers_rows}
                        </tbody>
                    </table>
                </div>
                """ if anoms else """
                <div class="not-applicable-notice">
                    Not applicable. Isolation Forest diagnostics not executed or failed to run.
                </div>
                """}
            </div>

            <!-- Section 12: Dedicated Categorical Audit -->
            <div id="sec-12" class="section">
                <div class="section-header">
                    <h2>12. Dedicated Categorical Variables Audit</h2>
                </div>
                <p style="margin-bottom: 15px;">Detailed metric tracking for categorical data features, capturing class counts, completeness, and major biases:</p>
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Feature Column</th>
                                <th>Cardinality Span</th>
                                <th>Information Completeness</th>
                                <th>Mode Value</th>
                                <th>Skew Bias Ratio</th>
                            </tr>
                        </thead>
                        <tbody>
                            {cat_summary_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Footer -->
            <footer>
                <p>{footer_text}</p>
                <p>&copy; 2026 AuraEDA Automation Framework. All rights reserved.</p>
            </footer>
        </div>
    </div>
</body>
</html>
"""
    return html_template
