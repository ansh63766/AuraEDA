import os
import io
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from collections import Counter

from typing import Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from backend.config import FEATURES

# Define cohesive color scheme for light PDF report (ideal for printing)
PRIMARY_COLOR = colors.HexColor("#1e293b")  # slate-800
SECONDARY_COLOR = colors.HexColor("#0891b2")  # cyan-600
TEXT_COLOR = colors.HexColor("#334155")  # slate-700
LIGHT_BG = colors.HexColor("#f8fafc")  # slate-50
BORDER_COLOR = colors.HexColor("#e2e8f0")  # slate-200
CRITICAL_COLOR = colors.HexColor("#e11d48")  # rose-600
WARNING_COLOR = colors.HexColor("#d97706")  # amber-600
SUCCESS_COLOR = colors.HexColor("#16a34a")  # green-600

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically calculate the total page count
    and render a professional footer and header on all pages except the cover.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            if self._pageNumber > 1:
                self.draw_header_footer(page_count)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        
        # Header (Top of Page)
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(PRIMARY_COLOR)
        self.drawString(54, 750, "AURAEDA QUALITY & FEATURE ANALYSIS REPORT")
        self.setFont("Helvetica", 8)
        self.setFillColor(TEXT_COLOR)
        self.drawRightString(558, 750, datetime.datetime.now().strftime("%Y-%m-%d"))
        
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.75)
        self.line(54, 742, 558, 742)
        
        # Footer (Bottom of Page)
        self.line(54, 55, 558, 55)
        self.setFont("Helvetica", 8)
        self.setFillColor(TEXT_COLOR)
        
        # Configurable report footer text
        footer_text = FEATURES.get("report_footer", "")
        self.drawString(54, 40, footer_text)
        self.drawRightString(558, 40, f"Page {self._pageNumber} of {page_count}")
        
        self.restoreState()

def get_penalty_breakdown(alerts_list: list) -> list:
    """
    Groups alerts dynamically by category and maps them to severity-based score deductions.
    """
    category_map = {}
    for alert in alerts_list:
        cat = alert.get("category", "General")
        metric = alert.get("metric", "")
        
        # Default severity-based deductions
        penalty = 5
        if metric == "constant_column":
            penalty = 15
        elif metric == "duplicate_columns":
            penalty = 10
        elif metric == "all_missing":
            penalty = 10
        elif metric == "class_imbalance":
            penalty = 10
        elif metric == "mixed_type":
            penalty = 10
        elif metric == "contradictory_rows":
            penalty = 8
        elif metric == "high_missing":
            val = alert.get("value", 0)
            penalty = 8 if val > 0.5 else 5
        elif metric == "near_duplicate_rows":
            penalty = 5
        elif metric == "duplicate_rows":
            sev = alert.get("severity", "medium").lower()
            penalty = 10 if sev == "high" else 5
        elif metric == "quasi_constant":
            penalty = 5
        elif metric == "skewed_column":
            penalty = 5
            
        if cat not in category_map:
            category_map[cat] = {"count": 0, "penalty": 0}
        category_map[cat]["count"] += 1
        category_map[cat]["penalty"] += penalty
        
    return [{"category": k, "count": v["count"], "penalty": v["penalty"]} for k, v in category_map.items()]

def get_executive_summary(analysis_results: dict, target_column: str = None) -> list:
    """
    Dynamically generates a cohesive, smart 3-bullet Executive Summary.
    """
    summary = analysis_results.get("dataset_summary", {})
    results = analysis_results.get("results", {})
    health_score = results.get("alerts", {}).get("health_score", 100)
    alerts_list = results.get("alerts", {}).get("alerts", [])
    
    bullets = []
    
    # Bullet 1: Overall Health State
    if health_score >= 90:
        bullets.append(f"<b>Overall Health:</b> The dataset exhibits an excellent health score of <b>{health_score}/100</b> with minimal structural flaws, making it highly suitable for direct modeling pipelines.")
    elif health_score >= 70:
        bullets.append(f"<b>Overall Health:</b> The dataset has a moderate health score of <b>{health_score}/100</b>. We identified {len(alerts_list)} active quality warnings that require mild pre-processing and tuning.")
    else:
        bullets.append(f"<b>Overall Health:</b> The dataset is in a critical state with a health score of <b>{health_score}/100</b>. We flagged {len(alerts_list)} active alerts, indicating significant data quality issues that MUST be addressed before training any models.")
        
    # Bullet 2: Key Bottleneck
    if alerts_list:
        cats = [a.get("category", "General") for a in alerts_list]
        top_cat = Counter(cats).most_common(1)[0][0]
        bullets.append(f"<b>Primary Bottleneck:</b> Quality audits indicate that <b>{top_cat}</b> is the leading source of degradation, contributing most heavily to score penalties. Prioritize addressing columns flagged in this category.")
    else:
        bullets.append("<b>Primary Bottleneck:</b> No significant statistical anomalies, missing values, or multicollinearity patterns were detected as primary bottlenecks.")
        
    # Bullet 3: Modeling Readiness
    has_leakage = len(results.get("leakage", {}).get("leakage_features", [])) > 0
    if target_column:
        if has_leakage:
            bullets.append(f"<b>ML Readiness:</b> High Risk. Potential target leakage was detected with respect to '{target_column}'. Do not proceed with modeling until redundant or predictive-leakage features are pruned.")
        else:
            bullets.append(f"<b>ML Readiness:</b> Ready. The target column '{target_column}' is properly integrated. Run the pre-modeling pipeline to ensure robust validation splits.")
    else:
        bullets.append("<b>ML Readiness:</b> Underspecified. A target variable was not defined, limiting supervised modeling readiness checks. Define a target in the Features Explorer for predictive audits.")
        
    return bullets

def create_pdf_report(analysis_results: Dict[str, Any], filename: str, target_column: str = None) -> str:
    """
    Generates a beautifully formatted PDF report of the analysis results.
    """
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    # Custom Paragraph Styles
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=32,
        leading=38,
        textColor=PRIMARY_COLOR,
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=14,
        leading=18,
        textColor=SECONDARY_COLOR,
        spaceAfter=40
    )
    
    h1_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=PRIMARY_COLOR,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        "SubsectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=SECONDARY_COLOR,
        spaceBefore=8,
        spaceAfter=5,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12.5,
        textColor=TEXT_COLOR,
        spaceAfter=6
    )

    header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12.5,
        textColor=colors.white
    )

    commentary_style = ParagraphStyle(
        "CommentaryBox",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=12.5,
        textColor=PRIMARY_COLOR,
        spaceAfter=10
    )

    meta_style = ParagraphStyle(
        "MetadataText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=TEXT_COLOR
    )

    story = []

    # ------------------ COVER PAGE ------------------
    story.append(Spacer(1, 40))
    story.append(Paragraph("AuraEDA", title_style))
    story.append(Paragraph("Automated Data Quality & Feature Analysis Report", subtitle_style))
    
    summary = analysis_results.get("dataset_summary", {})
    results = analysis_results.get("results", {})
    health_score = results.get("alerts", {}).get("health_score", 100)

    # Health score color categorization
    health_color = SUCCESS_COLOR
    if health_score < 70:
        health_color = CRITICAL_COLOR
    elif health_score < 90:
        health_color = WARNING_COLOR

    metadata_table_data = [
        [Paragraph("<b>File Name:</b>", meta_style), Paragraph(os.path.basename(filename).replace(".pdf", ".csv"), meta_style)],
        [Paragraph("<b>Report Generated:</b>", meta_style), Paragraph(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), meta_style)],
        [Paragraph("<b>Dataset Rows:</b>", meta_style), Paragraph(f"{summary.get('n_rows', 0):,}", meta_style)],
        [Paragraph("<b>Dataset Columns:</b>", meta_style), Paragraph(f"{summary.get('n_columns', 0)}", meta_style)],
        [Paragraph("<b>Target Variable:</b>", meta_style), Paragraph(target_column if target_column else "Not Specified", meta_style)],
        [Paragraph("<b>Dataset Health Score:</b>", meta_style), Paragraph(f"<font color='{health_color}'><b>{health_score}/100</b></font>", meta_style)],
    ]
    
    meta_table = Table(metadata_table_data, colWidths=[150, 350])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))

    # Health Score Penalty Breakdown Table
    story.append(Paragraph("<b>Health Score Deductions Breakdown</b>", h2_style))
    alerts_list = results.get("alerts", {}).get("alerts", [])
    penalty_breakdown = get_penalty_breakdown(alerts_list)

    if not penalty_breakdown:
        p_table_data = [[Paragraph("No penalties applied. The dataset structurally conforms to all audited quality guidelines.", body_style)]]
        p_table = Table(p_table_data, colWidths=[500])
        p_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
            ('PADDING', (0,0), (-1,-1), 10),
            ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR)
        ]))
    else:
        p_table_data = [[
            Paragraph("Anomaly Category", header_style),
            Paragraph("Active Warnings Count", header_style),
            Paragraph("Severity Deduction", header_style)
        ]]
        for p in penalty_breakdown:
            p_table_data.append([
                Paragraph(p["category"], body_style),
                Paragraph(str(p["count"]), body_style),
                Paragraph(f"-{p['penalty']} pts", body_style)
            ])
        p_table = Table(p_table_data, colWidths=[250, 130, 120])
        p_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
            ('PADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG])
        ]))

    story.append(p_table)
    story.append(Spacer(1, 15))
    story.append(Paragraph("<i>This document is an automated statistical audit of the dataset's features, shapes, anomalies, target relationships, and drift boundaries. The findings include LLM-generated recommendations to guide pre-processing and model building pipelines.</i>", body_style))
    story.append(PageBreak())

    # ------------------ PAGE 2: TOC & EXECUTIVE SUMMARY ------------------
    story.append(Paragraph("Table of Contents", h1_style))
    story.append(Spacer(1, 5))
    
    # Active/Not-Active mapping for all 10 sections
    toc_data = [
        ["1. Data Quality & Health Alerts", "Active"],
        ["2. Missing Value Analysis", "Active"],
        ["3. Feature Distributions & Outliers", "Active"],
        ["4. Feature Correlations & Multicollinearity", "Active"],
        ["5. Target Leakage & Predictive Assessment", "Active" if target_column else "Not Applicable"],
        ["6. Feature Drift & Model Sensitivity Simulation", "Active" if target_column else "Not Applicable"],
        ["7. Dimensionality Reduction & PCA 2D Clustering", "Active" if results.get("pca", {}).get("status") == "success" else "Not Applicable"],
        ["8. Surrogate Model Feature Importance", "Active" if results.get("importance", {}).get("status") == "success" else "Not Applicable"],
        ["9. Multivariate Anomaly & Outlier Diagnostics", "Active" if results.get("outliers", {}).get("status") == "success" else "Not Applicable"],
        ["10. Dedicated Categorical Feature Summary", "Active"]
    ]
    
    t_toc_data = [[Paragraph("Report Section", header_style), Paragraph("Status", header_style)]]
    for row in toc_data:
        status_color = SUCCESS_COLOR if row[1] == "Active" else TEXT_COLOR
        t_toc_data.append([
            Paragraph(row[0], body_style),
            Paragraph(f"<font color='{status_color}'><b>{row[1]}</b></font>", body_style)
        ])
        
    t_toc = Table(t_toc_data, colWidths=[380, 120])
    t_toc.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
        ('PADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG])
    ]))
    story.append(t_toc)
    story.append(Spacer(1, 20))

    # Executive Summary Box
    story.append(Paragraph("Executive Summary", h1_style))
    bullets = get_executive_summary(analysis_results, target_column)
    for b in bullets:
        story.append(Paragraph(f"&bull; {b}", body_style))
        story.append(Spacer(1, 5))
        
    story.append(PageBreak())

    # ------------------ SECTION 1: HEALTH ALERTS ------------------
    story.append(Paragraph("1. Data Quality & Health Alerts", h1_style))
    story.append(Spacer(1, 5))
    
    comm_alerts = results.get("alerts", {}).get("so_what", "")
    if comm_alerts:
        story.append(Paragraph(f"<b>So What?</b> {comm_alerts}", commentary_style))
        story.append(Spacer(1, 5))

    if not alerts_list:
        story.append(Paragraph("No major alerts detected. The dataset structurally conforms to standard modeling expectations.", body_style))
    else:
        alert_table_data = [[
            Paragraph("Feature", header_style), 
            Paragraph("Category", header_style), 
            Paragraph("Severity", header_style), 
            Paragraph("Warning Message", header_style)
        ]]
        
        for alert in alerts_list:
            sev = alert.get("severity", "medium").upper()
            sev_color = TEXT_COLOR
            if sev == "HIGH":
                sev_color = CRITICAL_COLOR
            elif sev == "MEDIUM":
                sev_color = WARNING_COLOR
                
            alert_table_data.append([
                Paragraph(alert.get("column", "N/A"), body_style),
                Paragraph(alert.get("category", "General"), body_style),
                Paragraph(f"<font color='{sev_color}'><b>{sev}</b></font>", body_style),
                Paragraph(alert.get("message", ""), body_style)
            ])
            
        t_alerts = Table(alert_table_data, colWidths=[100, 80, 60, 260])
        t_alerts.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('PADDING', (0,0), (-1,-1), 5),
            ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG])
        ]))
        story.append(t_alerts)
    
    story.append(Spacer(1, 15))

    # ------------------ SECTION 2: MISSINGNESS ------------------
    story.append(Paragraph("2. Missing Value Analysis", h1_style))
    
    comm_missing = results.get("missingness", {}).get("so_what", "")
    if comm_missing:
        story.append(Paragraph(f"<b>So What?</b> {comm_missing}", commentary_style))
        story.append(Spacer(1, 5))

    missing_summary = results.get("missingness", {}).get("summary", [])
    
    # Show ALL columns in Missingness table to avoid missing details
    missing_table_data = [[
        Paragraph("Column", header_style), 
        Paragraph("Type", header_style),
        Paragraph("Null Count", header_style), 
        Paragraph("Null Rate", header_style), 
        Paragraph("Imputation Recommendation", header_style)
    ]]
    
    for item in missing_summary:
        missing_table_data.append([
            Paragraph(item["column"], body_style),
            Paragraph(item.get("data_type", "N/A"), body_style),
            Paragraph(f"{item['missing_count']:,}", body_style),
            Paragraph(f"{item['missing_rate']*100:.1f}%", body_style),
            Paragraph(item["advice"], body_style)
        ])
        
    t_missing = Table(missing_table_data, colWidths=[110, 60, 60, 60, 210])
    t_missing.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('PADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG])
    ]))
    story.append(t_missing)
    
    # Missingness correlation matrix plot
    missing_cols = [x["column"] for x in missing_summary if x["missing_count"] > 0]
    if len(missing_cols) > 1 and len(missing_cols) <= 20:
        story.append(Spacer(1, 10))
        plt.figure(figsize=(6, 2.5))
        sns.set_theme(style="white")
        
        null_correlation = results.get("missingness", {}).get("null_correlation", {})
        if null_correlation and "matrix" in null_correlation:
            cols = null_correlation["columns"]
            matrix_data = np.array(null_correlation["matrix"])
            
            mask = np.triu(np.ones_like(matrix_data, dtype=bool))
            sns.heatmap(
                matrix_data, xticklabels=cols, yticklabels=cols, mask=mask,
                cmap="coolwarm", vmin=-1, vmax=1, center=0, cbar=True,
                annot=True, fmt=".2f", annot_kws={"size": 7}
            )
            plt.title("Missingness Correlation Matrix (Nullity Pearson)", fontsize=9, color="#1e293b", weight="bold")
            plt.xticks(rotation=45, ha='right', fontsize=7)
            plt.yticks(fontsize=7)
            plt.tight_layout()
            
            img_buf = io.BytesIO()
            plt.savefig(img_buf, format='png', dpi=200)
            img_buf.seek(0)
            plt.close()
            
            story.append(Spacer(1, 5))
            story.append(Image(img_buf, width=320, height=130))
            story.append(Paragraph("<font size='7.5'><i>Figure 1: Pearson correlation of missingness indicators. Values near +1 suggest columns are missing together.</i></font>", body_style))
            
    story.append(PageBreak())

    # ------------------ SECTION 3: DISTRIBUTIONS ------------------
    story.append(Paragraph("3. Feature Distributions & Outliers", h1_style))
    
    comm_dist = results.get("distributions", {}).get("so_what", "")
    if comm_dist:
        story.append(Paragraph(f"<b>So What?</b> {comm_dist}", commentary_style))
        story.append(Spacer(1, 5))

    features_dist = results.get("distributions", {}).get("features", {})
    num_features = {k: v for k, v in features_dist.items() if v["type"] == "numerical"}
    
    if num_features:
        story.append(Paragraph("<b>Numerical Features Summary:</b>", h2_style))
        num_table_data = [[
            Paragraph("Feature", header_style),
            Paragraph("Mean", header_style),
            Paragraph("Median", header_style),
            Paragraph("Skewness", header_style),
            Paragraph("Outliers %", header_style),
            Paragraph("Zero Rate", header_style)
        ]]
        
        for name, meta in list(num_features.items())[:12]:
            stats = meta.get("stats", {})
            num_table_data.append([
                Paragraph(name, body_style),
                Paragraph(f"{stats.get('mean', 0.0):.2f}", body_style),
                Paragraph(f"{stats.get('median', 0.0):.2f}", body_style),
                Paragraph(f"{stats.get('skewness', 0.0):.2f}", body_style),
                Paragraph(f"{stats.get('outlier_rate', 0.0)*100:.1f}%", body_style),
                Paragraph(f"{meta.get('zero_rate', 0.0)*100:.1f}%", body_style)
            ])
            
        t_num = Table(num_table_data, colWidths=[120, 75, 75, 75, 75, 80])
        t_num.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('PADDING', (0,0), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG])
        ]))
        story.append(t_num)
    else:
        story.append(Paragraph("No numerical features found to summarize distributions.", body_style))
        
    story.append(Spacer(1, 15))

    # ------------------ SECTION 4: CORRELATIONS ------------------
    story.append(Paragraph("4. Feature Correlations & Multicollinearity", h1_style))
    
    comm_corr = results.get("correlations", {}).get("so_what", "")
    if comm_corr:
        story.append(Paragraph(f"<b>So What?</b> {comm_corr}", commentary_style))
        story.append(Spacer(1, 5))

    corr_data = results.get("correlations", {})
    high_pairs = corr_data.get("high_correlation_pairs", [])
    vifs = corr_data.get("vif_scores", {})
    
    # Pairwise heatmap
    num_corr = corr_data.get("numeric_correlation", {})
    if num_corr and "matrix" in num_corr:
        cols = num_corr["columns"]
        matrix_data = np.array(num_corr["matrix"])
        
        if len(cols) > 1:
            plt.figure(figsize=(6, 3.5))
            sns.set_theme(style="white")
            
            if len(cols) > 12:
                cols = cols[:12]
                matrix_data = matrix_data[:12, :12]
                
            mask = np.triu(np.ones_like(matrix_data, dtype=bool))
            sns.heatmap(
                matrix_data, xticklabels=cols, yticklabels=cols, mask=mask,
                cmap="RdBu", vmin=-1, vmax=1, center=0, cbar=True,
                annot=True, fmt=".2f", annot_kws={"size": 6}
            )
            plt.title("Pairwise Pearson Correlation Heatmap", fontsize=10, color="#1e293b", weight="bold")
            plt.xticks(rotation=45, ha='right', fontsize=6.5)
            plt.yticks(fontsize=6.5)
            plt.tight_layout()
            
            img_buf = io.BytesIO()
            plt.savefig(img_buf, format='png', dpi=200)
            img_buf.seek(0)
            plt.close()
            
            story.append(Image(img_buf, width=320, height=186))
            story.append(Spacer(1, 5))
            story.append(Paragraph("<font size='7.5'><i>Figure 2: Heatmap showing pairwise Pearson correlation coefficient. Red indicates positive correlation, blue indicates negative.</i></font>", body_style))
            story.append(Spacer(1, 10))

    # Multicollinearity VIF display (ALL numerical columns included)
    if vifs:
        story.append(Paragraph("<b>Variance Inflation Factor (VIF) Scores:</b>", h2_style))
        vif_table_data = [[
            Paragraph("Feature", header_style), 
            Paragraph("VIF Score", header_style), 
            Paragraph("Redundancy Level / Color Code", header_style)
        ]]
        
        for k, v in sorted(vifs.items(), key=lambda x: x[1], reverse=True):
            v_str = "Infinity" if v >= 999999.0 else f"{v:.2f}"
            
            # Color coding VIF scales green, yellow, red
            if v > 10.0:
                color_tag = f"<font color='{CRITICAL_COLOR.hexval()}'><b>CRITICAL REDUNDANCY</b></font>"
            elif v > 5.0:
                color_tag = f"<font color='{WARNING_COLOR.hexval()}'><b>MODERATE REDUNDANCY</b></font>"
            else:
                color_tag = f"<font color='{SUCCESS_COLOR.hexval()}'><b>SAFE</b></font>"
                
            vif_table_data.append([
                Paragraph(k, body_style),
                Paragraph(v_str, body_style),
                Paragraph(color_tag, body_style)
            ])
            
        t_vif = Table(vif_table_data, colWidths=[150, 100, 250])
        t_vif.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('PADDING', (0,0), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG])
        ]))
        story.append(t_vif)
    else:
        story.append(Paragraph("VIF calculation not run or no numeric variables present.", body_style))
        
    story.append(PageBreak())

    # ------------------ SECTION 5: TARGET LEAKAGE & PREDICTIVE ASSESSMENT ------------------
    story.append(Paragraph("5. Target Leakage & Predictive Assessment", h1_style))
    if target_column:
        comm_leakage = results.get("leakage", {}).get("so_what", "")
        if comm_leakage:
            story.append(Paragraph(f"<b>So What? (Target Leakage)</b> {comm_leakage}", commentary_style))
            story.append(Spacer(1, 5))

        leakage_feats = results.get("leakage", {}).get("leakage_features", [])
        high_leakage = [x for x in leakage_feats if x["risk"] == "high"]
        
        if not leakage_feats:
            story.append(Paragraph("Leakage assessment was not executed.", body_style))
        elif not high_leakage:
            story.append(Paragraph("No features demonstrate symptoms of Target Leakage. All columns possess predictive signals inside normal thresholds.", body_style))
        else:
            story.append(Paragraph("<b>Flagged Leakage Features:</b>", h2_style))
            leakage_table_data = [[
                Paragraph("Feature", header_style),
                Paragraph("Mutual Info", header_style),
                Paragraph("CV Score", header_style),
                Paragraph("Metric", header_style),
                Paragraph("Analysis", header_style)
            ]]

            for x in high_leakage[:5]:
                leakage_table_data.append([
                    Paragraph(x["column"], body_style),
                    Paragraph(f"{x['mutual_info']:.3f}", body_style),
                    Paragraph(f"{x['cv_score']:.2f}", body_style),
                    Paragraph(x["metric_name"], body_style),
                    Paragraph(f"<font color='{CRITICAL_COLOR.hexval()}'><b>{x['reason']}</b></font>", body_style)
                ])
                
            t_leakage = Table(leakage_table_data, colWidths=[100, 60, 60, 60, 220])
            t_leakage.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('PADDING', (0,0), (-1,-1), 4),
                ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ]))
            story.append(t_leakage)
    else:
        story.append(Paragraph("<i>Not applicable. A target variable was not defined, limiting supervised modeling readiness checks. Define a target in the Features Explorer for predictive audits.</i>", body_style))
        
    story.append(Spacer(1, 15))

    # ------------------ SECTION 6: FEATURE DRIFT & MODEL SENSITIVITY SIMULATION ------------------
    story.append(Paragraph("6. Feature Drift & Model Sensitivity Simulation", h1_style))
    if target_column:
        comm_drift = results.get("drift", {}).get("so_what", "")
        if comm_drift:
            story.append(Paragraph(f"<b>So What? (Drift Sensitivity)</b> {comm_drift}", commentary_style))
            story.append(Spacer(1, 5))

        drift_data = results.get("drift", {})
        drift_feats = drift_data.get("drift_features", [])
        
        if drift_data.get("status") == "success" and drift_feats:
            story.append(Paragraph(f"Surrogate model type: Gradient Booster. Baseline Validation {drift_data.get('metric_name', 'Score')}: {drift_data.get('baseline_score', 0.0):.3f}.", body_style))
            
            plt.figure(figsize=(6, 2.5))
            sns.set_theme(style="whitegrid")
            
            top_drift = drift_feats[:8]
            cols_names = [x["column"] for x in top_drift]
            drops = [x["score_drop"] for x in top_drift]
            
            colors_palette = sns.color_palette("flare", len(top_drift))
            sns.barplot(x=drops, y=cols_names, palette=colors_palette)
            plt.title("Model Sensitivity to 10% Value Shift / Noise (Metric Drop)", fontsize=9, color="#1e293b", weight="bold")
            plt.xlabel("Validation Score Decrease", fontsize=7.5)
            plt.ylabel("Perturbed Column Name", fontsize=7.5)
            plt.xticks(fontsize=7)
            plt.yticks(fontsize=7)
            plt.tight_layout()
            
            img_buf = io.BytesIO()
            plt.savefig(img_buf, format='png', dpi=200)
            img_buf.seek(0)
            plt.close()
            
            story.append(Spacer(1, 5))
            story.append(Image(img_buf, width=320, height=133))
            story.append(Spacer(1, 5))
            story.append(Paragraph("<font size='7.5'><i>Figure 3: Metric decrease caused by pertubing feature by 10%. Columns with higher bars represent higher sensitivity to feature drift.</i></font>", body_style))
        else:
            story.append(Paragraph("Drift sensitivity simulation not run or failed.", body_style))
    else:
        story.append(Paragraph("<i>Not applicable. A target variable was not defined, limiting supervised modeling readiness checks. Define a target in the Features Explorer for predictive audits.</i>", body_style))
        
    story.append(PageBreak())

    # ------------------ SECTION 7: DIMENSIONALITY & CLUSTERS (PCA) ------------------
    story.append(Paragraph("7. Dimensionality Reduction & PCA 2D Clustering", h1_style))
    pca_data = results.get("pca", {})
    if pca_data.get("status") == "success":
        comm_pca = pca_data.get("so_what", "")
        if comm_pca:
            story.append(Paragraph(f"<b>So What?</b> {comm_pca}", commentary_style))
            story.append(Spacer(1, 5))

        points = pca_data.get("points", [])
        targets = pca_data.get("targets", [])
        explained = pca_data.get("explained_variance", [0.0, 0.0])

        if points:
            plt.figure(figsize=(6, 3.8))
            sns.set_theme(style="white")
            
            pc1 = [p["pc1"] for p in points]
            pc2 = [p["pc2"] for p in points]
            
            if targets:
                sns.scatterplot(x=pc1, y=pc2, hue=targets, palette="viridis", alpha=0.8, edgecolor="none", s=15)
                plt.legend(title=target_column, fontsize=7, title_fontsize=7.5, loc="best")
            else:
                sns.scatterplot(x=pc1, y=pc2, color="#0891b2", alpha=0.7, edgecolor="none", s=15)

            plt.title(f"PCA 2D Cluster Projection (Variance: PC1={explained[0]*100:.1f}%, PC2={explained[1]*100:.1f}%)", fontsize=9, color="#1e293b", weight="bold")
            plt.xlabel("Principal Component 1", fontsize=7.5)
            plt.ylabel("Principal Component 2", fontsize=7.5)
            plt.xticks(fontsize=7)
            plt.yticks(fontsize=7)
            plt.tight_layout()

            img_buf = io.BytesIO()
            plt.savefig(img_buf, format='png', dpi=200)
            img_buf.seek(0)
            plt.close()

            story.append(Image(img_buf, width=320, height=200))
            story.append(Spacer(1, 5))
            story.append(Paragraph("<font size='7.5'><i>Figure 4: 2D Projection of the dataset using Principal Component Analysis. Groups representing structural patterns are highlighted.</i></font>", body_style))
    else:
        story.append(Paragraph("<i>Not applicable. PCA analysis not executed or failed to run. Ensure sufficient numeric features exist.</i>", body_style))
        
    story.append(Spacer(1, 15))

    # ------------------ SECTION 8: SURROGATE IMPORTANCE ------------------
    story.append(Paragraph("8. Surrogate Model Feature Importance", h1_style))
    importance_data = results.get("importance", {})
    if importance_data.get("status") == "success":
        comm_importance = importance_data.get("so_what", "")
        if comm_importance:
            story.append(Paragraph(f"<b>So What?</b> {comm_importance}", commentary_style))
            story.append(Spacer(1, 5))

        feature_scores = importance_data.get("feature_importance", [])
        if feature_scores:
            plt.figure(figsize=(6, 3))
            sns.set_theme(style="whitegrid")
            
            top_scores = feature_scores[:10]
            cols_names = [x["column"] for x in top_scores]
            scores_val = [x["importance_mean"] for x in top_scores]
            
            sns.barplot(x=scores_val, y=cols_names, palette="mako")
            plt.title("Permutation Feature Importance on Surrogate Gradient Booster", fontsize=9, color="#1e293b", weight="bold")
            plt.xlabel("Permutation Importance Score (Validation Drop)", fontsize=7.5)
            plt.ylabel("Column Name", fontsize=7.5)
            plt.xticks(fontsize=7)
            plt.yticks(fontsize=7)
            plt.tight_layout()

            img_buf = io.BytesIO()
            plt.savefig(img_buf, format='png', dpi=200)
            img_buf.seek(0)
            plt.close()

            story.append(Image(img_buf, width=320, height=160))
            story.append(Spacer(1, 5))
            story.append(Paragraph("<font size='7.5'><i>Figure 5: Permutation importance scores. Higher values signify features with higher predictive weights.</i></font>", body_style))
    else:
        story.append(Paragraph("<i>Not applicable. Feature importance assessment was not run or target variable was omitted.</i>", body_style))
        
    story.append(PageBreak())

    # ------------------ SECTION 9: MULTIVARIATE OUTLIERS ------------------
    story.append(Paragraph("9. Multivariate Anomaly & Outlier Diagnostics", h1_style))
    outlier_data = results.get("outliers", {})
    if outlier_data.get("status") == "success":
        comm_outliers = outlier_data.get("so_what", "")
        if comm_outliers:
            story.append(Paragraph(f"<b>So What?</b> {comm_outliers}", commentary_style))
            story.append(Spacer(1, 5))

        anoms = outlier_data.get("anomalies", [])
        if anoms:
            story.append(Paragraph(f"Isolation Forest identified <b>{outlier_data.get('total_anomalies_found', 0)}</b> anomalous rows (contamination rate: 5%). Showing top anomalous records:", body_style))
            
            # Draw outliers table with NO TRUNCATION
            outliers_table_data = [[
                Paragraph("Index", header_style),
                Paragraph("Anomaly Score", header_style),
                Paragraph("Audited Variables Key Values", header_style)
            ]]

            for a in anoms[:8]:
                # Format all variable values cleanly with no truncation
                val_summary = ", ".join([f"<b>{k}</b>: {v}" for k, v in a["values"].items()])
                outliers_table_data.append([
                    Paragraph(str(a["row_index"]), body_style),
                    Paragraph(f"{a['anomaly_score']:.4f}", body_style),
                    Paragraph(val_summary, body_style)
                ])

            t_outliers = Table(outliers_table_data, colWidths=[50, 90, 360])
            t_outliers.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('PADDING', (0,0), (-1,-1), 5),
                ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG])
            ]))
            story.append(t_outliers)
    else:
        story.append(Paragraph("<i>Not applicable. Isolation Forest diagnostics not executed or failed to run.</i>", body_style))
        
    story.append(Spacer(1, 15))

    # ------------------ SECTION 10: CATEGORICAL FEATURE SUMMARY ------------------
    story.append(Paragraph("10. Dedicated Categorical Feature Summary", h1_style))
    story.append(Spacer(1, 5))
    
    # Pull categorical feature data
    categorical_features = {k: v for k, v in features_dist.items() if v["type"] == "categorical"}
    
    if categorical_features:
        story.append(Paragraph("A comprehensive audit of all high-cardinality and low-cardinality categorical attributes inside the dataset, highlighting frequency biases and distribution coverage.", body_style))
        story.append(Spacer(1, 5))
        
        cat_table_data = [[
            Paragraph("Feature Name", header_style),
            Paragraph("Unique Counts (Cardinality)", header_style),
            Paragraph("Completeness Rate", header_style),
            Paragraph("Top Category (Mode)", header_style),
            Paragraph("Top Category Bias (%)", header_style)
        ]]
        
        for name, meta in categorical_features.items():
            stats = meta.get("stats", {})
            completeness = (1.0 - meta.get("null_rate", 0.0)) * 100
            top_rate = stats.get("top_rate", 0.0) * 100
            
            cat_table_data.append([
                Paragraph(name, body_style),
                Paragraph(f"{meta.get('unique_count', 0)} values", body_style),
                Paragraph(f"{completeness:.1f}% complete", body_style),
                Paragraph(str(stats.get("top_category", "N/A")), body_style),
                Paragraph(f"{top_rate:.1f}% frequency", body_style)
            ])
            
        t_cat = Table(cat_table_data, colWidths=[120, 110, 100, 100, 70])
        t_cat.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('PADDING', (0,0), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG])
        ]))
        story.append(t_cat)
    else:
        story.append(Paragraph("No categorical features were detected in the dataset.", body_style))

    # Build PDF doc
    doc.build(story, canvasmaker=NumberedCanvas)
    return filename
