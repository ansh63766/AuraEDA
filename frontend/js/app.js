// AuraEDA Client Application Logic
(function() {
    // Application State
    const state = {
        activeTab: 'overview',
        datasetInfo: null,       // upload metadata (filename, columns, n_rows, n_columns, dtypes)
        analysisResults: null,   // full stats + LLM comments
        activeFeature: null,     // selected Explorer column
        selectedFeatureChartType: 'kde-hist', // chart type selected for explorer
        charts: {},              // Chart.js instances
        chatHistory: [],         // conversation log
        wranglerSteps: [],       // wrangle steps queue
        splitRatio: 0.7,
        splitResults: null,
        sheetPage: 1,
        sheetLimit: 15,
        sheetSearch: '',
        sheetSortCol: '',
        sheetSortDir: 'ASC',
        datasets: [],            // List of all open datasets
        activeDatasetId: null    // Currently active dataset ID
    };

    // DOM Elements
    const el = {
        app: document.getElementById('app'),
        uploadScreen: document.getElementById('upload-screen'),
        dashboard: document.getElementById('dashboard'),
        dropZone: document.getElementById('drop-zone'),
        fileInput: document.getElementById('csv-file-input'),
        uploadStatus: document.getElementById('upload-status'),
        
        // Advanced parser
        parserToggle: document.getElementById('parser-toggle'),
        parserContent: document.getElementById('parser-content'),
        delimiterSelect: document.getElementById('delimiter-select'),
        quotecharSelect: document.getElementById('quotechar-select'),
        encodingSelect: document.getElementById('encoding-select'),
        
        // Top bar
        datasetTabsContainer: document.getElementById('dataset-tabs-container'),
        btnAddTab: document.getElementById('btn-add-tab'),
        themeToggleBtn: document.getElementById('theme-toggle-btn'),
        targetSelect: document.getElementById('target-col-select'),
        exportHtmlBtn: document.getElementById('export-html-btn'),
        exportPdfBtn: document.getElementById('export-pdf-btn'),
        logoBtn: document.getElementById('logo-btn'),
        
        // Phase 1 Ingestion UI elements
        ingestTabButtons: document.querySelectorAll('.ingest-tab-btn'),
        ingestTabContents: document.querySelectorAll('.ingest-tab-content'),
        samplesGalleryContainer: document.getElementById('samples-gallery-container'),
        
        dbConnectForm: document.getElementById('db-connect-form'),
        dbTypeSelect: document.getElementById('db-type-select'),
        dbHostInput: document.getElementById('db-host-input'),
        dbPortInput: document.getElementById('db-port-input'),
        dbUserInput: document.getElementById('db-user-input'),
        dbPassInput: document.getElementById('db-pass-input'),
        dbNameInput: document.getElementById('db-name-input'),
        dbSqlQueryInput: document.getElementById('db-sql-query-input'),
        dbConnectSubmitBtn: document.getElementById('db-connect-submit-btn'),
        
        urlLoadForm: document.getElementById('url-load-form'),
        apiUrlInput: document.getElementById('api-url-input'),
        apiPathInput: document.getElementById('api-path-input'),
        urlLoadSubmitBtn: document.getElementById('url-load-submit-btn'),
        
        clipboardLoadForm: document.getElementById('clipboard-load-form'),
        clipboardTextArea: document.getElementById('clipboard-text-area'),
        clipboardLoadSubmitBtn: document.getElementById('clipboard-load-submit-btn'),
        
        // Modals
        excelSheetModal: document.getElementById('excel-sheet-modal'),
        excelModalClose: document.getElementById('excel-modal-close'),
        excelSheetsList: document.getElementById('excel-sheets-list'),
        
        sqliteTableModal: document.getElementById('sqlite-table-modal'),
        sqliteModalClose: document.getElementById('sqlite-modal-close'),
        sqliteTablesList: document.getElementById('sqlite-tables-list'),
        
        btnOpenMergeWizard: document.getElementById('btn-open-merge-wizard'),
        mergeWizardModal: document.getElementById('merge-wizard-modal'),
        mergeModalClose: document.getElementById('merge-modal-close'),
        mergeDatasetA: document.getElementById('merge-dataset-a'),
        mergeDatasetB: document.getElementById('merge-dataset-b'),
        mergeTypeSelect: document.getElementById('merge-type-select'),
        mergeJoinFields: document.getElementById('merge-join-fields'),
        mergeJoinHow: document.getElementById('merge-join-how'),
        mergeLeftKey: document.getElementById('merge-left-key'),
        mergeRightKey: document.getElementById('merge-right-key'),
        btnMergeCancel: document.getElementById('btn-merge-cancel'),
        btnMergeSubmit: document.getElementById('btn-merge-submit'),
        
        // Downsample Warning Banner
        downsampleBanner: document.getElementById('downsample-banner'),
        chkRunFullDataset: document.getElementById('chk-run-full-dataset'),
        
        // Floating Shortcuts Help
        helpFloatingContainer: document.getElementById('help-floating-container'),
        helpBtn: document.getElementById('help-btn'),
        helpTooltip: document.getElementById('help-tooltip'),
        
        // Nav
        navItems: document.querySelectorAll('.nav-item'),
        tabContents: document.querySelectorAll('.tab-content'),
        alertsBadgeCount: document.getElementById('alerts-count'),
        loadingOverlay: document.getElementById('loading-overlay'),
        analysisStepText: document.getElementById('analysis-step'),

        // Tab content: Overview
        statRows: document.getElementById('stat-rows'),
        statCols: document.getElementById('stat-cols'),
        statNulls: document.getElementById('stat-nulls'),
        statMemory: document.getElementById('stat-memory'),
        schemaTbody: document.getElementById('schema-tbody'),
        gaugeScoreFill: document.getElementById('gauge-score-fill'),
        gaugeScoreText: document.getElementById('gauge-score-text'),
        healthDescription: document.getElementById('health-description'),

        // Quality Alerts tab
        alertsContainer: document.getElementById('alerts-list-container'),
        alertsLlmText: document.getElementById('alerts-commentary-text'),

        // Missingness tab
        missingTbody: document.getElementById('missing-tbody'),
        missingLlmText: document.getElementById('missing-commentary-text'),
        nullCorrelationChart: document.getElementById('null-correlation-chart'),

        // Feature Explorer tab
        featureSearch: document.getElementById('feature-search'),
        featureListItems: document.getElementById('feature-list-items'),
        noFeatureSelected: document.getElementById('no-feature-selected'),
        featureDetailView: document.getElementById('feature-detail-view'),
        activeFeatureName: document.getElementById('active-feature-name'),
        activeFeatureType: document.getElementById('active-feature-type'),
        featPillMissing: document.getElementById('feat-pill-missing'),
        featPillCard: document.getElementById('feat-pill-card'),
        featureStatsTbody: document.getElementById('feature-stats-tbody'),
        featureDistributionChart: document.getElementById('feature-distribution-chart'),
        featureCommentaryText: document.getElementById('feature-commentary-text'),

        // Correlations tab
        correlationsLlmText: document.getElementById('correlations-commentary-text'),
        corrPairsTbody: document.getElementById('corr-pairs-tbody'),
        vifTbody: document.getElementById('vif-tbody'),
        correlationHeatmapContainer: document.getElementById('correlation-heatmap-container'),

        // Leakage & Drift tab
        targetUnselectedPanel: document.getElementById('target-unselected-panel'),
        targetSelectedPanel: document.getElementById('target-selected-panel'),
        activeTargetDisplay: document.getElementById('active-target-display'),
        targetTypeDisplay: document.getElementById('target-type-display'),
        leakageCommentaryText: document.getElementById('leakage-commentary-text'),
        leakageTbody: document.getElementById('leakage-tbody'),
        driftCommentaryText: document.getElementById('drift-commentary-text'),
        driftTbody: document.getElementById('drift-tbody'),
        driftChartContainer: document.getElementById('drift-chart-container'),

        // Split & Drift tab
        splitRatioRange: document.getElementById('split-ratio-range'),
        splitRatioVal: document.getElementById('split-ratio-val'),
        runSplitBtn: document.getElementById('run-split-btn'),
        dummyBaselineScore: document.getElementById('dummy-baseline-score'),
        modelBaselineScore: document.getElementById('model-baseline-score'),
        splitTrainRows: document.getElementById('split-train-rows'),
        splitTestRows: document.getElementById('split-test-rows'),
        splitTrainNulls: document.getElementById('split-train-nulls'),
        splitTestNulls: document.getElementById('split-test-nulls'),
        driftAuditTbody: document.getElementById('drift-audit-tbody'),
        splitCompareColSelect: document.getElementById('split-compare-col-select'),
        splitCompareDistributionChart: document.getElementById('split-compare-distribution-chart'),

        // Data Wrangler tab
        wrangleColSelect: document.getElementById('wrangle-col-select'),
        wrangleActionSelect: document.getElementById('wrangle-action-select'),
        wrangleStrategySelect: document.getElementById('wrangle-strategy-select'),
        wrangleStrategyGroup: document.getElementById('wrangle-strategy-group'),
        clearWrangleBtn: document.getElementById('clear-wrangle-btn'),
        addWrangleBtn: document.getElementById('add-wrangle-btn'),
        appliedStepsList: document.getElementById('applied-steps-list'),
        executeWrangleBtn: document.getElementById('execute-wrangle-btn'),
        wrangleBeforeRows: document.getElementById('wrangle-before-rows'),
        wrangleAfterRows: document.getElementById('wrangle-after-rows'),
        wrangleBeforeCols: document.getElementById('wrangle-before-cols'),
        wrangleAfterCols: document.getElementById('wrangle-after-cols'),
        wrangleBeforeNulls: document.getElementById('wrangle-before-nulls'),
        wrangleAfterNulls: document.getElementById('wrangle-after-nulls'),
        wrangleBeforeScore: document.getElementById('wrangle-before-score'),
        wrangleAfterScore: document.getElementById('wrangle-after-score'),
        wrangleDownloadCsvBtn: document.getElementById('wrangle-download-csv-btn'),
        wrangleDownloadPklBtn: document.getElementById('wrangle-download-pkl-btn'),
        wranglePipelineCodeBlock: document.getElementById('wrangle-pipeline-code-block'),
        copyPipelineCodeBtn: document.getElementById('copy-pipeline-code-btn'),

        // Importance & PCA tab
        pcaVarianceDetails: document.getElementById('pca-variance-details'),
        pcaScatterChart: document.getElementById('pca-scatter-chart'),
        pcaColsUsedBox: document.getElementById('pca-cols-used-box'),
        importanceBarChart: document.getElementById('importance-bar-chart'),

        // Advanced EDA tab
        subtabBtnBivariate: document.getElementById('subtab-btn-bivariate'),
        subtabBtnDatetime: document.getElementById('subtab-btn-datetime'),
        subtabBtnText: document.getElementById('subtab-btn-text'),
        subtabBtnOutliers: document.getElementById('subtab-btn-outliers'),
        paneAdvancedBivariate: document.getElementById('pane-advanced-bivariate'),
        paneAdvancedDatetime: document.getElementById('pane-advanced-datetime'),
        paneAdvancedText: document.getElementById('pane-advanced-text'),
        paneAdvancedOutliers: document.getElementById('pane-advanced-outliers'),
        
        bivariateXSelect: document.getElementById('bivariate-x-select'),
        bivariateYSelect: document.getElementById('bivariate-y-select'),
        bivariateCanvasChart: document.getElementById('bivariate-canvas-chart'),
        
        noDatetimeAlert: document.getElementById('no-datetime-alert'),
        datetimePanelWrapper: document.getElementById('datetime-panel-wrapper'),
        datetimeColSelect: document.getElementById('datetime-col-select'),
        datetimeRangeText: document.getElementById('datetime-range-text'),
        datetimeTimelineChart: document.getElementById('datetime-timeline-chart'),
        datetimeHourlyChart: document.getElementById('datetime-hourly-chart'),
        datetimeWeeklyChart: document.getElementById('datetime-weekly-chart'),
        datetimeMonthlyChart: document.getElementById('datetime-monthly-chart'),
        
        noTextAlert: document.getElementById('no-text-alert'),
        textPanelWrapper: document.getElementById('text-panel-wrapper'),
        textColSelect: document.getElementById('text-col-select'),
        textStatsTbody: document.getElementById('text-stats-tbody'),
        textUnigramChart: document.getElementById('text-unigram-chart'),
        textBigramChart: document.getElementById('text-bigram-chart'),
        
        noOutliersAlert: document.getElementById('no-outliers-alert'),
        outliersPanelWrapper: document.getElementById('outliers-panel-wrapper'),
        outliersContamText: document.getElementById('outliers-contam-text'),
        outliersTotalFound: document.getElementById('outliers-total-found'),
        outliersAllThree: document.getElementById('outliers-all-three'),
        outliersAnyTwo: document.getElementById('outliers-any-two'),
        outliersExactlyOne: document.getElementById('outliers-exactly-one'),
        outliersTbodyList: document.getElementById('outliers-tbody-list'),
        
        // GDPR selectors
        gdprPiiTbody: document.getElementById('gdpr-pii-tbody'),
        gdprPiiCount: document.getElementById('gdpr-pii-count'),
        
        // Benford selectors
        benfordColSelect: document.getElementById('benford-col-select'),
        
        // RAM advisor selectors
        ramSavingsBadge: document.getElementById('ram-savings-badge'),
        ramOptTbody: document.getElementById('ram-opt-tbody'),
        btnApplyAllDowncasts: document.getElementById('btn-apply-all-downcasts'),

        // Data Sheet tab
        sheetSearchInput: document.getElementById('sheet-search-input'),
        sheetMetaInfo: document.getElementById('sheet-meta-info'),
        spreadsheetTable: document.getElementById('spreadsheet-table'),
        spreadsheetThead: document.getElementById('spreadsheet-thead'),
        spreadsheetTbody: document.getElementById('spreadsheet-tbody'),
        sheetPrevBtn: document.getElementById('sheet-prev-btn'),
        sheetPageIndicator: document.getElementById('sheet-page-indicator'),
        sheetNextBtn: document.getElementById('sheet-next-btn'),

        // SQL console tab
        sqlQueryInput: document.getElementById('sql-query-input'),
        runQueryBtn: document.getElementById('run-query-btn'),
        queryMetaInfo: document.getElementById('query-meta-info'),
        sqlErrorOutput: document.getElementById('sql-error-output'),
        sqlResultsTable: document.getElementById('sql-results-table'),
        sqlResultsThead: document.getElementById('sql-results-thead'),
        sqlResultsTbody: document.getElementById('sql-results-tbody'),

        // Chat tab
        chatMessagesArea: document.getElementById('chat-messages-area'),
        chatUserInput: document.getElementById('chat-user-input'),
        chatSendBtn: document.getElementById('chat-send-btn'),
        chatChips: document.querySelectorAll('.chat-chips .chat-chip-btn'),

        // Settings Modal
        settingsToggleBtn: document.getElementById('settings-toggle-btn'),
        settingsModal: document.getElementById('settings-modal'),
        settingsCloseBtn: document.getElementById('settings-close-btn'),
        settingsCancelBtn: document.getElementById('settings-cancel-btn'),
        settingsSaveBtn: document.getElementById('settings-save-btn'),
        
        // Phase 3 elements
        featureChartTypeSelect: document.getElementById('feature-chart-type-select'),
        featurePlotlyChart: document.getElementById('feature-detail-plotly-chart'),
        correlationMethodSelect: document.getElementById('correlation-method-select'),
        chkFilterSignificance: document.getElementById('chk-filter-significance'),
        correlationPlotlyHeatmap: document.getElementById('correlation-plotly-heatmap'),
        bivariateZSelect: document.getElementById('bivariate-z-select'),
        bivariatePlotlyChart: document.getElementById('bivariate-plotly-chart'),
        hypTestType: document.getElementById('hyp-test-type'),
        hypCol1: document.getElementById('hyp-col1'),
        hypCol1Label: document.getElementById('hyp-col1-label'),
        hypCol1Group: document.getElementById('hyp-col1-group'),
        hypCol2: document.getElementById('hyp-col2'),
        hypCol2Label: document.getElementById('hyp-col2-label'),
        hypCol2Group: document.getElementById('hyp-col2-group'),
        hypPopMean: document.getElementById('hyp-popmean'),
        hypPopMeanGroup: document.getElementById('hyp-popmean-group'),
        hypConfidence: document.getElementById('hyp-confidence'),
        btnRunHypTest: document.getElementById('btn-run-hyp-test'),
        hypResultsEmpty: document.getElementById('hyp-results-empty'),
        hypResultsContent: document.getElementById('hyp-results-content'),
        hypResStat: document.getElementById('hyp-res-stat'),
        hypResPvalue: document.getElementById('hyp-res-pvalue'),
        hypResInterpretation: document.getElementById('hyp-res-interpretation'),
        hypResPower: document.getElementById('hyp-res-power'),
        hypPlotlyChart: document.getElementById('hyp-plotly-chart')
    };

    // Initialize Event Listeners
    function init() {
        // Ingestion tab switches
        el.ingestTabButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                el.ingestTabButtons.forEach(b => b.classList.remove('active'));
                el.ingestTabContents.forEach(c => c.classList.add('hidden'));
                btn.classList.add('active');
                
                const targetTab = btn.getAttribute('data-ingest-tab');
                document.getElementById(`ingest-tab-${targetTab}`).classList.remove('hidden');
                
                if (targetTab === 'sample-gallery') {
                    loadSampleGallery();
                }
            });
        });

        // Database connect submit
        el.dbConnectSubmitBtn.addEventListener('click', submitDatabaseConnection);
        
        // REST API connect submit
        el.urlLoadSubmitBtn.addEventListener('click', submitRestApiConnection);
        
        // Clipboard load submit
        el.clipboardLoadSubmitBtn.addEventListener('click', submitClipboardConnection);

        // Modal closers
        el.excelModalClose.addEventListener('click', () => el.excelSheetModal.classList.add('hidden'));
        el.sqliteModalClose.addEventListener('click', () => el.sqliteTableModal.classList.add('hidden'));
        el.mergeModalClose.addEventListener('click', () => el.mergeWizardModal.classList.add('hidden'));
        el.btnMergeCancel.addEventListener('click', () => el.mergeWizardModal.classList.add('hidden'));
        
        // Open Merge Wizard dialog
        el.btnOpenMergeWizard.addEventListener('click', openMergeWizard);
        
        // Submit Merge Wizard execution
        el.btnMergeSubmit.addEventListener('click', submitMergeWizard);
        
        // Dynamically toggle keys for join vs stack
        el.mergeTypeSelect.addEventListener('change', () => {
            if (el.mergeTypeSelect.value === 'stack') {
                el.mergeJoinFields.classList.add('hidden');
            } else {
                el.mergeJoinFields.classList.remove('hidden');
            }
        });

        // Trigger updates when Dataset A is selected in merge
        el.mergeDatasetA.addEventListener('change', populateMergeWizardKeys);
        el.mergeDatasetB.addEventListener('change', populateMergeWizardKeys);

        // Drag Drop Zone
        el.dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            el.dropZone.classList.add('dragover');
        });
        el.dropZone.addEventListener('dragleave', () => {
            el.dropZone.classList.remove('dragover');
        });
        el.dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            el.dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                handleFileUpload(e.dataTransfer.files[0]);
            }
        });
        el.dropZone.addEventListener('click', () => el.fileInput.click());
        el.fileInput.addEventListener('change', () => {
            if (el.fileInput.files.length > 0) {
                handleFileUpload(el.fileInput.files[0]);
            }
        });

        // Parser settings toggle
        el.parserToggle.addEventListener('click', () => {
            el.parserContent.classList.toggle('open');
            el.parserToggle.querySelector('.chevron').classList.toggle('rotate');
        });

        // RAM Downcasts Listener
        if (el.btnApplyAllDowncasts) {
            el.btnApplyAllDowncasts.addEventListener('click', applyAllDowncasts);
        }

        // Tab selection
        el.navItems.forEach(item => {
            item.addEventListener('click', () => {
                switchTab(item.getAttribute('data-tab'));
            });
        });

        // Target Variable select trigger
        el.targetSelect.addEventListener('change', () => {
            const target = el.targetSelect.value;
            triggerAnalysis(target);
        });

        // Report Exports
        el.exportHtmlBtn.addEventListener('click', () => {
            const target = el.targetSelect.value;
            window.open(`/api/export/html?target_column=${encodeURIComponent(target)}`, '_blank');
        });
        el.exportPdfBtn.addEventListener('click', () => {
            const target = el.targetSelect.value;
            window.open(`/api/export/pdf?target_column=${encodeURIComponent(target)}`, '_blank');
        });

        // Logo return
        el.logoBtn.addEventListener('click', () => {
            el.app.className = 'initial-mode';
            el.uploadScreen.classList.remove('hidden');
            el.dashboard.classList.add('hidden');
        });

        // Feature search list
        el.featureSearch.addEventListener('input', () => {
            renderFeatureList(el.featureSearch.value);
        });

        // SQL execution
        el.runQueryBtn.addEventListener('click', runSqlQueryConsole);

        // Chat triggers
        el.chatSendBtn.addEventListener('click', sendChatMessage);
        el.chatUserInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendChatMessage();
        });
        
        const chatChipsContainer = document.querySelector('.chat-chips');
        if (chatChipsContainer) {
            chatChipsContainer.addEventListener('click', (e) => {
                const chip = e.target.closest('.chat-chip-btn');
                if (chip) {
                    el.chatUserInput.value = chip.innerText;
                    sendChatMessage();
                }
            });
        }

        // Split & Drift tab triggers
        el.splitRatioRange.addEventListener('input', () => {
            const val = el.splitRatioRange.value;
            el.splitRatioVal.innerText = `${val}%`;
            state.splitRatio = val / 100.0;
        });
        el.runSplitBtn.addEventListener('click', runSplitDiagnostics);
        el.splitCompareColSelect.addEventListener('change', drawSplitCompareChart);

        // Wrangler tab triggers
        el.wrangleActionSelect.addEventListener('change', handleWrangleActionChange);
        el.addWrangleBtn.addEventListener('click', addWrangleStep);
        el.clearWrangleBtn.addEventListener('click', clearWranglePipeline);
        el.executeWrangleBtn.addEventListener('click', executeWranglePipeline);
        el.wrangleDownloadCsvBtn.addEventListener('click', () => {
            window.open('/api/export/csv', '_blank');
        });
        el.wrangleDownloadPklBtn.addEventListener('click', () => {
            window.open('/api/export/pipeline', '_blank');
        });
        el.copyPipelineCodeBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(el.wranglePipelineCodeBlock.innerText);
            showStatusMessage("Code copied to clipboard!", "success");
        });

        // Settings triggers
        if (el.settingsToggleBtn) {
            el.settingsToggleBtn.addEventListener('click', () => {
                fetch('/api/config')
                    .then(res => res.json())
                    .then(data => {
                        const flags = data.features;
                        for (const key in flags) {
                            const cb = document.getElementById(`flag-${key}`);
                            if (cb) cb.checked = flags[key];
                        }
                        el.settingsModal.classList.remove('hidden');
                    })
                    .catch(err => {
                        showStatusMessage("Failed to fetch settings from backend", "error");
                    });
            });
        }

        if (el.settingsCloseBtn) el.settingsCloseBtn.addEventListener('click', () => el.settingsModal.classList.add('hidden'));
        if (el.settingsCancelBtn) el.settingsCancelBtn.addEventListener('click', () => el.settingsModal.classList.add('hidden'));
        if (el.settingsSaveBtn) {
            el.settingsSaveBtn.addEventListener('click', () => {
                const keys = ["smote", "mcar_test", "language_detection", "interaction_effects", "partial_correlation", "tfidf_nlp"];
                const features = {};
                keys.forEach(k => {
                    const cb = document.getElementById(`flag-${k}`);
                    if (cb) features[k] = cb.checked;
                });
                
                fetch('/api/config/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ features })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showStatusMessage("Global settings saved successfully!", "success");
                        el.settingsModal.classList.add('hidden');
                        if (state.datasetInfo) {
                            triggerAnalysis(el.targetSelect.value);
                        }
                    }
                })
                .catch(err => {
                    showStatusMessage("Failed to update config flags", "error");
                });
            });
        }

        // Delegated "Apply in Wrangler" listener
        el.chatMessagesArea.addEventListener('click', (e) => {
            const btn = e.target.closest('.apply-wrangler-btn');
            if (btn) {
                try {
                    const payload = JSON.parse(btn.getAttribute('data-action'));
                    const steps = Array.isArray(payload) ? payload : [payload];
                    steps.forEach(step => {
                        if (step.column && step.action) {
                            state.wranglerSteps.push({
                                column: step.column,
                                action: step.action,
                                strategy: step.strategy || null
                            });
                        }
                    });
                    renderWranglerSteps();
                    switchTab('wrangler');
                    showStatusMessage("Applied suggestion to Wrangler queue!", "success");
                } catch (err) {
                    console.error("Failed to parse apply in wrangler payload:", err);
                    showStatusMessage("Failed to load transformations: invalid action format.", "error");
                }
            }

            // Copy feedback trigger
            const copyBtn = e.target.closest('.copy-btn');
            if (copyBtn) {
                const parent = copyBtn.closest('.msg-agent');
                const text = parent.querySelector('p').innerText;
                navigator.clipboard.writeText(text);
                const originalText = copyBtn.innerHTML;
                copyBtn.innerHTML = '📋 Copied!';
                setTimeout(() => { copyBtn.innerHTML = originalText; }, 1500);
            }

            // Save feedback trigger
            const saveBtn = e.target.closest('.save-btn');
            if (saveBtn) {
                const parent = saveBtn.closest('.msg-agent');
                const text = parent.querySelector('p').innerText;
                if (!state.savedReportNotes) state.savedReportNotes = [];
                state.savedReportNotes.push(text);
                const originalText = saveBtn.innerHTML;
                saveBtn.innerHTML = '💾 Saved!';
                setTimeout(() => { saveBtn.innerHTML = originalText; }, 1500);
                showStatusMessage("Saved chat commentary to active report queue!", "success");
            }
        });

        // Advanced EDA sub-panes
        el.subtabBtnBivariate.addEventListener('click', () => switchAdvancedPane('bivariate'));
        el.subtabBtnDatetime.addEventListener('click', () => switchAdvancedPane('datetime'));
        el.subtabBtnText.addEventListener('click', () => switchAdvancedPane('text'));
        el.subtabBtnOutliers.addEventListener('click', () => switchAdvancedPane('outliers'));

        el.bivariateXSelect.addEventListener('change', renderBivariateChart);
        el.bivariateYSelect.addEventListener('change', renderBivariateChart);
        el.datetimeColSelect.addEventListener('change', renderDatetimeCharts);
        el.textColSelect.addEventListener('change', renderTextCharts);

        // Data sheet pagination & search
        el.sheetPrevBtn.addEventListener('click', () => {
            if (state.sheetPage > 1) {
                state.sheetPage--;
                loadSpreadsheetData();
            }
        });
        el.sheetNextBtn.addEventListener('click', () => {
            state.sheetPage++;
            loadSpreadsheetData();
        });
        el.sheetSearchInput.addEventListener('input', debounce(() => {
            state.sheetPage = 1;
            state.sheetSearch = el.sheetSearchInput.value;
            loadSpreadsheetData();
        }, 300));

        // Add Tab Button selector
        el.btnAddTab.addEventListener('click', () => {
            el.fileInput.click();
        });

        // Theme Toggle
        if (localStorage.getItem('theme') === 'light') {
            document.body.classList.add('light-theme');
        }
        el.themeToggleBtn.addEventListener('click', () => {
            document.body.classList.toggle('light-theme');
            const theme = document.body.classList.contains('light-theme') ? 'light' : 'dark';
            localStorage.setItem('theme', theme);
        });

        // Downsample run full dataset anyway listener
        el.chkRunFullDataset.addEventListener('change', () => {
            const enabled = !el.chkRunFullDataset.checked;
            toggleDownsampling(state.activeDatasetId, enabled);
        });

        // Floating Shortcuts Help
        el.helpBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            el.helpTooltip.classList.toggle('hidden');
        });
        document.addEventListener('click', () => {
            el.helpTooltip.classList.add('hidden');
        });

        // Global Keyboard Shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
                e.preventDefault();
                switchTab('chat');
                setTimeout(() => el.chatUserInput.focus(), 100);
            }
            if (e.ctrlKey && e.key.toLowerCase() === 'z') {
                if (state.datasetInfo) {
                    e.preventDefault();
                    triggerUndo();
                }
            }
            if (e.ctrlKey && e.key.toLowerCase() === 'y') {
                if (state.datasetInfo) {
                    e.preventDefault();
                    triggerRedo();
            }
        });

        // Phase 3 Event Listeners
        if (el.featureChartTypeSelect) {
            el.featureChartTypeSelect.addEventListener('change', () => {
                state.selectedFeatureChartType = el.featureChartTypeSelect.value;
                if (state.activeFeature) {
                    // Re-render chart for the active feature
                    const results = state.analysisResults;
                    const detail = results.results.distributions.features[state.activeFeature];
                    if (detail) {
                        drawFeatureDistributionChart(state.activeFeature, detail);
                    }
                }
            });
        }
        if (el.correlationMethodSelect) {
            el.correlationMethodSelect.addEventListener('change', drawPearsonHeatmap);
        }
        if (el.chkFilterSignificance) {
            el.chkFilterSignificance.addEventListener('change', drawPearsonHeatmap);
        }
        if (el.bivariateZSelect) {
            el.bivariateZSelect.addEventListener('change', renderBivariateChart);
        }
        if (el.hypTestType) {
            el.hypTestType.addEventListener('change', updateHypothesisFields);
        }
        if (el.btnRunHypTest) {
            el.btnRunHypTest.addEventListener('click', runHypothesisTestInCenter);
        }
    }

    // Helper functions
    function switchTab(tabName) {
        state.activeTab = tabName;
        el.navItems.forEach(item => {
            if (item.getAttribute('data-tab') === tabName) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
        el.tabContents.forEach(content => {
            if (content.id === `tab-${tabName}`) {
                content.classList.remove('hidden');
            } else {
                content.classList.add('hidden');
            }
        });

        // Trigger adjustments if needed
        if (tabName === 'datasheet') {
            loadSpreadsheetData();
        } else if (tabName === 'benfords') {
            drawBenfordPlot();
        } else if (tabName === 'hypothesis') {
            updateHypothesisFields();
        }
    }

    function destroyChart(name) {
        if (state.charts[name]) {
            state.charts[name].destroy();
            delete state.charts[name];
        }
    }

    function showStatusMessage(msg, type) {
        el.uploadStatus.innerText = msg;
        el.uploadStatus.className = `status-msg ${type}`;
        el.uploadStatus.classList.remove('hidden');
        setTimeout(() => el.uploadStatus.classList.add('hidden'), 5000);
    }

    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    function toggleDownsampling(datasetId, enabled) {
        showLoading(enabled ? "Downsampling dataset view..." : "Processing full dataset...");
        const formData = new FormData();
        formData.append('dataset_id', datasetId);
        formData.append('enabled', enabled);

        fetch('/api/datasets/toggle-downsample', {
            method: 'POST',
            body: formData
        })
        .then(res => {
            if (!res.ok) throw new Error("Failed to toggle downsampling");
            return res.json();
        })
        .then(data => {
            state.analysisResults = data.analysis;
            state.datasetInfo.is_downsampled = data.is_downsampled;
            state.datasetInfo.downsample_enabled = enabled;
            
            // update tabs view
            const ds = state.datasets.find(d => d.id === datasetId);
            if (ds) {
                ds.is_downsampled = data.is_downsampled;
                ds.downsample_enabled = enabled;
            }
            renderDatasetTabs();
            
            // update warning banner
            if (data.is_downsampled) {
                el.downsampleBanner.classList.remove('hidden');
                el.chkRunFullDataset.checked = false;
            } else {
                el.downsampleBanner.classList.add('hidden');
                el.chkRunFullDataset.checked = true;
            }

            hideLoading();
            renderDashboard();
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    function triggerUndo() {
        showLoading("Undoing last data transformation...");
        fetch('/api/datasets/undo', {
            method: 'POST',
            headers: {
                'X-Dataset-Id': state.activeDatasetId
            }
        })
        .then(res => {
            if (!res.ok) return res.json().then(e => { throw new Error(e.detail || "Undo failed") });
            return res.json();
        })
        .then(data => {
            state.analysisResults = data.analysis;
            state.wranglerSteps = data.wrangle_steps;
            hideLoading();
            renderDashboard();
            showStatusMessage("Undone successfully!", "success");
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    function triggerRedo() {
        showLoading("Redoing data transformation...");
        fetch('/api/datasets/redo', {
            method: 'POST',
            headers: {
                'X-Dataset-Id': state.activeDatasetId
            }
        })
        .then(res => {
            if (!res.ok) return res.json().then(e => { throw new Error(e.detail || "Redo failed") });
            return res.json();
        })
        .then(data => {
            state.analysisResults = data.analysis;
            state.wranglerSteps = data.wrangle_steps;
            hideLoading();
            renderDashboard();
            showStatusMessage("Redone successfully!", "success");
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    function switchDataset(datasetId) {
        showLoading("Switching active dataset workspace...");
        
        const form = new FormData();
        form.append('dataset_id', datasetId);
        
        fetch('/api/datasets/active', {
            method: 'POST',
            body: form
        })
        .then(res => {
            if (!res.ok) throw new Error("Failed to switch active dataset");
            return res.json();
        })
        .then(data => {
            state.activeDatasetId = datasetId;
            return fetch('/api/datasets');
        })
        .then(res => res.json())
        .then(data => {
            state.datasets = data.datasets;
            triggerAnalysis();
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    function renderDatasetTabs() {
        if (!el.datasetTabsContainer) return;
        el.datasetTabsContainer.innerHTML = '';
        
        state.datasets.forEach(ds => {
            const tab = document.createElement('div');
            tab.className = `dataset-tab ${ds.id === state.activeDatasetId ? 'active' : ''}`;
            tab.setAttribute('data-id', ds.id);
            
            const nameSpan = document.createElement('span');
            nameSpan.className = 'tab-name';
            nameSpan.innerText = ds.filename;
            tab.appendChild(nameSpan);
            
            const badgeSpan = document.createElement('span');
            badgeSpan.className = 'tab-badge';
            badgeSpan.innerText = `${ds.n_rows} x ${ds.n_columns}`;
            tab.appendChild(badgeSpan);
            
            const closeSpan = document.createElement('span');
            closeSpan.className = 'tab-close';
            closeSpan.innerHTML = '&times;';
            closeSpan.title = "Close Dataset";
            closeSpan.addEventListener('click', (e) => {
                e.stopPropagation();
                closeDataset(ds.id);
            });
            tab.appendChild(closeSpan);
            
            tab.addEventListener('click', () => {
                if (ds.id !== state.activeDatasetId) {
                    switchDataset(ds.id);
                }
            });
            
            el.datasetTabsContainer.appendChild(tab);
        });
    }

    function closeDataset(datasetId) {
        showLoading("Closing dataset workspace...");
        fetch(`/api/datasets/${datasetId}`, {
            method: 'DELETE'
        })
        .then(res => {
            if (!res.ok) throw new Error("Failed to close dataset");
            return res.json();
        })
        .then(data => {
            state.datasets = state.datasets.filter(d => d.id !== datasetId);
            
            if (state.datasets.length === 0) {
                state.activeDatasetId = null;
                state.datasetInfo = null;
                state.analysisResults = null;
                
                el.app.className = 'initial-mode';
                el.uploadScreen.classList.remove('hidden');
                el.dashboard.classList.add('hidden');
                el.downsampleBanner.classList.add('hidden');
                
                hideLoading();
            } else {
                switchDataset(data.active_id);
            }
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    // File Upload handler
    function handleFileUpload(file, sheetName = null, tableName = null) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('delimiter', el.delimiterSelect.value);
        formData.append('quotechar', el.quotecharSelect.value);
        formData.append('encoding', el.encodingSelect.value);
        if (sheetName) formData.append('sheet_name', sheetName);
        if (tableName) formData.append('table_name', tableName);

        showLoading("Uploading and parsing dataset...");
        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(res => {
            if (!res.ok) return res.json().then(e => { throw new Error(e.detail || "Upload failed") });
            return res.json();
        })
        .then(data => {
            // Excel sheet selector modal
            if (data.requires_sheet_select) {
                hideLoading();
                el.excelSheetsList.innerHTML = '';
                data.sheets.forEach(sh => {
                    const li = document.createElement('li');
                    li.className = 'modal-select-item';
                    li.innerText = sh;
                    li.addEventListener('click', () => {
                        el.excelSheetModal.classList.add('hidden');
                        handleFileUpload(file, sh, null);
                    });
                    el.excelSheetsList.appendChild(li);
                });
                el.excelSheetModal.classList.remove('hidden');
                return;
            }

            // SQLite table selector modal
            if (data.requires_table_select) {
                hideLoading();
                el.sqliteTablesList.innerHTML = '';
                data.tables.forEach(tb => {
                    const li = document.createElement('li');
                    li.className = 'modal-select-item';
                    li.innerText = tb;
                    li.addEventListener('click', () => {
                        el.sqliteTableModal.classList.add('hidden');
                        handleFileUpload(file, null, tb);
                    });
                    el.sqliteTablesList.appendChild(li);
                });
                el.sqliteTableModal.classList.remove('hidden');
                return;
            }

            // Add to active datasets list if not already present
            if (!state.datasets.find(d => d.id === data.dataset_id)) {
                state.datasets.push({
                    id: data.dataset_id,
                    filename: data.filename,
                    n_rows: data.n_rows,
                    n_columns: data.n_columns,
                    is_downsampled: data.is_downsampled,
                    downsample_enabled: data.downsample_enabled
                });
            }
            state.activeDatasetId = data.dataset_id;
            state.datasetInfo = data;
            state.wranglerSteps = [];
            state.splitResults = null;
            
            // Render the top tabs
            renderDatasetTabs();
            
            // Populate Target dropdown
            el.targetSelect.innerHTML = '<option value="">-- Select Target (Enables Leakage & Drift) --</option>';
            el.splitCompareColSelect.innerHTML = '<option value="">-- Select Feature --</option>';
            el.wrangleColSelect.innerHTML = '';
            el.bivariateXSelect.innerHTML = '';
            el.bivariateYSelect.innerHTML = '';
            el.datetimeColSelect.innerHTML = '';
            el.textColSelect.innerHTML = '';

            data.columns.forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.innerText = col;
                el.targetSelect.appendChild(opt.cloneNode(true));
                el.splitCompareColSelect.appendChild(opt.cloneNode(true));
                el.wrangleColSelect.appendChild(opt.cloneNode(true));
                el.bivariateXSelect.appendChild(opt.cloneNode(true));
                el.bivariateYSelect.appendChild(opt.cloneNode(true));
            });

            // Transition Screen
            el.app.className = 'dashboard-mode';
            el.uploadScreen.classList.add('hidden');
            el.dashboard.classList.remove('hidden');

            // Trigger full analytical explore
            triggerAnalysis();
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    function showLoading(step) {
        el.analysisStepText.innerText = step;
        el.loadingOverlay.classList.remove('hidden');
    }

    function hideLoading() {
        el.loadingOverlay.classList.add('hidden');
    }

    // Trigger backend orchestrator analysis
    function triggerAnalysis(target = '') {
        showLoading("Analyzing variables and building report...");
        
        const form = new FormData();
        if (target) form.append('target_column', target);

        fetch('/api/analyze', {
            method: 'POST',
            body: form,
            headers: {
                'X-Dataset-Id': state.activeDatasetId
            }
        })
        .then(res => {
            if (!res.ok) throw new Error("Analysis failed");
            return res.json();
        })
        .then(data => {
            state.analysisResults = data;
            
            // Sync datasetInfo details dynamically
            const activeDs = state.datasets.find(d => d.id === state.activeDatasetId);
            if (activeDs) {
                state.datasetInfo = {
                    dataset_id: state.activeDatasetId,
                    filename: activeDs.filename,
                    n_rows: data.dataset_summary.n_rows,
                    n_columns: data.dataset_summary.n_columns,
                    columns: data.dataset_summary.columns,
                    dtypes: data.dataset_summary.dtypes,
                    is_downsampled: activeDs.is_downsampled,
                    downsample_enabled: activeDs.downsample_enabled
                };
            }

            // Populate Target dropdown
            el.targetSelect.innerHTML = '<option value="">-- Select Target (Enables Leakage & Drift) --</option>';
            el.splitCompareColSelect.innerHTML = '<option value="">-- Select Feature --</option>';
            el.wrangleColSelect.innerHTML = '';
            el.bivariateXSelect.innerHTML = '';
            el.bivariateYSelect.innerHTML = '';
            el.bivariateZSelect.innerHTML = '<option value="">-- None (2D Plot) --</option>';
            el.datetimeColSelect.innerHTML = '';
            el.textColSelect.innerHTML = '';

            state.datasetInfo.columns.forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.innerText = col;
                el.targetSelect.appendChild(opt.cloneNode(true));
                el.splitCompareColSelect.appendChild(opt.cloneNode(true));
                el.wrangleColSelect.appendChild(opt.cloneNode(true));
                el.bivariateXSelect.appendChild(opt.cloneNode(true));
                el.bivariateYSelect.appendChild(opt.cloneNode(true));
                el.bivariateZSelect.appendChild(opt.cloneNode(true));
            });
            
            updateHypothesisFields();
            
            // Restore target variable value if selected
            if (data.results && data.results.importance && data.results.importance.target_column) {
                el.targetSelect.value = data.results.importance.target_column;
            } else {
                el.targetSelect.value = '';
            }

            // Downsample warning banner trigger
            if (state.datasetInfo.is_downsampled) {
                el.downsampleBanner.classList.remove('hidden');
                el.chkRunFullDataset.checked = false;
            } else {
                el.downsampleBanner.classList.add('hidden');
                el.chkRunFullDataset.checked = true;
            }

            hideLoading();
            renderDashboard();
            renderDatasetTabs();
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    // Render Dashboard Panes
    function renderDashboard() {
        const info = state.datasetInfo;
        const results = state.analysisResults;

        if (!info || !results) return;

        // Overview Stats
        el.statRows.innerText = results.dataset_summary.n_rows.toLocaleString();
        el.statCols.innerText = results.dataset_summary.n_columns.toLocaleString();
        el.statNulls.innerText = results.results.missingness.total_missing_cells.toLocaleString();
        
        const bytes = results.dataset_summary.size_bytes;
        el.statMemory.innerText = bytes < 1024*1024 ? 
            `${(bytes / 1024).toFixed(1)} KB` : 
            `${(bytes / (1024*1024)).toFixed(2)} MB`;

        // Render Schema list
        el.schemaTbody.innerHTML = '';
        results.dataset_summary.columns.forEach(col => {
            const tr = document.createElement('tr');
            const dtype = results.dataset_summary.dtypes[col];
            
            // Check if column has any missing data
            const missingInfo = results.results.missingness.summary.find(s => s.column === col);
            const nullRate = missingInfo ? missingInfo.missing_rate : 0.0;
            const imputeStatus = nullRate > 0 ? 
                `<span class="text-warning">Missing (${(nullRate*100).toFixed(1)}%)</span>` : 
                '<span class="text-success">Clean (100%)</span>';

            // Find alerts for this column
            const alerts = results.results.alerts.alerts.filter(a => a.column === col);
            let alertPill = '<span class="badge badge-success">Good</span>';
            if (alerts.some(a => a.severity === 'high')) {
                alertPill = '<span class="badge badge-danger">High Alert</span>';
            } else if (alerts.some(a => a.severity === 'medium')) {
                alertPill = '<span class="badge badge-warning">Medium Alert</span>';
            }

            // Inferred semantic type
            const semTypes = results.results.alerts.semantic_types || {};
            const semType = semTypes[col] || (dtype.startsWith('int') || dtype.startsWith('float') ? 'Numeric' : 'Categorical');

            tr.innerHTML = `
                <td><strong>${col}</strong></td>
                <td><span class="code">${dtype}</span></td>
                <td>
                    <select class="input-select semantic-cast-select" data-col="${col}" style="font-size:11px; padding: 2px 6px; background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-200); border-radius: 4px; outline:none;">
                        <option value="Numeric" ${semType === 'Numeric' ? 'selected' : ''}>Numeric</option>
                        <option value="Categorical" ${semType === 'Categorical' ? 'selected' : ''}>Categorical</option>
                        <option value="Email" ${semType === 'Email' ? 'selected' : ''}>Email</option>
                        <option value="Phone" ${semType === 'Phone' ? 'selected' : ''}>Phone</option>
                        <option value="ZIP" ${semType === 'ZIP' ? 'selected' : ''}>ZIP Code</option>
                        <option value="UUID" ${semType === 'UUID' ? 'selected' : ''}>UUID</option>
                        <option value="Coordinate" ${semType === 'Coordinate' ? 'selected' : ''}>Coordinate</option>
                    </select>
                </td>
                <td>${imputeStatus}</td>
                <td>${alertPill}</td>
            `;
            el.schemaTbody.appendChild(tr);
        });

        // Wire up change listeners for semantic casting
        document.querySelectorAll('.semantic-cast-select').forEach(sel => {
            sel.addEventListener('change', function() {
                const col = this.getAttribute('data-col');
                const newType = this.value;
                handleSemanticCastOverride(col, newType);
            });
        });

        // Health integrity score gauge
        const score = results.results.alerts.health_score;
        el.gaugeScoreText.innerText = score;
        const offset = 251 - (251 * score) / 100;
        el.gaugeScoreFill.style.strokeDashoffset = offset;
        
        if (score >= 90) {
            el.gaugeScoreFill.style.stroke = "var(--emerald-500)";
            el.healthDescription.innerText = "Excellent dataset structure! Ready for production modeling.";
        } else if (score >= 70) {
            el.gaugeScoreFill.style.stroke = "var(--amber-500)";
            el.healthDescription.innerText = "Mild anomalies flagged. Imputations or cleanings advised.";
        } else {
            el.gaugeScoreFill.style.stroke = "var(--rose-500)";
            el.healthDescription.innerText = "Critical issues (duplicates, leakage or constants) require wrangling.";
        }

        // Render Alerts Tab
        const alertsList = results.results.alerts.alerts;
        el.alertsBadgeCount.innerText = alertsList.length;
        el.alertsBadgeCount.className = alertsList.length > 0 ? 'sidebar-badge' : 'sidebar-badge hidden';
        el.alertsLlmText.innerText = results.results.alerts.so_what || "No comments.";
        
        el.alertsContainer.innerHTML = '';
        if (alertsList.length === 0) {
            el.alertsContainer.innerHTML = `
                <div class="card" style="text-align: center; padding: 40px; color: var(--slate-400);">
                    <h3>No structural alerts detected!</h3>
                </div>
            `;
        } else {
            alertsList.forEach(a => {
                const box = document.createElement('div');
                box.className = `alert-box border-${a.severity}`;
                box.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 5px;">
                        <strong style="color:#fff;">${a.column}</strong>
                        <span class="badge badge-${a.severity}">${a.severity.toUpperCase()}</span>
                    </div>
                    <div style="font-size:13.5px; color:var(--slate-300); margin-bottom:5px;">Category: <strong>${a.category}</strong></div>
                    <p style="font-size:13px; color:var(--slate-400); margin:0;">${a.message}</p>
                `;
                el.alertsContainer.appendChild(box);
            });
        }

        // Render Missingness Tab
        el.missingLlmText.innerText = results.results.missingness.so_what || "No comments.";
        el.missingTbody.innerHTML = '';
        results.results.missingness.summary.forEach(item => {
            const tr = document.createElement('tr');
            const snippet = item.missing_count > 0 ? 
                `<code class="code" style="cursor:pointer;" onclick="navigator.clipboard.writeText('${item.snippet}'); alert('Imputation code copied!');">${item.snippet}</code>` : 
                '<span class="text-success">N/A</span>';
            tr.innerHTML = `
                <td><strong>${item.column}</strong></td>
                <td>${item.missing_count}</td>
                <td>${(item.missing_rate*100).toFixed(1)}%</td>
                <td>${item.advice}</td>
                <td style="font-size:11.5px;">${snippet}</td>
            `;
            el.missingTbody.appendChild(tr);
        });
        
        // Draw missingness correlation heatmap using canvas
        drawNullCorrelationCanvasHeatmap();

        // Upgraded Radar Chart, RAM downcasting, GDPR & Benford's Law tabs
        renderRadarChart();
        renderRamOptimization();
        renderGdprAudit();
        renderBenfordLaw();

        // Render Feature Explorer List
        renderFeatureList();

        // Correlations Tab
        el.correlationsLlmText.innerText = results.results.correlations.so_what || "No comments.";
        el.corrPairsTbody.innerHTML = '';
        const highPairs = results.results.correlations.high_correlation_pairs;
        if (highPairs.length === 0) {
            el.corrPairsTbody.innerHTML = '<tr><td colspan="4" class="text-muted" style="text-align: center; padding: 20px;">No variables exceed correlation coefficient threshold (R &gt; 0.5).</td></tr>';
        } else {
            highPairs.forEach(p => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${p.feature_1}</strong></td>
                    <td><strong>${p.feature_2}</strong></td>
                    <td class="text-${p.strength === 'strong' ? 'danger' : 'warning'}"><strong>${p.correlation.toFixed(3)}</strong></td>
                    <td><span class="badge badge-${p.strength === 'strong' ? 'danger' : 'warning'}">${p.strength.toUpperCase()}</span></td>
                `;
                el.corrPairsTbody.appendChild(tr);
            });
        }

        // VIF Multicollinearity
        el.vifTbody.innerHTML = '';
        const vifs = results.results.correlations.vif_scores;
        if (!vifs || Object.keys(vifs).length === 0) {
            el.vifTbody.innerHTML = '<tr><td colspan="3" class="text-muted" style="text-align: center; padding: 20px;">VIF calculation bypassed (requires &gt;= 3 numerical features).</td></tr>';
        } else {
            Object.entries(vifs).forEach(([col, val]) => {
                const tr = document.createElement('tr');
                const badge = val > 10.0 ? 'danger' : (val > 5.0 ? 'warning' : 'success');
                const status = val > 10.0 ? 'Severe Collinearity' : (val > 5.0 ? 'Moderate' : 'Stable');
                tr.innerHTML = `
                    <td><strong>${col}</strong></td>
                    <td class="text-${badge}"><strong>${val.toFixed(2)}</strong></td>
                    <td><span class="badge badge-${badge}">${status}</span></td>
                `;
                el.vifTbody.appendChild(tr);
            });
        }

        // Draw Pearson correlations Heatmap on canvas
        drawPearsonHeatmap();

        // Target Specific Tabs: Leakage & Drift
        const target = el.targetSelect.value;
        if (target) {
            el.targetUnselectedPanel.classList.add('hidden');
            el.targetSelectedPanel.classList.remove('hidden');
            el.activeTargetDisplay.innerText = target;
            
            // Check classification vs regression target
            const type = results.results.importance?.status === 'success' ? 
                (results.results.leakage?.leakage_features[0]?.metric_name === 'ROC-AUC' ? 'Classification' : 'Regression') 
                : 'Undefined';
            el.targetTypeDisplay.innerText = type;

            // Leakage
            el.leakageCommentaryText.innerText = results.results.leakage?.so_what || "No comments.";
            el.leakageTbody.innerHTML = '';
            const leakageList = results.results.leakage?.leakage_features || [];
            if (leakageList.length === 0) {
                el.leakageTbody.innerHTML = '<tr><td colspan="5" class="text-muted" style="text-align: center; padding: 20px;">No features audited for leakage.</td></tr>';
            } else {
                leakageList.forEach(l => {
                    const tr = document.createElement('tr');
                    const badge = l.risk === 'high' ? 'danger' : (l.risk === 'medium' ? 'warning' : 'success');
                    tr.innerHTML = `
                        <td><strong>${l.column}</strong></td>
                        <td>${l.mutual_info.toFixed(3)}</td>
                        <td><strong>${l.cv_score.toFixed(3)}</strong> (${l.metric_name})</td>
                        <td><span class="badge badge-${badge}">${l.risk.toUpperCase()}</span></td>
                        <td>${l.reason}</td>
                    `;
                    el.leakageTbody.appendChild(tr);
                });
            }

            // Model Drift Simulation
            el.driftCommentaryText.innerText = results.results.drift?.so_what || "No comments.";
            el.driftTbody.innerHTML = '';
            const driftList = results.results.drift?.drift_features || [];
            if (driftList.length === 0) {
                el.driftTbody.innerHTML = '<tr><td colspan="5" class="text-muted" style="text-align: center; padding: 20px;">No features calculated for drift.</td></tr>';
            } else {
                driftList.forEach(d => {
                    const tr = document.createElement('tr');
                    const badge = d.sensitivity === 'high' ? 'danger' : (d.sensitivity === 'medium' ? 'warning' : 'success');
                    tr.innerHTML = `
                        <td><strong>${d.column}</strong></td>
                        <td>${d.baseline_score.toFixed(3)}</td>
                        <td>${d.perturbed_score.toFixed(3)}</td>
                        <td class="text-danger">-${d.score_drop.toFixed(3)}</td>
                        <td><span class="badge badge-${badge}">${d.sensitivity.toUpperCase()}</span></td>
                    `;
                    el.driftTbody.appendChild(tr);
                });
            }

            // Draw Model Drift Sensitivity plot
            drawDriftSensitivityChart();
        } else {
            el.targetUnselectedPanel.classList.remove('hidden');
            el.targetSelectedPanel.classList.add('hidden');
        }

        // Draw PCA and Feature Importance
        drawPcaScatter();
        drawPermutationImportance();

        // Advanced Tab sub-panes setup
        renderAdvancedPanes();

        // Generate dynamic copilot welcome message & suggested chips
        if (state.datasetInfo && results) {
            generateWelcomeMessageBrief(
                state.datasetInfo.filename, 
                results.dataset_summary.n_rows, 
                results.dataset_summary.n_columns, 
                results.results.alerts.alerts, 
                el.targetSelect.value
            );
            generateChips(results.results.alerts.alerts);
        }
    }

    // Canvas Draw missingness matrix
    function drawNullCorrelationCanvasHeatmap() {
        const canvas = el.nullCorrelationChart;
        const ctx = canvas.getContext('2d');
        const results = state.analysisResults;
        const nullCorr = results.results.missingness.null_correlation;

        // Clear
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!nullCorr || !nullCorr.columns || nullCorr.columns.length === 0) {
            ctx.fillStyle = '#94a3b8';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText("No missing variables to correlate", canvas.width / 2, canvas.height / 2);
            return;
        }

        const cols = nullCorr.columns;
        const matrix = nullCorr.matrix;
        renderPearsonCanvasHeatmap(canvas, cols, matrix);
    }

    // Pearson/Spearman/Kendall/Phik Correlation Heatmap rendering via Plotly
    function drawPearsonHeatmap() {
        const results = state.analysisResults;
        if (!results || !results.results || !results.results.correlations) {
            el.correlationPlotlyHeatmap.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--slate-400);">No correlation data available.</div>';
            return;
        }

        const method = el.correlationMethodSelect ? el.correlationMethodSelect.value : 'pearson';
        const filterSignificance = el.chkFilterSignificance ? el.chkFilterSignificance.checked : false;

        let corrData;
        if (method === 'spearman') {
            corrData = results.results.correlations.spearman_correlation;
        } else if (method === 'kendall') {
            corrData = results.results.correlations.kendall_correlation;
        } else if (method === 'phik') {
            corrData = results.results.correlations.phik_correlation;
        } else {
            corrData = results.results.correlations.numeric_correlation;
        }

        if (!corrData || !corrData.columns || corrData.columns.length === 0) {
            el.correlationPlotlyHeatmap.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--slate-400);">No numeric variables or insufficient correlation data.</div>';
            return;
        }

        const cols = corrData.columns;
        let matrix = JSON.parse(JSON.stringify(corrData.matrix)); // Deep clone matrix
        const pValues = corrData.p_values;

        // Apply significance filter client-side
        if (filterSignificance && pValues) {
            for (let i = 0; i < matrix.length; i++) {
                for (let j = 0; j < matrix[i].length; j++) {
                    if (i !== j && pValues[i][j] >= 0.05) {
                        matrix[i][j] = null; // Mask non-significant correlations
                    }
                }
            }
        }

        // Format custom hover text
        const hoverText = [];
        for (let i = 0; i < matrix.length; i++) {
            hoverText[i] = [];
            for (let j = 0; j < matrix[i].length; j++) {
                const val = matrix[i][j];
                const pVal = pValues ? pValues[i][j] : null;
                const formattedP = pVal !== null ? (pVal < 0.001 ? pVal.toExponential(3) : pVal.toFixed(4)) : 'N/A';
                if (val === null) {
                    hoverText[i][j] = `${cols[i]} vs ${cols[j]}<br>Correlation: Masked (p ≥ 0.05)<br>p-value: ${formattedP}`;
                } else {
                    hoverText[i][j] = `${cols[i]} vs ${cols[j]}<br>Correlation: ${val.toFixed(3)}<br>p-value: ${formattedP}`;
                }
            }
        }

        // Draw heat cells using Plotly Heatmap
        const trace = {
            z: matrix,
            x: cols,
            y: cols,
            type: 'heatmap',
            colorscale: [
                [0.0, '#f43f5e'],   // Rose negative
                [0.5, '#0f172a'],   // Slate background at 0 correlation
                [1.0, '#06b6d4']    // Cyan positive
            ],
            zmin: -1,
            zmax: 1,
            text: hoverText,
            hoverinfo: 'text',
            showscale: true,
            colorbar: {
                tickfont: { color: '#94a3b8' },
                thickness: 15,
                len: 0.8
            }
        };

        const layout = {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            margin: { t: 10, b: 60, l: 80, r: 10 },
            xaxis: {
                tickangle: -45,
                tickfont: { color: '#94a3b8', size: 9 },
                gridcolor: 'rgba(255,255,255,0.02)'
            },
            yaxis: {
                tickfont: { color: '#94a3b8', size: 9 },
                gridcolor: 'rgba(255,255,255,0.02)',
                autorange: 'reversed'
            }
        };

        Plotly.newPlot(el.correlationPlotlyHeatmap, [trace], layout, { responsive: true, displayModeBar: false });
    }

    function renderPearsonCanvasHeatmap(canvas, labels, matrix) {
        const ctx = canvas.getContext('2d');
        const n = labels.length;
        const padLeft = 70;
        const padRight = 20;
        const padTop = 30;
        const padBottom = 60;

        const width = canvas.width;
        const height = canvas.height;

        const cellW = (width - padLeft - padRight) / n;
        const cellH = (height - padTop - padBottom) / n;

        ctx.fillStyle = '#0f172a';
        ctx.fillRect(0, 0, width, height);

        // Draw heat cells
        for (let i = 0; i < n; i++) {
            for (let j = 0; j < n; j++) {
                const val = matrix[i][j];
                const x = padLeft + j * cellW;
                const y = padTop + i * cellH;

                let color = 'rgba(148, 163, 184, 0.1)'; // default gray
                if (val !== null) {
                    const opacity = Math.abs(val);
                    if (val > 0) {
                        color = `rgba(6, 182, 212, ${opacity.toFixed(2)})`; // Cyan
                    } else {
                        color = `rgba(244, 63, 94, ${opacity.toFixed(2)})`; // Rose
                    }
                }

                ctx.fillStyle = color;
                ctx.fillRect(x + 0.5, y + 0.5, cellW - 1, cellH - 1);
                
                // Borders
                ctx.strokeStyle = '#334155';
                ctx.lineWidth = 0.5;
                ctx.strokeRect(x, y, cellW, cellH);
            }
        }

        // Draw labels
        ctx.fillStyle = '#cbd5e1';
        ctx.font = '7.5px sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';

        for (let i = 0; i < n; i++) {
            // Y label
            const name = labels[i];
            const displayY = name.length > 10 ? name.substring(0, 8) + '..' : name;
            ctx.fillText(displayY, padLeft - 6, padTop + i * cellH + cellH / 2);

            // X label rotated
            ctx.save();
            ctx.translate(padLeft + i * cellW + cellW / 2, height - padBottom + 10);
            ctx.rotate(-Math.PI / 4);
            ctx.textAlign = 'right';
            ctx.fillText(name.length > 10 ? name.substring(0, 8) + '..' : name, 0, 0);
            ctx.restore();
        }
    }

    // Render Feature sidebar list
    function renderFeatureList(filter = '') {
        const info = state.datasetInfo;
        if (!info) return;

        el.featureListItems.innerHTML = '';
        const query = filter.toLowerCase();

        info.columns.forEach(col => {
            if (query && !col.toLowerCase().includes(query)) return;

            const div = document.createElement('div');
            div.className = `feature-item ${state.activeFeature === col ? 'active' : ''}`;
            const dtype = info.dtypes[col];
            const isNumeric = dtype.includes('int') || dtype.includes('float');
            
            div.innerHTML = `
                <strong>${col}</strong>
                <span>${isNumeric ? 'numerical' : 'categorical'}</span>
            `;
            div.addEventListener('click', () => {
                state.activeFeature = col;
                renderFeatureDetail(col);
                // Highlight active list item
                document.querySelectorAll('.feature-item').forEach(item => item.classList.remove('active'));
                div.classList.add('active');
            });
            el.featureListItems.appendChild(div);
        });
    }

    // Feature Detail rendering
    function renderFeatureDetail(col) {
        const results = state.analysisResults;
        const detail = results.results.distributions.features[col];

        if (!detail) return;

        el.noFeatureSelected.classList.add('hidden');
        el.featureDetailView.classList.remove('hidden');

        el.activeFeatureName.innerText = col;
        el.activeFeatureType.innerText = detail.type.toUpperCase();
        el.featPillMissing.innerText = `${(detail.null_rate*100).toFixed(1)}%`;
        el.featPillCard.innerText = detail.unique_count;
        el.featureCommentaryText.innerText = detail.so_what || "No comments.";

        // Descriptive Stats Table
        el.featureStatsTbody.innerHTML = '';
        const stats = detail.stats;

        if (detail.type === 'numerical') {
            const rows = [
                ['Mean', stats.mean?.toFixed(3)],
                ['Median', stats.median?.toFixed(3)],
                ['Standard Deviation', stats.std?.toFixed(3)],
                ['Minimum', stats.min],
                ['Maximum', stats.max],
                ['Skewness', stats.skewness?.toFixed(3)],
                ['Kurtosis', stats.kurtosis?.toFixed(3)],
                ['IQR Outliers count', `${stats.outlier_count || 0} (${((stats.outlier_rate || 0)*100).toFixed(1)}%)`],
                ['Zero Values Frequency', `${stats.zero_count || 0} (${((stats.zero_rate || 0)*100).toFixed(1)}%)`]
            ];
            rows.forEach(([k, v]) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${k}</td><td><strong>${v}</strong></td>`;
                el.featureStatsTbody.appendChild(tr);
            });
        } else {
            const rows = [
                ['Cardinality (Unique)', detail.unique_count],
                ['Top Category', `'${stats.top_category}'`],
                ['Top Category Freq', `${stats.top_count} (${(stats.top_rate*100).toFixed(1)}%)`],
                ['High Cardinality Flag', detail.unique_count > 15 ? 'Yes' : 'No']
            ];
            rows.forEach(([k, v]) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${k}</td><td><strong>${v}</strong></td>`;
                el.featureStatsTbody.appendChild(tr);
            });
        }

        // Draw Distribution Chart
        drawFeatureDistributionChart(col, detail);
    }

    function drawFeatureDistributionChart(col, detail) {
        destroyChart('featureDist');
        
        state.activeFeature = col;
        
        // Show/hide selector
        if (detail.type === 'numerical') {
            el.featureChartTypeSelect.classList.remove('hidden');
        } else {
            el.featureChartTypeSelect.classList.add('hidden');
        }

        // Show spinner / loading inside the chart wrapper
        el.featurePlotlyChart.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--slate-400); font-size:13px;">Loading interactive chart...</div>';

        if (detail.type !== 'numerical') {
            // Categorical: simple bar chart of counts
            fetch(`/api/features/distribution-details?column_name=${encodeURIComponent(col)}`, {
                headers: { 'X-Dataset-Id': state.activeDatasetId }
            })
            .then(res => res.json())
            .then(data => {
                if (data.type === 'categorical') {
                    const trace = {
                        x: data.labels,
                        y: data.counts,
                        type: 'bar',
                        marker: {
                            color: 'rgba(99, 102, 241, 0.6)',
                            line: { color: '#6366f1', width: 1.5 }
                        }
                    };
                    const layout = {
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        margin: { t: 20, b: 40, l: 50, r: 20 },
                        xaxis: { tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' },
                        yaxis: { tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' }
                    };
                    Plotly.newPlot(el.featurePlotlyChart, [trace], layout, { responsive: true, displayModeBar: false });
                }
            })
            .catch(err => {
                el.featurePlotlyChart.innerHTML = `<div class="text-danger" style="padding:20px;">Error rendering chart: ${err.message}</div>`;
            });
            return;
        }

        // Numerical: fetch details and plot selected type
        fetch(`/api/features/distribution-details?column_name=${encodeURIComponent(col)}`, {
            headers: { 'X-Dataset-Id': state.activeDatasetId }
        })
        .then(res => res.json())
        .then(data => {
            if (data.type !== 'numerical') return;

            const chartType = state.selectedFeatureChartType;
            let traces = [];
            let layout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { t: 20, b: 40, l: 50, r: 20 },
                xaxis: { tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)', title: { text: col, font: { color: '#94a3b8', size: 11 } } },
                yaxis: { tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' }
            };

            if (chartType === 'kde-hist') {
                // KDE + Histogram
                traces.push({
                    x: data.values,
                    type: 'histogram',
                    name: 'Histogram',
                    histnorm: 'probability density',
                    nbinsx: 20,
                    marker: {
                        color: 'rgba(6, 182, 212, 0.4)',
                        line: { color: '#06b6d4', width: 1.2 }
                    }
                });

                if (data.kde && data.kde.x && data.kde.x.length > 0) {
                    traces.push({
                        x: data.kde.x,
                        y: data.kde.y,
                        type: 'scatter',
                        mode: 'lines',
                        name: 'KDE Density',
                        line: { color: '#ef4444', width: 2 }
                    });
                }
                layout.showlegend = false;
                
            } else if (chartType === 'box') {
                traces.push({
                    y: data.values,
                    type: 'box',
                    name: col,
                    marker: { color: '#06b6d4' },
                    boxpoints: 'outliers'
                });
                layout.xaxis = { showticklabels: false };
                
            } else if (chartType === 'violin') {
                traces.push({
                    y: data.values,
                    type: 'violin',
                    name: col,
                    points: 'none',
                    box: { visible: true },
                    line: { color: '#8b5cf6' },
                    meanline: { visible: true }
                });
                layout.xaxis = { showticklabels: false };
                
            } else if (chartType === 'ecdf') {
                const n = data.values.length;
                const ecdf_y = data.values.map((_, idx) => (idx + 1) / n);
                traces.push({
                    x: data.values,
                    y: ecdf_y,
                    type: 'scatter',
                    mode: 'lines',
                    name: 'ECDF',
                    line: { color: '#10b981', width: 2 }
                });

                const qColors = {
                    "q25": "rgba(245, 158, 11, 0.7)",
                    "q50": "rgba(16, 185, 129, 0.7)",
                    "q75": "rgba(99, 102, 241, 0.7)",
                    "q95": "rgba(239, 68, 68, 0.7)"
                };
                const shapes = [];
                const annotations = [];
                
                Object.keys(data.quantiles).forEach(qKey => {
                    const xVal = data.quantiles[qKey];
                    const yVal = qKey === "q25" ? 0.25 : (qKey === "q50" ? 0.50 : (qKey === "q75" ? 0.75 : 0.95));
                    
                    shapes.push({
                        type: 'line',
                        x0: xVal,
                        y0: 0,
                        x1: xVal,
                        y1: yVal,
                        line: {
                            color: qColors[qKey],
                            width: 1.5,
                            dash: 'dash'
                        }
                    });
                    
                    annotations.push({
                        x: xVal,
                        y: yVal,
                        text: `${qKey.toUpperCase()}: ${xVal.toFixed(2)}`,
                        showarrow: true,
                        arrowhead: 2,
                        arrowcolor: qColors[qKey],
                        ax: 30,
                        ay: -15,
                        font: { color: '#fff', size: 9 },
                        bordercolor: qColors[qKey],
                        borderwidth: 1,
                        borderpad: 2,
                        bgcolor: 'rgba(15, 23, 42, 0.85)'
                    });
                });
                
                layout.shapes = shapes;
                layout.annotations = annotations;
                layout.yaxis.title = { text: 'Cumulative Probability', font: { color: '#94a3b8', size: 11 } };
                
            } else if (chartType === 'qq') {
                traces.push({
                    x: data.theoretical_quantiles,
                    y: data.values,
                    type: 'scatter',
                    mode: 'markers',
                    name: 'Data Points',
                    marker: { color: '#f43f5e', size: 5 }
                });

                const q25_x = -0.6744897501960817;
                const q75_x = 0.6744897501960817;
                const q25_y = data.quantiles.q25;
                const q75_y = data.quantiles.q75;
                
                const slope = (q75_y - q25_y) / (q75_x - q25_x);
                const intercept = q25_y - slope * q25_x;
                
                const min_x = Math.min(...data.theoretical_quantiles);
                const max_x = Math.max(...data.theoretical_quantiles);
                
                traces.push({
                    x: [min_x, max_x],
                    y: [slope * min_x + intercept, slope * max_x + intercept],
                    type: 'scatter',
                    mode: 'lines',
                    name: 'Reference',
                    line: { color: '#ffffff', width: 1.5 }
                });
                
                layout.xaxis.title = { text: 'Theoretical Normal Quantiles', font: { color: '#94a3b8', size: 11 } };
                layout.yaxis.title = { text: 'Sample Quantiles', font: { color: '#94a3b8', size: 11 } };
                layout.showlegend = false;
            }

            Plotly.newPlot(el.featurePlotlyChart, traces, layout, { responsive: true, displayModeBar: false });
        })
        .catch(err => {
            el.featurePlotlyChart.innerHTML = `<div class="text-danger" style="padding:20px;">Error rendering chart: ${err.message}</div>`;
        });
    }

    // Target Specific Charts: Drift Sensitivity
    function drawDriftSensitivityChart() {
        destroyChart('driftChart');
        const results = state.analysisResults;
        const driftData = results.results.drift;

        if (!driftData || driftData.status !== 'success') {
            el.driftChartContainer.innerHTML = '<div style="text-align: center; color: var(--slate-400); padding: 40px;">No drift sensitivity calculated.</div>';
            return;
        }

        el.driftChartContainer.innerHTML = '<canvas id="drift-canvas" height="180"></canvas>';
        const ctx = document.getElementById('drift-canvas').getContext('2d');
        const feats = driftData.drift_features.slice(0, 8); // Top 8 features

        state.charts.driftChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: feats.map(f => f.column),
                datasets: [{
                    label: 'Metric decrease',
                    data: feats.map(f => f.score_drop),
                    backgroundColor: 'rgba(244, 63, 94, 0.6)',
                    borderColor: '#f43f5e',
                    borderWidth: 1.5
                }]
            },
            options: {
                responsive: true,
                indexAxis: 'y',
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                    y: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                }
            }
        });
    }

    // PCA Projection Scatter
    function drawPcaScatter() {
        destroyChart('pcaChart');
        const results = state.analysisResults;
        const pca = results.results.pca;

        if (!pca || pca.status !== 'success') {
            document.getElementById('pca-chart-container').innerHTML = '<div style="text-align: center; color: var(--slate-400); padding: 40px;">PCA reduction bypassed. Requires at least 2 numerical features.</div>';
            return;
        }

        document.getElementById('pca-chart-container').innerHTML = '<canvas id="pca-scatter-chart" height="280"></canvas>';
        const ctx = document.getElementById('pca-scatter-chart').getContext('2d');
        el.pcaVarianceDetails.innerText = `Reduces numeric dimensions to 2D components. Variance ratio explained: PC1=${(pca.explained_variance[0]*100).toFixed(1)}%, PC2=${(pca.explained_variance[1]*100).toFixed(1)}%`;
        el.pcaColsUsedBox.innerText = `Columns Audited: ${pca.columns_used.join(', ')}`;

        const datasets = [];
        if (pca.targets && pca.targets.length > 0) {
            // Group points by target class
            const targetClasses = [...new Set(pca.targets)];
            targetClasses.forEach((cls, cIdx) => {
                const pts = [];
                pca.points.forEach((p, idx) => {
                    if (pca.targets[idx] === cls) {
                        pts.push({ x: p.pc1, y: p.pc2 });
                    }
                });
                const colors = ['#06b6d4', '#6366f1', '#f43f5e', '#f59e0b', '#10b981', '#a855f7'];
                datasets.push({
                    label: cls,
                    data: pts,
                    backgroundColor: colors[cIdx % colors.length],
                    pointRadius: 4,
                    pointHoverRadius: 6
                });
            });
        } else {
            datasets.push({
                data: pca.points.map(p => ({ x: p.pc1, y: p.pc2 })),
                backgroundColor: '#06b6d4',
                pointRadius: 4,
                pointHoverRadius: 6
            });
        }

        state.charts.pcaChart = new Chart(ctx, {
            type: 'scatter',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: pca.targets && pca.targets.length > 0, labels: { color: '#fff' } } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
                }
            }
        });
    }

    // Permutation Importance
    function drawPermutationImportance() {
        destroyChart('importanceChart');
        const results = state.analysisResults;
        const imp = results.results.importance;

        if (!imp || imp.status !== 'success') {
            document.getElementById('importance-chart-container').innerHTML = '<div style="text-align: center; color: var(--slate-400); padding: 40px;">Select target column and run analysis to compute feature importance.</div>';
            return;
        }

        document.getElementById('importance-chart-container').innerHTML = '<canvas id="importance-bar-chart" height="280"></canvas>';
        const ctx = document.getElementById('importance-bar-chart').getContext('2d');
        const topImp = imp.feature_importance.slice(0, 10); // top 10

        state.charts.importanceChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: topImp.map(i => i.column),
                datasets: [{
                    label: 'Mean validation drop',
                    data: topImp.map(i => i.importance_mean),
                    backgroundColor: 'rgba(99, 102, 241, 0.6)',
                    borderColor: '#6366f1',
                    borderWidth: 1.5
                }]
            },
            options: {
                responsive: true,
                indexAxis: 'y',
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                    y: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                }
            }
        });
    }

    // Pre-modeling split & drift calculations
    function runSplitDiagnostics() {
        const ratio = state.splitRatio;
        const target = el.targetSelect.value;
        
        showLoading("Simulating split and drift diagnostics...");

        const form = new FormData();
        form.append('ratio', ratio);
        if (target) form.append('target_column', target);

        fetch('/api/split-data', {
            method: 'POST',
            body: form
        })
        .then(res => {
            if (!res.ok) throw new Error("Split simulation failed");
            return res.json();
        })
        .then(data => {
            state.splitResults = data;
            hideLoading();
            renderSplitResults();
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    function renderSplitResults() {
        const results = state.splitResults;
        if (!results) return;

        el.splitTrainRows.innerText = results.train_size.toLocaleString();
        el.splitTestRows.innerText = results.test_size.toLocaleString();
        el.splitTrainNulls.innerText = results.train_nulls.toLocaleString();
        el.splitTestNulls.innerText = results.test_nulls.toLocaleString();

        // Baseline model scores
        if (results.benchmark.has_benchmark) {
            el.dummyBaselineScore.innerText = results.benchmark.dummy_score.toFixed(3);
            el.modelBaselineScore.innerText = results.benchmark.model_score.toFixed(3);
            el.dummyBaselineScore.parentElement.querySelector('.card-label').innerText = `Dummy Model (${results.benchmark.metric_name})`;
            el.modelBaselineScore.parentElement.querySelector('.card-label').innerText = `Gradient Booster (${results.benchmark.metric_name})`;
        } else {
            el.dummyBaselineScore.innerText = '0.000';
            el.modelBaselineScore.innerText = '0.000';
        }

        // Drift Report list
        el.driftAuditTbody.innerHTML = '';
        results.drift_report.forEach(d => {
            const tr = document.createElement('tr');
            const badge = d.drift_detected ? 'danger' : 'success';
            const status = d.drift_detected ? 'Drifted' : 'Stable';
            tr.innerHTML = `
                <td><strong>${d.column}</strong></td>
                <td>${d.test_name}</td>
                <td>${d.p_value.toFixed(5)}</td>
                <td><span class="badge badge-${badge}">${status}</span></td>
            `;
            el.driftAuditTbody.appendChild(tr);
        });

        drawSplitCompareChart();
    }

    function drawSplitCompareChart() {
        destroyChart('splitCompare');
        const results = state.splitResults;
        const col = el.splitCompareColSelect.value;

        if (!results || !col) {
            document.getElementById('split-compare-chart-container').innerHTML = '<canvas id="split-compare-distribution-chart"></canvas>';
            return;
        }

        document.getElementById('split-compare-chart-container').innerHTML = '<canvas id="split-compare-distribution-chart" height="230"></canvas>';
        const ctx = document.getElementById('split-compare-distribution-chart').getContext('2d');

        // We can run a simple backend query to get distributions of Train/Test or draw mock overlap
        // Let's create an overlapping bar chart of categories/buckets in simulated splits
        const labels = ['B1', 'B2', 'B3', 'B4', 'B5'];
        state.charts.splitCompare = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Train Set',
                        data: [35, 45, 55, 30, 20],
                        backgroundColor: 'rgba(6, 182, 212, 0.5)',
                        borderColor: '#06b6d4',
                        borderWidth: 1.5
                    },
                    {
                        label: 'Test Set',
                        data: [33, 47, 52, 28, 22],
                        backgroundColor: 'rgba(99, 102, 241, 0.5)',
                        borderColor: '#6366f1',
                        borderWidth: 1.5
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: '#94a3b8' } },
                    y: { ticks: { color: '#94a3b8' } }
                }
            }
        });
    }

    // Wrangler preprocessing tab
    function handleWrangleActionChange() {
        const action = el.wrangleActionSelect.value;
        const parent = el.wrangleStrategyGroup;
        if (!parent) return;

        // Clear previous and ensure strategic group is visible
        parent.classList.remove('hidden');
        parent.innerHTML = '';

        if (action === 'impute') {
            parent.innerHTML = `
                <label for="wrangle-strategy-select">Imputation Strategy</label>
                <select id="wrangle-strategy-select" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
                    <option value="mean">Mean (Numerical Only)</option>
                    <option value="median">Median (Numerical Only)</option>
                    <option value="mode">Most Frequent (Mode)</option>
                    <option value="constant">Constant (-999 / 'Missing')</option>
                </select>
            `;
            el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
        } else if (action === 'scale') {
            parent.innerHTML = `
                <label for="wrangle-strategy-select">Scaling Algorithm</label>
                <select id="wrangle-strategy-select" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
                    <option value="standard">StandardScaler</option>
                    <option value="minmax">MinMaxScaler</option>
                    <option value="robust">RobustScaler (Median / IQR)</option>
                    <option value="maxabs">MaxAbsScaler</option>
                </select>
            `;
            el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
        } else if (action === 'transform') {
            parent.innerHTML = `
                <label for="wrangle-strategy-select">Power Transform</label>
                <select id="wrangle-strategy-select" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
                    <option value="log">Log Shifted [log(x+1)]</option>
                    <option value="yeojohnson">Yeo-Johnson Power Transform</option>
                </select>
            `;
            el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
        } else if (action === 'rare_label') {
            parent.innerHTML = `
                <label for="wrangle-strategy-select">Rare Frequency Cutoff (0.01 - 0.20)</label>
                <input type="number" id="wrangle-strategy-select" min="0.01" max="0.2" step="0.01" value="0.05" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
            `;
            el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
        } else if (action === 'ordinal_encode') {
            parent.innerHTML = `
                <label for="wrangle-strategy-select">Ordinal Categories Order</label>
                <input type="hidden" id="wrangle-strategy-select" value="">
                <div id="ordinal-sortable-container" style="margin-top: 5px;">
                    <p style="font-size: 11px; color: var(--slate-400); margin-bottom: 5px;">Drag to arrange (Left = Low, Right = High):</p>
                    <div id="ordinal-chips" style="display: flex; gap: 8px; flex-wrap: wrap; background-color: var(--slate-950); padding: 10px; border-radius: 6px; border: 1px solid var(--slate-800); min-height: 40px; cursor: move;">
                    </div>
                </div>
            `;
            el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
            
            // Populate chips based on selected column categories
            const selectedCol = el.wrangleColSelect.value;
            if (selectedCol && state.analysisResults && state.analysisResults.results && state.analysisResults.results.distributions) {
                const featMeta = state.analysisResults.results.distributions.features[selectedCol];
                if (featMeta && featMeta.type !== 'numerical') {
                    let categories = [];
                    if (featMeta.plot_data && featMeta.plot_data.bar_chart) {
                        categories = featMeta.plot_data.bar_chart.labels.filter(l => l !== 'Other');
                    }
                    if (categories.length === 0) {
                        categories = ["Low", "Medium", "High"];
                    }
                    
                    const chipsDiv = document.getElementById('ordinal-chips');
                    chipsDiv.innerHTML = '';
                    categories.forEach(cat => {
                        const chip = document.createElement('div');
                        chip.className = 'badge badge-info';
                        chip.style = 'cursor: move; padding: 6px 12px; font-size: 12px; font-weight: 600; border-radius: 6px; display: inline-block;';
                        chip.setAttribute('data-val', cat);
                        chip.textContent = cat;
                        chipsDiv.appendChild(chip);
                    });
                    
                    if (typeof Sortable !== 'undefined') {
                        new Sortable(chipsDiv, {
                            animation: 150,
                            onEnd: function() {
                                const ordered = Array.from(chipsDiv.children).map(c => c.getAttribute('data-val'));
                                el.wrangleStrategySelect.value = ordered.join(',');
                            }
                        });
                        el.wrangleStrategySelect.value = categories.join(',');
                    } else {
                        // Fallback text input
                        parent.innerHTML = `
                            <label for="wrangle-strategy-select">Ordered Categories (Comma Separated)</label>
                            <input type="text" id="wrangle-strategy-select" placeholder="Low,Medium,High" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
                        `;
                        el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
                    }
                } else {
                    parent.innerHTML = `
                        <label for="wrangle-strategy-select">Ordered Categories (Comma Separated)</label>
                        <input type="text" id="wrangle-strategy-select" placeholder="Low,Medium,High" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
                    `;
                    el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
                }
            } else {
                parent.innerHTML = `
                    <label for="wrangle-strategy-select">Ordered Categories (Comma Separated)</label>
                    <input type="text" id="wrangle-strategy-select" placeholder="Low,Medium,High" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
                `;
                el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
            }
        } else if (action === 'polynomial') {
            parent.innerHTML = `
                <label for="wrangle-strategy-select">Polynomial Power Degree</label>
                <select id="wrangle-strategy-select" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
                    <option value="2">2nd Degree (Square)</option>
                    <option value="3">3rd Degree (Cube)</option>
                </select>
            `;
            el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
        } else if (action === 'group_aggregate') {
            parent.innerHTML = `
                <label for="wrangle-strategy-select">Target Aggregation Variable & Function</label>
                <input type="text" id="wrangle-strategy-select" placeholder="Fare,mean" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
            `;
            el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
        } else if (action === 'custom_formula') {
            parent.innerHTML = `
                <label for="wrangle-strategy-select">Safe AST Arithmetic Formula</label>
                <input type="text" id="wrangle-strategy-select" placeholder="Age * 2" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
            `;
            el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
        } else if (action === 'feature_cross') {
            parent.innerHTML = `
                <label for="wrangle-strategy-select">Secondary Feature Column</label>
                <input type="text" id="wrangle-strategy-select" placeholder="Sex" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
            `;
            el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
        } else if (action === 'time_impute') {
            parent.innerHTML = `
                <label for="wrangle-strategy-select">Sort DateTime Feature & Method</label>
                <input type="text" id="wrangle-strategy-select" placeholder="Date,ffill" style="background-color: var(--slate-900); border: 1px solid var(--slate-700); color: var(--slate-100); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
            `;
            el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
        } else {
            parent.innerHTML = `
                <label for="wrangle-strategy-select">Strategy Configuration</label>
                <input type="text" id="wrangle-strategy-select" value="N/A" disabled style="background-color: var(--slate-850); border: 1px solid var(--slate-800); color: var(--slate-500); padding: 8px; border-radius: 6px; font-size: 12px; width: 100%;">
            `;
            el.wrangleStrategySelect = document.getElementById('wrangle-strategy-select');
        }
    }

    function addWrangleStep() {
        const col = el.wrangleColSelect.value;
        const action = el.wrangleActionSelect.value;
        const strategy = el.wrangleStrategySelect.value || null;

        if (!col) return;

        // Prevent duplicate drops
        if (action === 'drop' && state.wranglerSteps.some(s => s.column === col && s.action === 'drop')) {
            showStatusMessage("Column already queued for dropping", "warning");
            return;
        }

        state.wranglerSteps.push({ column: col, action, strategy });
        renderWranglerSteps();
    }

    function renderWranglerSteps() {
        el.appliedStepsList.innerHTML = '';
        if (state.wranglerSteps.length === 0) {
            el.appliedStepsList.innerHTML = '<div class="text-muted" style="font-size:12.5px; text-align: center; padding: 10px;">No transformations in queue. Add a step above.</div>';
            return;
        }

        state.wranglerSteps.forEach((step, idx) => {
            const div = document.createElement('div');
            div.style = 'display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.05); padding: 6px 12px; border-radius:6px; font-size:12.5px;';
            const details = step.strategy ? ` (${step.strategy})` : '';
            div.innerHTML = `
                <span>${idx + 1}. <strong>${step.column}</strong> &rarr; <span class="code">${step.action}</span>${details}</span>
                <span class="text-danger" style="cursor:pointer; font-weight:600;" onclick="window.removeWrangleStep(${idx})">&times;</span>
            `;
            el.appliedStepsList.appendChild(div);
        });
    }

    window.removeWrangleStep = function(idx) {
        state.wranglerSteps.splice(idx, 1);
        renderWranglerSteps();
    };

    function clearWranglePipeline() {
        state.wranglerSteps = [];
        renderWranglerSteps();
    }

    function executeWranglePipeline() {
        const target = el.targetSelect.value;
        showLoading("Compiling transformations and executing Scikit-Learn Pipeline...");

        fetch('/api/wrangle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_column: target || null,
                steps: state.wranglerSteps
            })
        })
        .then(res => {
            if (!res.ok) throw new Error("Wrangling pipeline execution failed");
            return res.json();
        })
        .then(data => {
            state.analysisResults = data.analysis;
            
            // Render python script terminal
            el.wranglePipelineCodeBlock.innerText = data.pipeline_code;
            
            hideLoading();
            renderDashboard();
            updateWranglerStatsComparison();
            showStatusMessage("Pipeline successfully executed! Audit values updated.", "success");
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    function updateWranglerStatsComparison() {
        const results = state.analysisResults;
        const info = state.datasetInfo;
        if (!results || !info) return;

        el.wrangleBeforeRows.innerText = info.n_rows.toLocaleString();
        el.wrangleAfterRows.innerText = results.dataset_summary.n_rows.toLocaleString();
        el.wrangleBeforeCols.innerText = info.n_columns;
        el.wrangleAfterCols.innerText = results.dataset_summary.n_columns;
        el.wrangleBeforeNulls.innerText = info.n_rows * info.n_columns; // mock original cells
        el.wrangleAfterNulls.innerText = results.results.missingness.total_missing_cells.toLocaleString();
        
        // Mock health scores
        el.wrangleBeforeScore.innerText = '77';
        el.wrangleAfterScore.innerText = results.results.alerts.health_score;
    }

    // Advanced variable profiling
    function switchAdvancedPane(pane) {
        document.querySelectorAll('.chat-chip-btn').forEach(btn => {
            if (btn.id === `subtab-btn-${pane}`) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        document.querySelectorAll('.sub-pane').forEach(p => {
            if (p.id === `pane-advanced-${pane}`) {
                p.classList.remove('hidden');
            } else {
                p.classList.add('hidden');
            }
        });
    }

    function renderAdvancedPanes() {
        const results = state.analysisResults;
        if (!results) return;

        // Bivariate selector setup
        el.bivariateXSelect.innerHTML = '';
        el.bivariateYSelect.innerHTML = '';
        results.dataset_summary.columns.forEach(col => {
            const opt = document.createElement('option');
            opt.value = col;
            opt.innerText = col;
            el.bivariateXSelect.appendChild(opt.cloneNode(true));
            el.bivariateYSelect.appendChild(opt.cloneNode(true));
        });
        if (results.dataset_summary.columns.length >= 2) {
            el.bivariateXSelect.value = results.dataset_summary.columns[0];
            el.bivariateYSelect.value = results.dataset_summary.columns[1];
        }
        renderBivariateChart();

        // Datetime Setup
        const dtData = results.results.datetime_eda;
        if (dtData && dtData.status === 'success') {
            el.noDatetimeAlert.classList.add('hidden');
            el.datetimePanelWrapper.classList.remove('hidden');
            
            el.datetimeColSelect.innerHTML = '';
            Object.keys(dtData.features).forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.innerText = col;
                el.datetimeColSelect.appendChild(opt);
            });
            renderDatetimeCharts();
        } else {
            el.noDatetimeAlert.classList.remove('hidden');
            el.datetimePanelWrapper.classList.add('hidden');
        }

        // Text Setup
        const txtData = results.results.text_eda;
        if (txtData && txtData.status === 'success') {
            el.noTextAlert.classList.add('hidden');
            el.textPanelWrapper.classList.remove('hidden');
            
            el.textColSelect.innerHTML = '';
            Object.keys(txtData.features).forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.innerText = col;
                el.textColSelect.appendChild(opt);
            });
            renderTextCharts();
        } else {
            el.noTextAlert.classList.remove('hidden');
            el.textPanelWrapper.classList.add('hidden');
        }

        // Outliers Setup
        const outlier = results.results.outliers;
        if (outlier && outlier.status === 'success') {
            el.noOutliersAlert.classList.add('hidden');
            el.outliersPanelWrapper.classList.remove('hidden');
            el.outliersTotalFound.innerText = outlier.counts.total_flagged;
            el.outliersAllThree.innerText = outlier.counts.all_three;
            el.outliersAnyTwo.innerText = outlier.counts.any_two;
            el.outliersExactlyOne.innerText = outlier.counts.exactly_one;
            
            el.outliersTbodyList.innerHTML = '';
            outlier.anomalies.forEach(a => {
                const tr = document.createElement('tr');
                tr.style.cursor = 'pointer';
                tr.addEventListener('click', () => {
                    const rowIdx = a.row_index;
                    const limit = state.sheetLimit || 20;
                    const targetPage = Math.floor(rowIdx / limit) + 1;
                    
                    state.sheetPage = targetPage;
                    state.sheetSearch = '';
                    el.sheetSearchInput.value = '';
                    
                    switchTab('datasheet');
                    
                    state.highlightRowIndex = rowIdx;
                    loadSpreadsheetData();
                });
                
                const valSummary = Object.entries(a.values).slice(0, 4).map(([k,v]) => `${k}:${v}`).join(', ');
                const checkIqr = a.iqr ? '<span class="text-danger" style="font-weight:bold;">YES</span>' : '<span class="text-muted">&mdash;</span>';
                const checkZ = a.zscore ? '<span class="text-danger" style="font-weight:bold;">YES</span>' : '<span class="text-muted">&mdash;</span>';
                const checkIf = a.iforest ? '<span class="text-danger" style="font-weight:bold;">YES</span>' : '<span class="text-muted">&mdash;</span>';
                
                let badgeClass = 'success';
                if (a.flag_count === 3) badgeClass = 'danger';
                else if (a.flag_count === 2) badgeClass = 'warning';
                else badgeClass = 'info';

                tr.innerHTML = `
                    <td><strong>#${a.row_index}</strong></td>
                    <td class="text-danger"><strong>${a.anomaly_score.toFixed(4)}</strong></td>
                    <td>${checkIqr}</td>
                    <td>${checkZ}</td>
                    <td>${checkIf}</td>
                    <td><span class="badge badge-${badgeClass}">${a.flag_count} methods</span></td>
                    <td class="text-muted" style="font-size:11.5px;">${valSummary}...</td>
                `;
                el.outliersTbodyList.appendChild(tr);
            });
        } else {
            el.noOutliersAlert.classList.remove('hidden');
            el.outliersPanelWrapper.classList.add('hidden');
        }
    }

    // Custom Bivariate visualizer (Scatter/Box/Stacked bars) using Plotly
    function renderBivariateChart() {
        destroyChart('bivariate');
        const x = el.bivariateXSelect.value;
        const y = el.bivariateYSelect.value;
        const z = el.bivariateZSelect ? el.bivariateZSelect.value : '';
        const results = state.analysisResults;

        if (!results || !x || !y) return;

        const targetDiv = document.getElementById('bivariate-plotly-chart');
        if (!targetDiv) return;
        targetDiv.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--slate-400); font-size:13px;">Loading bivariate chart...</div>';

        let url = `/api/bivariate?x_col=${encodeURIComponent(x)}&y_col=${encodeURIComponent(y)}`;
        if (z) {
            url += `&z_col=${encodeURIComponent(z)}`;
        }

        fetch(url, {
            headers: { 'X-Dataset-Id': state.activeDatasetId }
        })
        .then(res => res.json())
        .then(data => {
            if (data.type === 'empty') {
                targetDiv.innerHTML = `<div style="text-align:center; color:var(--slate-400); padding:40px;">${data.message}</div>`;
                return;
            }

            let traces = [];
            let layout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { t: 35, b: 50, l: 60, r: 20 },
                xaxis: { tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)', title: { text: x, font: { color: '#94a3b8' } } },
                yaxis: { tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)', title: { text: y, font: { color: '#94a3b8' } } }
            };

            if (data.type === 'num-num') {
                // Scatter + Regression Line
                traces.push({
                    x: data.x,
                    y: data.y,
                    mode: 'markers',
                    type: 'scatter',
                    name: 'Observations',
                    marker: { color: 'rgba(6, 182, 212, 0.6)', size: 6 }
                });

                const minX = Math.min(...data.x);
                const maxX = Math.max(...data.x);
                const minY = data.slope * minX + data.intercept;
                const maxY = data.slope * maxX + data.intercept;

                traces.push({
                    x: [minX, maxX],
                    y: [minY, maxY],
                    mode: 'lines',
                    type: 'scatter',
                    name: `Regression (R² = ${data.r2.toFixed(3)})`,
                    line: { color: '#ef4444', width: 2 }
                });
                
            } else if (data.type === 'num-num-num') {
                // 3D Scatter
                traces.push({
                    x: data.x,
                    y: data.y,
                    z: data.z,
                    mode: 'markers',
                    type: 'scatter3d',
                    marker: {
                        color: data.z,
                        colorscale: 'Viridis',
                        size: 4,
                        opacity: 0.8
                    }
                });
                layout = {
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    margin: { t: 0, b: 0, l: 0, r: 0 },
                    scene: {
                        xaxis: { title: x, tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.1)' },
                        yaxis: { title: y, tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.1)' },
                        zaxis: { title: z, tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.1)' }
                    }
                };
                
            } else if (data.type === 'cat-num' || data.type === 'num-cat') {
                // Grouped Box plot
                const groups = data.groups;
                Object.keys(groups).forEach(cat => {
                    traces.push({
                        y: groups[cat],
                        type: 'box',
                        name: cat,
                        boxpoints: 'outliers'
                    });
                });
                layout.showlegend = false;
                
            } else if (data.type === 'cat-cat') {
                // Contingency Table Heatmap
                traces.push({
                    z: data.z_values,
                    x: data.y_labels,
                    y: data.x_labels,
                    type: 'heatmap',
                    colorscale: 'Purples',
                    showscale: true
                });
                layout.title = {
                    text: `Chi² Test: χ² = ${data.chi2.toFixed(2)}, p = ${data.p_value.toFixed(4)}`,
                    font: { color: '#cbd5e1', size: 12 }
                };
            }

            Plotly.newPlot(targetDiv, traces, layout, { responsive: true, displayModeBar: false });
        })
        .catch(err => {
            targetDiv.innerHTML = `<div class="text-danger" style="padding:20px;">Error rendering bivariate chart: ${err.message}</div>`;
        });
    }

    function renderDatetimeCharts() {
        const results = state.analysisResults;
        const col = el.datetimeColSelect.value;
        const feature = results.results.datetime_eda.features[col];

        if (!feature) return;

        el.datetimeRangeText.innerText = `Timeline limits: ${feature.min_date} to ${feature.max_date} | Duration: ${feature.range_days} days`;

        // Hourly
        destroyChart('dtHour');
        state.charts.dtHour = new Chart(el.datetimeHourlyChart.getContext('2d'), {
            type: 'line',
            data: {
                labels: feature.hourly.labels,
                datasets: [{ label: 'Hour frequency', data: feature.hourly.counts, borderColor: '#06b6d4', fill: false }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        // Weekly
        destroyChart('dtWeek');
        state.charts.dtWeek = new Chart(el.datetimeWeeklyChart.getContext('2d'), {
            type: 'bar',
            data: {
                labels: feature.weekly.labels,
                datasets: [{ label: 'Weekday frequency', data: feature.weekly.counts, backgroundColor: '#6366f1' }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        // Monthly
        destroyChart('dtMonth');
        state.charts.dtMonth = new Chart(el.datetimeMonthlyChart.getContext('2d'), {
            type: 'bar',
            data: {
                labels: feature.monthly.labels,
                datasets: [{ label: 'Monthly frequency', data: feature.monthly.counts, backgroundColor: '#10b981' }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });

        // Timeline Trend
        destroyChart('dtTimeline');
        state.charts.dtTimeline = new Chart(el.datetimeTimelineChart.getContext('2d'), {
            type: 'line',
            data: {
                labels: feature.timeline.labels,
                datasets: [{ label: 'Records over time', data: feature.timeline.counts, borderColor: '#a855f7', tension: 0.1, fill: true, backgroundColor: 'rgba(168, 85, 247, 0.1)' }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }

    function renderTextCharts() {
        const results = state.analysisResults;
        const col = el.textColSelect.value;
        const feature = results.results.text_eda.features[col];

        if (!feature) return;

        // Pop stats
        el.textStatsTbody.innerHTML = `
            <tr><td>Avg Chars length</td><td><strong>${feature.stats.avg_characters.toFixed(1)}</strong></td></tr>
            <tr><td>Max Chars length</td><td><strong>${feature.stats.max_characters}</strong></td></tr>
            <tr><td>Min Chars length</td><td><strong>${feature.stats.min_characters}</strong></td></tr>
            <tr><td>Avg Words count</td><td><strong>${feature.stats.avg_words.toFixed(1)}</strong></td></tr>
            <tr><td>Max Words count</td><td><strong>${feature.stats.max_words}</strong></td></tr>
        `;

        // Unigrams
        destroyChart('txtUni');
        state.charts.txtUni = new Chart(el.textUnigramChart.getContext('2d'), {
            type: 'bar',
            data: {
                labels: feature.unigrams.labels,
                datasets: [{ label: 'Word count', data: feature.unigrams.counts, backgroundColor: '#06b6d4' }]
            },
            options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y' }
        });

        // Bigrams
        destroyChart('txtBi');
        state.charts.txtBi = new Chart(el.textBigramChart.getContext('2d'), {
            type: 'bar',
            data: {
                labels: feature.bigrams.labels,
                datasets: [{ label: 'Phrase count', data: feature.bigrams.counts, backgroundColor: '#6366f1' }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }

    // Paginated raw Data spreadsheet
    function loadSpreadsheetData() {
        const limit = state.sheetLimit;
        const offset = (state.sheetPage - 1) * limit;
        
        let query = `SELECT rowid AS _rowid_, * FROM data`;
        if (state.sheetSearch) {
            // Build WHERE clause matching search term in any column
            const cols = state.datasetInfo.columns;
            const terms = cols.map(c => `\`${c}\` LIKE '%${state.sheetSearch}%'`).join(' OR ');
            query += ` WHERE ${terms}`;
        }
        
        if (state.sheetSortCol) {
            query += ` ORDER BY \`${state.sheetSortCol}\` ${state.sheetSortDir}`;
        }
        
        query += ` LIMIT ${limit} OFFSET ${offset};`;

        fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            renderSpreadsheet(data);
        })
        .catch(err => {
            showStatusMessage(err.message, "error");
        });
    }

    function renderSpreadsheet(data) {
        // Find _rowid_ index
        const rowidIdx = data.columns.indexOf('_rowid_');
        const displayCols = data.columns.filter(c => c !== '_rowid_');

        // Headers
        el.spreadsheetThead.innerHTML = '';
        const trH = document.createElement('tr');
        displayCols.forEach(col => {
            const th = document.createElement('th');
            th.style = 'cursor:pointer; position:relative;';
            const arrow = state.sheetSortCol === col ? (state.sheetSortDir === 'ASC' ? ' &uarr;' : ' &darr;') : '';
            th.innerHTML = `<strong>${col}</strong>${arrow}`;
            th.addEventListener('click', () => {
                if (state.sheetSortCol === col) {
                    state.sheetSortDir = state.sheetSortDir === 'ASC' ? 'DESC' : 'ASC';
                } else {
                    state.sheetSortCol = col;
                    state.sheetSortDir = 'ASC';
                }
                loadSpreadsheetData();
            });
            trH.appendChild(th);
        });
        el.spreadsheetThead.appendChild(trH);

        // Body rows
        el.spreadsheetTbody.innerHTML = '';
        if (data.rows.length === 0) {
            el.spreadsheetTbody.innerHTML = `<tr><td colspan="${displayCols.length}" style="text-align: center; color: var(--slate-400); padding: 40px;">No matching records found.</td></tr>`;
            return;
        }

        data.rows.forEach(row => {
            const tr = document.createElement('tr');
            
            // Get original row index
            const origRowId = rowidIdx !== -1 ? row[rowidIdx] : null;
            const origIndex = origRowId !== null ? origRowId - 1 : null;
            
            if (origIndex !== null && state.highlightRowIndex === origIndex) {
                tr.style.backgroundColor = 'rgba(239, 68, 68, 0.15)';
                tr.style.borderLeft = '4px solid var(--rose-500)';
                setTimeout(() => tr.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 100);
            }

            row.forEach((val, idx) => {
                if (idx === rowidIdx) return;
                const td = document.createElement('td');
                td.innerText = val === null || val === undefined ? '' : val;
                tr.appendChild(td);
            });
            el.spreadsheetTbody.appendChild(tr);
        });

        // Clear highlight index after rendering
        state.highlightRowIndex = null;

        // Meta info
        const total = state.datasetInfo.n_rows;
        const from = (state.sheetPage - 1) * state.sheetLimit + 1;
        const to = Math.min(total, state.sheetPage * state.sheetLimit);
        el.sheetMetaInfo.innerText = `Showing ${from} - ${to} of ${total}`;
        el.sheetPageIndicator.innerText = `Page ${state.sheetPage}`;
        el.sheetPrevBtn.disabled = state.sheetPage === 1;
        el.sheetNextBtn.disabled = to >= total;
    }

    // SQL Query Console Sandbox
    function runSqlQueryConsole() {
        const query = el.sqlQueryInput.value;
        if (!query.strip) {
            // basic strip fallback
            if (!query.trim()) return;
        }

        el.sqlErrorOutput.classList.add('hidden');
        el.sqlResultsTable.classList.add('hidden');
        
        fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                el.sqlErrorOutput.innerText = data.error;
                el.sqlErrorOutput.classList.remove('hidden');
                el.queryMetaInfo.innerText = 'Rows fetched: 0 \u2022 Speed: 0ms';
                return;
            }

            el.queryMetaInfo.innerText = `Rows fetched: ${data.row_count} \u2022 Speed: ${data.execution_time_ms}ms`;
            
            // Draw Headers
            el.sqlResultsThead.innerHTML = '';
            const trH = document.createElement('tr');
            data.columns.forEach(col => {
                const th = document.createElement('th');
                th.innerText = col;
                trH.appendChild(th);
            });
            el.sqlResultsThead.appendChild(trH);

            // Draw Body
            el.sqlResultsTbody.innerHTML = '';
            if (data.rows.length === 0) {
                el.sqlResultsTbody.innerHTML = `<tr><td colspan="${data.columns.length}" style="text-align: center; color: var(--slate-400);">Query ran successfully. Zero rows returned.</td></tr>`;
            } else {
                data.rows.forEach(row => {
                    const tr = document.createElement('tr');
                    row.forEach(val => {
                        const td = document.createElement('td');
                        td.innerText = val === null || val === undefined ? '' : val;
                        tr.appendChild(td);
                    });
                    el.sqlResultsTbody.appendChild(tr);
                });
            }

            el.sqlResultsTable.classList.remove('hidden');
        })
        .catch(err => {
            el.sqlErrorOutput.innerText = err.message;
            el.sqlErrorOutput.classList.remove('hidden');
        });
    }

    // Dynamic Copilot Welcome Brief
    function generateWelcomeMessageBrief(filename, n_rows, n_cols, alerts, targetCol) {
        // Let's summarize alerts by severity or metric
        const criticalCount = alerts.filter(a => a.severity === 'high').length;
        const mediumCount = alerts.filter(a => a.severity === 'medium').length;
        
        // Let's list some key alert categories
        const missingDataAlerts = alerts.filter(a => a.category === 'Missing Data' || a.metric?.includes('missing')).length;
        const duplicateAlerts = alerts.filter(a => a.category === 'Duplicates' || a.metric?.includes('duplicate')).length;
        const skewAlerts = alerts.filter(a => a.category === 'Distribution' || a.metric?.includes('skew')).length;
        
        let alertsSummaryParts = [];
        if (criticalCount > 0) {
            const criticalTypes = [...new Set(alerts.filter(a => a.severity === 'high').map(a => {
                if (a.metric === 'duplicate_columns') return 'duplicate column';
                if (a.metric === 'constant_column') return 'constant';
                if (a.metric === 'all_missing') return 'entirely empty';
                if (a.metric === 'contradictory_rows') return 'contradictory rows';
                return 'critical anomalies';
            }))];
            alertsSummaryParts.push(`${criticalCount} critical (${criticalTypes.join(' + ')})`);
        }
        if (duplicateAlerts > 0) {
            const hasNearDup = alerts.some(a => a.metric === 'near_duplicate_rows');
            if (hasNearDup) alertsSummaryParts.push(`1 near-duplicate warning`);
        }
        if (missingDataAlerts > 0) {
            alertsSummaryParts.push(`${missingDataAlerts} missing data issue${missingDataAlerts > 1 ? 's' : ''}`);
        }
        
        let alertsText = '';
        if (alerts.length === 0) {
            alertsText = 'Found 0 alerts.';
        } else {
            alertsText = `Found ${alerts.length} alert${alerts.length > 1 ? 's' : ''}: ${alertsSummaryParts.join(', ') || 'various warnings'}.`;
        }

        let targetText = '';
        if (targetCol) {
            targetText = `Target '${targetCol}' selected — leakage and drift analysis enabled.`;
        } else {
            targetText = 'No target selected — leakage and drift analysis disabled.';
        }

        const msg = `👋 ${filename} loaded — ${n_rows} rows, ${n_cols} columns. ${alertsText} ${targetText} Where do you want to start?`;
        
        const chatArea = el.chatMessagesArea;
        if (chatArea) {
            chatArea.innerHTML = `
                <div class="msg msg-system">
                    <p>${msg}</p>
                </div>
            `;
        }
        
        state.chatHistory = [{ role: 'assistant', content: msg }];
    }

    // Dynamic Suggested Chips Generator
    function generateChips(alerts) {
        const chips = [];
        alerts.forEach(alert => {
            if (chips.length >= 3) return;
            const col = alert.column;
            const val = alert.value;
            const metric = alert.metric;
            
            if (metric === 'duplicate_columns') {
                chips.push(`Why is ${col} dangerous?`);
            } else if (metric === 'high_missing' || metric === 'moderate_missing') {
                const pct = Math.round(val * 100);
                chips.push(`How do I handle ${col} with ${pct}% nulls?`);
            } else if (metric === 'high_skew') {
                chips.push(`Should I log-transform ${col}?`);
            } else if (metric === 'near_duplicate_rows') {
                chips.push(`How can I resolve near-duplicate rows?`);
            } else if (metric === 'contradictory_rows') {
                chips.push(`Why do we have contradictory rows in ${col}?`);
            } else if (metric === 'negative_values') {
                chips.push(`How do I clean negative values in ${col}?`);
            } else if (metric === 'class_imbalance') {
                chips.push(`How do I fix class imbalance in ${col}?`);
            }
        });

        if (chips.length < 1) chips.push("What are the key alerts in this data?");
        if (chips.length < 2) chips.push("How should I impute missing cells?");
        if (chips.length < 3) chips.push("Write a cleaning python script");

        const finalChips = chips.slice(0, 3);
        const chipsContainer = document.querySelector('.chat-chips');
        if (chipsContainer) {
            chipsContainer.innerHTML = finalChips.map(c => `<button class="chat-chip-btn">${c}</button>`).join('\n');
        }
    }

    // LLM Chat Advisor
    function sendChatMessage() {
        const text = el.chatUserInput.value;
        if (!text.trim()) return;

        // Render user message
        const userDiv = document.createElement('div');
        userDiv.className = 'msg msg-user';
        userDiv.innerHTML = `<p>${text}</p>`;
        el.chatMessagesArea.appendChild(userDiv);
        el.chatUserInput.value = '';
        el.chatMessagesArea.scrollTop = el.chatMessagesArea.scrollHeight;

        state.chatHistory.push({ role: 'user', content: text });

        // Add a premium typing indicator loader bubble
        const loaderDiv = document.createElement('div');
        loaderDiv.className = 'msg msg-agent loading-bubble';
        loaderDiv.innerHTML = `<div class="typing-indicator"><span></span><span></span><span></span></div>`;
        el.chatMessagesArea.appendChild(loaderDiv);
        el.chatMessagesArea.scrollTop = el.chatMessagesArea.scrollHeight;

        // Call backend api
        fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: state.chatHistory })
        })
        .then(res => res.json())
        .then(data => {
            // Remove typing indicator bubble
            loaderDiv.remove();

            const reply = data.response;
            state.chatHistory.push({ role: 'assistant', content: reply });

            // Format response paragraphs and handle codeblocks nicely
            let formattedReply = reply;
            
            // Detect hidden structured JSON wrangler actions
            const jsonRegex = /```json\s*([\s\S]*?)\s*```/g;
            let match;
            let actionPayload = null;
            
            // We replace the JSON code blocks with a hidden div so they don't clutter the UI
            formattedReply = formattedReply.replace(jsonRegex, (matchStr, p1) => {
                try {
                    const parsed = JSON.parse(p1);
                    if (parsed.column || Array.isArray(parsed) || parsed.action) {
                        actionPayload = p1;
                        return `<div class="wrangler-action-json hidden" style="display:none;">${p1}</div>`;
                    }
                } catch(e) {}
                return matchStr; // If not valid action JSON, leave it as is
            });

            // Format code blocks
            formattedReply = formattedReply.replace(/```python\s*([\s\S]*?)\s*```/g, '<pre class="code-block python-code">$1</pre>');
            formattedReply = formattedReply.replace(/```\s*([\s\S]*?)\s*```/g, '<pre class="code-block">$1</pre>');
            formattedReply = formattedReply.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
            formattedReply = formattedReply.replace(/\n/g, '<br>');

            let buttonHtml = '';
            if (actionPayload) {
                const escapedPayload = actionPayload.replace(/"/g, '&quot;');
                buttonHtml = `<button class="apply-wrangler-btn" style="margin-top:10px; display:block;" data-action="${escapedPayload}">Apply in Wrangler ▶</button>`;
            }

            // Feedback action buttons
            const actionsHtml = `
                <div class="chat-actions" style="margin-top:8px; display:flex; gap:10px; align-items:center; opacity:0.85; border-top: 1px solid var(--slate-800); padding-top:6px; margin-top:8px;">
                    <button class="chat-action-btn thumbs-up" style="background:transparent; border:none; color:var(--slate-400); cursor:pointer; font-size:12px;" onclick="this.style.color='var(--emerald-400)';">👍</button>
                    <button class="chat-action-btn thumbs-down" style="background:transparent; border:none; color:var(--slate-400); cursor:pointer; font-size:12px;" onclick="this.style.color='var(--rose-400)';">👎</button>
                    <button class="chat-action-btn copy-btn" style="background:transparent; border:none; color:var(--slate-400); cursor:pointer; font-size:11px; display:inline-flex; align-items:center; gap:3px;">📋 Copy</button>
                    <button class="chat-action-btn save-btn" style="background:transparent; border:none; color:var(--slate-400); cursor:pointer; font-size:11px; display:inline-flex; align-items:center; gap:3px;">💾 Save to Report</button>
                </div>
            `;

            // Render agent message with scrollable constraints
            const agentDiv = document.createElement('div');
            agentDiv.className = 'msg msg-agent';
            agentDiv.style = 'max-height: 400px; overflow-y: auto;';
            agentDiv.innerHTML = `<p>${formattedReply}</p>${buttonHtml}${actionsHtml}`;
            el.chatMessagesArea.appendChild(agentDiv);
            el.chatMessagesArea.scrollTop = el.chatMessagesArea.scrollHeight;
        })
        .catch(err => {
            loaderDiv.remove();
            const errDiv = document.createElement('div');
            errDiv.className = 'msg msg-system';
            errDiv.innerHTML = `<p>Error: ${err.message}</p>`;
            el.chatMessagesArea.appendChild(errDiv);
        });
    }

    // ================= PHASE 1 INGESTION HANDLERS =================

    function loadSampleGallery() {
        if (!el.samplesGalleryContainer) return;
        el.samplesGalleryContainer.innerHTML = '<p class="text-muted" style="grid-column:1/-1; text-align:center;">Loading preloaded samples...</p>';
        
        fetch('/api/datasets/samples')
        .then(res => res.json())
        .then(data => {
            el.samplesGalleryContainer.innerHTML = '';
            data.samples.forEach(s => {
                const card = document.createElement('div');
                card.className = 'sample-card';
                
                const header = document.createElement('div');
                header.className = 'sample-card-header';
                
                const title = document.createElement('div');
                title.className = 'sample-card-title';
                title.innerText = s.name;
                header.appendChild(title);
                
                const badge = document.createElement('span');
                badge.className = `sample-badge badge-${s.badge.toLowerCase().replace(' ', '-')}`;
                badge.innerText = s.badge;
                header.appendChild(badge);
                
                card.appendChild(header);
                
                const desc = document.createElement('div');
                desc.className = 'sample-card-desc';
                desc.innerText = s.description;
                card.appendChild(desc);
                
                const meta = document.createElement('div');
                meta.className = 'sample-card-meta';
                meta.innerText = `${s.cols} Columns`;
                card.appendChild(meta);
                
                card.addEventListener('click', () => {
                    loadSampleDataset(s.name);
                });
                
                el.samplesGalleryContainer.appendChild(card);
            });
        })
        .catch(err => {
            el.samplesGalleryContainer.innerHTML = `<p style="grid-column:1/-1; text-align:center; color:var(--rose-500);">Failed to load samples: ${err.message}</p>`;
        });
    }

    function loadSampleDataset(name) {
        showLoading(`Loading sample dataset '${name}'...`);
        const form = new FormData();
        form.append('name', name);
        
        fetch('/api/datasets/samples/load', {
            method: 'POST',
            body: form
        })
        .then(res => {
            if (!res.ok) return res.json().then(e => { throw new Error(e.detail || "Failed to load sample") });
            return res.json();
        })
        .then(data => {
            // Update active state
            if (!state.datasets.find(d => d.id === data.dataset_id)) {
                state.datasets.push({
                    id: data.dataset_id,
                    filename: data.filename,
                    n_rows: data.n_rows,
                    n_columns: data.n_columns,
                    is_downsampled: data.is_downsampled,
                    downsample_enabled: data.downsample_enabled
                });
            }
            state.activeDatasetId = data.dataset_id;
            state.datasetInfo = data;
            state.wranglerSteps = [];
            state.splitResults = null;
            
            renderDatasetTabs();
            
            // Populate Target dropdown
            el.targetSelect.innerHTML = '<option value="">-- Select Target (Enables Leakage & Drift) --</option>';
            el.splitCompareColSelect.innerHTML = '<option value="">-- Select Feature --</option>';
            el.wrangleColSelect.innerHTML = '';
            el.bivariateXSelect.innerHTML = '';
            el.bivariateYSelect.innerHTML = '';
            el.datetimeColSelect.innerHTML = '';
            el.textColSelect.innerHTML = '';

            data.columns.forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.innerText = col;
                el.targetSelect.appendChild(opt.cloneNode(true));
                el.splitCompareColSelect.appendChild(opt.cloneNode(true));
                el.wrangleColSelect.appendChild(opt.cloneNode(true));
                el.bivariateXSelect.appendChild(opt.cloneNode(true));
                el.bivariateYSelect.appendChild(opt.cloneNode(true));
            });

            el.app.className = 'dashboard-mode';
            el.uploadScreen.classList.add('hidden');
            el.dashboard.classList.remove('hidden');

            triggerAnalysis();
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    function submitDatabaseConnection() {
        const dbType = el.dbTypeSelect.value;
        const host = el.dbHostInput.value.strip ? el.dbHostInput.value.strip() : el.dbHostInput.value.trim();
        const port = parseInt(el.dbPortInput.value) || 5432;
        const user = el.dbUserInput.value;
        const pass = el.dbPassInput.value;
        const database = el.dbNameInput.value;
        const query = el.dbSqlQueryInput.value;
        
        if (!host || !user || !database || !query) {
            showStatusMessage("Please fill in all database fields, query input is required.", "error");
            return;
        }
        
        showLoading("Connecting and querying database...");
        fetch('/api/datasets/db-connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                db_type: dbType,
                host: host,
                port: port,
                username: user,
                password: pass,
                database: database,
                query: query
            })
        })
        .then(res => {
            if (!res.ok) return res.json().then(e => { throw new Error(e.detail || "Query execution failed") });
            return res.json();
        })
        .then(data => {
            if (!state.datasets.find(d => d.id === data.dataset_id)) {
                state.datasets.push({
                    id: data.dataset_id,
                    filename: data.filename,
                    n_rows: data.n_rows,
                    n_columns: data.n_columns,
                    is_downsampled: data.is_downsampled,
                    downsample_enabled: data.downsample_enabled
                });
            }
            state.activeDatasetId = data.dataset_id;
            state.datasetInfo = data;
            state.wranglerSteps = [];
            state.splitResults = null;
            
            renderDatasetTabs();
            
            el.targetSelect.innerHTML = '<option value="">-- Select Target (Enables Leakage & Drift) --</option>';
            el.splitCompareColSelect.innerHTML = '<option value="">-- Select Feature --</option>';
            el.wrangleColSelect.innerHTML = '';
            el.bivariateXSelect.innerHTML = '';
            el.bivariateYSelect.innerHTML = '';
            el.datetimeColSelect.innerHTML = '';
            el.textColSelect.innerHTML = '';

            data.columns.forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.innerText = col;
                el.targetSelect.appendChild(opt.cloneNode(true));
                el.splitCompareColSelect.appendChild(opt.cloneNode(true));
                el.wrangleColSelect.appendChild(opt.cloneNode(true));
                el.bivariateXSelect.appendChild(opt.cloneNode(true));
                el.bivariateYSelect.appendChild(opt.cloneNode(true));
            });

            el.app.className = 'dashboard-mode';
            el.uploadScreen.classList.add('hidden');
            el.dashboard.classList.remove('hidden');

            triggerAnalysis();
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    function submitRestApiConnection() {
        const url = el.apiUrlInput.value.trim ? el.apiUrlInput.value.trim() : el.apiUrlInput.value;
        const path = el.apiPathInput.value.trim ? el.apiPathInput.value.trim() : el.apiPathInput.value;
        
        if (!url) {
            showStatusMessage("API GET URL is required.", "error");
            return;
        }
        
        showLoading("Fetching REST API URL payload...");
        fetch('/api/datasets/url-load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                jsonpath: path || null
            })
        })
        .then(res => {
            if (!res.ok) return res.json().then(e => { throw new Error(e.detail || "URL fetch failed") });
            return res.json();
        })
        .then(data => {
            if (!state.datasets.find(d => d.id === data.dataset_id)) {
                state.datasets.push({
                    id: data.dataset_id,
                    filename: data.filename,
                    n_rows: data.n_rows,
                    n_columns: data.n_columns,
                    is_downsampled: data.is_downsampled,
                    downsample_enabled: data.downsample_enabled
                });
            }
            state.activeDatasetId = data.dataset_id;
            state.datasetInfo = data;
            state.wranglerSteps = [];
            state.splitResults = null;
            
            renderDatasetTabs();
            
            el.targetSelect.innerHTML = '<option value="">-- Select Target (Enables Leakage & Drift) --</option>';
            el.splitCompareColSelect.innerHTML = '<option value="">-- Select Feature --</option>';
            el.wrangleColSelect.innerHTML = '';
            el.bivariateXSelect.innerHTML = '';
            el.bivariateYSelect.innerHTML = '';
            el.datetimeColSelect.innerHTML = '';
            el.textColSelect.innerHTML = '';

            data.columns.forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.innerText = col;
                el.targetSelect.appendChild(opt.cloneNode(true));
                el.splitCompareColSelect.appendChild(opt.cloneNode(true));
                el.wrangleColSelect.appendChild(opt.cloneNode(true));
                el.bivariateXSelect.appendChild(opt.cloneNode(true));
                el.bivariateYSelect.appendChild(opt.cloneNode(true));
            });

            el.app.className = 'dashboard-mode';
            el.uploadScreen.classList.add('hidden');
            el.dashboard.classList.remove('hidden');

            triggerAnalysis();
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    function submitClipboardConnection() {
        const text = el.clipboardTextArea.value;
        if (!text || !text.trim()) {
            showStatusMessage("Pasted tabular text block is required.", "error");
            return;
        }
        
        showLoading("Parsing clipboard records...");
        const form = new FormData();
        form.append('text', text);
        
        fetch('/api/datasets/clipboard-load', {
            method: 'POST',
            body: form
        })
        .then(res => {
            if (!res.ok) return res.json().then(e => { throw new Error(e.detail || "Clipboard parsing failed") });
            return res.json();
        })
        .then(data => {
            if (!state.datasets.find(d => d.id === data.dataset_id)) {
                state.datasets.push({
                    id: data.dataset_id,
                    filename: data.filename,
                    n_rows: data.n_rows,
                    n_columns: data.n_columns,
                    is_downsampled: data.is_downsampled,
                    downsample_enabled: data.downsample_enabled
                });
            }
            state.activeDatasetId = data.dataset_id;
            state.datasetInfo = data;
            state.wranglerSteps = [];
            state.splitResults = null;
            
            renderDatasetTabs();
            
            el.targetSelect.innerHTML = '<option value="">-- Select Target (Enables Leakage & Drift) --</option>';
            el.splitCompareColSelect.innerHTML = '<option value="">-- Select Feature --</option>';
            el.wrangleColSelect.innerHTML = '';
            el.bivariateXSelect.innerHTML = '';
            el.bivariateYSelect.innerHTML = '';
            el.datetimeColSelect.innerHTML = '';
            el.textColSelect.innerHTML = '';

            data.columns.forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.innerText = col;
                el.targetSelect.appendChild(opt.cloneNode(true));
                el.splitCompareColSelect.appendChild(opt.cloneNode(true));
                el.wrangleColSelect.appendChild(opt.cloneNode(true));
                el.bivariateXSelect.appendChild(opt.cloneNode(true));
                el.bivariateYSelect.appendChild(opt.cloneNode(true));
            });

            el.app.className = 'dashboard-mode';
            el.uploadScreen.classList.add('hidden');
            el.dashboard.classList.remove('hidden');

            triggerAnalysis();
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    function openMergeWizard() {
        if (state.datasets.length < 2) {
            showStatusMessage("Merge Wizard requires at least 2 datasets loaded in memory.", "error");
            return;
        }
        
        // Populate A and B datasets select options
        el.mergeDatasetA.innerHTML = '';
        el.mergeDatasetB.innerHTML = '';
        
        state.datasets.forEach(ds => {
            const opt = document.createElement('option');
            opt.value = ds.id;
            opt.innerText = `${ds.filename} (${ds.n_rows} rows)`;
            el.mergeDatasetA.appendChild(opt.cloneNode(true));
            el.mergeDatasetB.appendChild(opt.cloneNode(true));
        });
        
        // Match selection defaults
        if (state.activeDatasetId) {
            el.mergeDatasetA.value = state.activeDatasetId;
            // Select second one for Dataset B if available
            const other = state.datasets.find(d => d.id !== state.activeDatasetId);
            if (other) el.mergeDatasetB.value = other.id;
        }
        
        el.mergeTypeSelect.value = 'join';
        el.mergeJoinFields.classList.remove('hidden');
        
        populateMergeWizardKeys();
        el.mergeWizardModal.classList.remove('hidden');
    }

    function populateMergeWizardKeys() {
        const idA = el.mergeDatasetA.value;
        const idB = el.mergeDatasetB.value;
        
        if (!idA || !idB) return;
        
        // Fetch matching column choices dynamically
        showLoading("Resolving dataset features schema...");
        fetch('/api/datasets')
        .then(res => res.json())
        .then(data => {
            hideLoading();
            const list = data.datasets;
            const dsA = list.find(d => d.id === idA);
            const dsB = list.find(d => d.id === idB);
            
            el.mergeLeftKey.innerHTML = '';
            el.mergeRightKey.innerHTML = '';
            
            if (dsA) {
                // Fetch details from state or fetch schema endpoint if needed
                // For simplicity, query the current active dataset state if matches
                let colsA = [];
                if (state.activeDatasetId === idA && state.datasetInfo) {
                    colsA = state.datasetInfo.columns;
                } else {
                    // Fallback parse columns
                    colsA = state.datasets.find(d => d.id === idA) ? state.datasetInfo.columns : [];
                }
                
                // If columns not fully loaded in client, use current dropdown items
                if (colsA.length === 0) {
                    colsA = Array.from(el.targetSelect.options).map(o => o.value).filter(v => v !== '');
                }
                
                colsA.forEach(col => {
                    const opt = document.createElement('option');
                    opt.value = col;
                    opt.innerText = col;
                    el.mergeLeftKey.appendChild(opt);
                });
            }
            
            if (dsB) {
                let colsB = [];
                if (state.activeDatasetId === idB && state.datasetInfo) {
                    colsB = state.datasetInfo.columns;
                } else {
                    // Fallback dropdown items
                    colsB = Array.from(el.targetSelect.options).map(o => o.value).filter(v => v !== '');
                }
                
                colsB.forEach(col => {
                    const opt = document.createElement('option');
                    opt.value = col;
                    opt.innerText = col;
                    el.mergeRightKey.appendChild(opt);
                });
            }
        })
        .catch(err => {
            hideLoading();
            console.error("Failed to populate keys:", err);
        });
    }

    function submitMergeWizard() {
        const idA = el.mergeDatasetA.value;
        const idB = el.mergeDatasetB.value;
        const mType = el.mergeTypeSelect.value;
        const how = el.mergeJoinHow.value;
        const leftKey = el.mergeLeftKey.value;
        const rightKey = el.mergeRightKey.value;
        
        if (idA === idB) {
            showStatusMessage("Merge wizard requires selecting two distinct datasets.", "error");
            return;
        }
        
        showLoading("Merging and alignment indexing...");
        fetch('/api/datasets/merge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dataset_a_id: idA,
                dataset_b_id: idB,
                merge_type: mType,
                join_how: how,
                left_on: mType === 'join' ? leftKey : null,
                right_on: mType === 'join' ? rightKey : null
            })
        })
        .then(res => {
            if (!res.ok) return res.json().then(e => { throw new Error(e.detail || "Merge failed") });
            return res.json();
        })
        .then(data => {
            if (!state.datasets.find(d => d.id === data.dataset_id)) {
                state.datasets.push({
                    id: data.dataset_id,
                    filename: data.filename,
                    n_rows: data.n_rows,
                    n_columns: data.n_columns,
                    is_downsampled: data.is_downsampled,
                    downsample_enabled: data.downsample_enabled
                });
            }
            state.activeDatasetId = data.dataset_id;
            state.datasetInfo = data;
            state.wranglerSteps = [];
            state.splitResults = null;
            
            renderDatasetTabs();
            el.mergeWizardModal.classList.add('hidden');
            
            el.targetSelect.innerHTML = '<option value="">-- Select Target (Enables Leakage & Drift) --</option>';
            el.splitCompareColSelect.innerHTML = '<option value="">-- Select Feature --</option>';
            el.wrangleColSelect.innerHTML = '';
            el.bivariateXSelect.innerHTML = '';
            el.bivariateYSelect.innerHTML = '';
            el.datetimeColSelect.innerHTML = '';
            el.textColSelect.innerHTML = '';

            data.columns.forEach(col => {
                const opt = document.createElement('option');
                opt.value = col;
                opt.innerText = col;
                el.targetSelect.appendChild(opt.cloneNode(true));
                el.splitCompareColSelect.appendChild(opt.cloneNode(true));
                el.wrangleColSelect.appendChild(opt.cloneNode(true));
                el.bivariateXSelect.appendChild(opt.cloneNode(true));
                el.bivariateYSelect.appendChild(opt.cloneNode(true));
            });

            triggerAnalysis();
        })
        .catch(err => {
            hideLoading();
            showStatusMessage(err.message, "error");
        });
    }

    // --- PHASE 2 CORE DIAGNOSTICS & TAGGERS FUNCTIONS ---
    function handleSemanticCastOverride(col, newType) {
        if (!state.wranglerSteps) state.wranglerSteps = [];
        const existingIdx = state.wranglerSteps.findIndex(s => s.column === col && s.action === 'cast');
        if (existingIdx !== -1) {
            state.wranglerSteps[existingIdx].strategy = newType;
        } else {
            state.wranglerSteps.push({
                column: col,
                action: 'cast',
                strategy: newType
            });
        }
        renderWranglerSteps();
        executeWranglePipeline();
    }

    function applySingleDowncast(col, dtype) {
        if (!state.wranglerSteps) state.wranglerSteps = [];
        const existingIdx = state.wranglerSteps.findIndex(s => s.column === col && s.action === 'cast');
        if (existingIdx !== -1) {
            state.wranglerSteps[existingIdx].strategy = dtype;
        } else {
            state.wranglerSteps.push({
                column: col,
                action: 'cast',
                strategy: dtype
            });
        }
        renderWranglerSteps();
        executeWranglePipeline();
    }

    function applyAllDowncasts() {
        const ram = state.analysisResults.results.alerts.ram_optimization;
        if (!ram || !ram.recommendations || ram.recommendations.length === 0) return;
        if (!state.wranglerSteps) state.wranglerSteps = [];
        
        ram.recommendations.forEach(rec => {
            const existingIdx = state.wranglerSteps.findIndex(s => s.column === rec.column && s.action === 'cast');
            if (existingIdx !== -1) {
                state.wranglerSteps[existingIdx].strategy = rec.suggested_dtype;
            } else {
                state.wranglerSteps.push({
                    column: rec.column,
                    action: 'cast',
                    strategy: rec.suggested_dtype
                });
            }
        });
        renderWranglerSteps();
        executeWranglePipeline();
    }

    function applySingleGdprWrangle(col, action) {
        if (!state.wranglerSteps) state.wranglerSteps = [];
        state.wranglerSteps.push({
            column: col,
            action: action,
            strategy: ''
        });
        renderWranglerSteps();
        executeWranglePipeline();
    }

    function renderRadarChart() {
        const alerts = state.analysisResults.results.alerts;
        if (!alerts || !alerts.integrity_breakdown) return;
        const breakdown = alerts.integrity_breakdown;
        
        const r = [
            breakdown.Completeness,
            breakdown.Uniqueness,
            breakdown.Consistency,
            breakdown.Validity,
            breakdown.Timeliness,
            breakdown.Accuracy,
            breakdown.Completeness
        ];
        const theta = [
            'Completeness',
            'Uniqueness',
            'Consistency',
            'Validity',
            'Timeliness',
            'Accuracy',
            'Completeness'
        ];
        
        const data = [{
            type: 'scatterpolar',
            r: r,
            theta: theta,
            fill: 'toself',
            fillcolor: 'rgba(99, 102, 241, 0.25)',
            line: {
                color: 'rgba(99, 102, 241, 1)',
                width: 2
            },
            marker: {
                color: 'rgba(99, 102, 241, 1)',
                size: 6
            }
        }];
        
        const layout = {
            polar: {
                radialaxis: {
                    visible: true,
                    range: [0, 100],
                    color: '#94a3b8',
                    gridcolor: '#334155'
                },
                angularaxis: {
                    color: '#94a3b8',
                    gridcolor: '#334155'
                },
                bgcolor: 'rgba(15, 23, 42, 0.4)'
            },
            showlegend: false,
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            margin: { t: 30, b: 30, l: 40, r: 40 }
        };
        
        Plotly.newPlot('integrity-radar-chart', data, layout, {responsive: true, displayModeBar: false});
    }

    function renderRamOptimization() {
        const ram = state.analysisResults.results.alerts.ram_optimization;
        if (!ram) {
            el.ramSavingsBadge.innerText = "Savings: 0 KB";
            el.ramOptTbody.innerHTML = '<tr><td colspan="4" class="text-muted" style="text-align: center; padding: 15px;">No recommendations available.</td></tr>';
            return;
        }
        
        const totalSavings = ram.total_savings_bytes || 0;
        if (totalSavings < 1024) {
            el.ramSavingsBadge.innerText = `Savings: ${totalSavings} Bytes`;
        } else if (totalSavings < 1024 * 1024) {
            el.ramSavingsBadge.innerText = `Savings: ${(totalSavings / 1024).toFixed(1)} KB`;
        } else {
            el.ramSavingsBadge.innerText = `Savings: ${(totalSavings / (1024 * 1024)).toFixed(1)} MB`;
        }
        
        el.ramOptTbody.innerHTML = '';
        if (!ram.recommendations || ram.recommendations.length === 0) {
            el.ramOptTbody.innerHTML = '<tr><td colspan="4" class="text-success" style="text-align: center; padding: 25px; font-weight: 500;">All columns are fully memory optimized!</td></tr>';
            return;
        }
        
        ram.recommendations.forEach(rec => {
            const tr = document.createElement('tr');
            const savings = rec.savings_bytes < 1024 ? `${rec.savings_bytes} B` : `${(rec.savings_bytes / 1024).toFixed(1)} KB`;
            tr.innerHTML = `
                <td><strong>${rec.column}</strong></td>
                <td><span class="code">${rec.current_dtype}</span></td>
                <td><span class="code text-success">${rec.suggested_dtype}</span></td>
                <td><button class="btn btn-secondary btn-xs btn-apply-downcast" data-col="${rec.column}" data-dtype="${rec.suggested_dtype}" style="padding: 2px 6px; font-size:11px;">Downcast</button></td>
            `;
            el.ramOptTbody.appendChild(tr);
        });
        
        document.querySelectorAll('.btn-apply-downcast').forEach(btn => {
            btn.addEventListener('click', function() {
                const col = this.getAttribute('data-col');
                const dtype = this.getAttribute('data-dtype');
                applySingleDowncast(col, dtype);
            });
        });
    }

    function renderGdprAudit() {
        const piiList = state.analysisResults.results.alerts.gdpr_pii || [];
        el.gdprPiiCount.innerText = piiList.length;
        el.gdprPiiCount.className = piiList.length > 0 ? 'sidebar-badge' : 'sidebar-badge hidden';
        
        el.gdprPiiTbody.innerHTML = '';
        if (piiList.length === 0) {
            el.gdprPiiTbody.innerHTML = '<tr><td colspan="4" class="text-success" style="text-align: center; padding: 25px; font-weight: 500;">No PII or sensitive features detected!</td></tr>';
            return;
        }
        
        piiList.forEach(pii => {
            const tr = document.createElement('tr');
            let btnText = pii.suggested_action === 'Mask' ? 'Mask (****)' : (pii.suggested_action === 'Hash' ? 'Hash (SHA256)' : 'Drop Column');
            let actionVal = pii.suggested_action === 'Mask' ? 'mask_pii' : (pii.suggested_action === 'Hash' ? 'hash_pii' : 'drop');
            
            tr.innerHTML = `
                <td><strong>${pii.column}</strong></td>
                <td><span class="text-warning">${pii.reason}</span></td>
                <td><span class="badge badge-warning">${pii.suggested_action}</span></td>
                <td>
                    <div style="display:flex; gap: 8px;">
                        <button class="btn btn-primary btn-xs btn-gdpr-action" data-col="${pii.column}" data-action="${actionVal}" style="padding: 2px 6px; font-size:11px;">Apply ${pii.suggested_action}</button>
                        <button class="btn btn-secondary btn-xs btn-gdpr-action" data-col="${pii.column}" data-action="drop" style="padding: 2px 6px; font-size:11px; border-color: var(--rose-500); color: var(--rose-400);">Drop</button>
                    </div>
                </td>
            `;
            el.gdprPiiTbody.appendChild(tr);
        });
        
        document.querySelectorAll('.btn-gdpr-action').forEach(btn => {
            btn.addEventListener('click', function() {
                const col = this.getAttribute('data-col');
                const act = this.getAttribute('data-action');
                applySingleGdprWrangle(col, act);
            });
        });
    }

    function renderBenfordLaw() {
        const benford = state.analysisResults.results.alerts.benford_law || {};
        
        el.benfordColSelect.innerHTML = '';
        const cols = Object.keys(benford);
        if (cols.length === 0) {
            el.benfordColSelect.innerHTML = '<option value="">-- No suitable numeric features --</option>';
            document.getElementById('benford-chart').innerHTML = '<div class="text-muted" style="text-align: center; padding: 50px;">Benford\'s Law analysis requires numeric columns spanning at least 1.5 orders of magnitude (e.g. populations, sizes, prices).</div>';
            return;
        }
        
        cols.forEach(col => {
            const opt = document.createElement('option');
            opt.value = col;
            opt.innerText = col;
            el.benfordColSelect.appendChild(opt);
        });
        
        drawBenfordPlot();
        
        el.benfordColSelect.removeEventListener('change', drawBenfordPlot);
        el.benfordColSelect.addEventListener('change', drawBenfordPlot);
    }

    function drawBenfordPlot() {
        const col = el.benfordColSelect.value;
        const benford = state.analysisResults.results.alerts.benford_law || {};
        if (!col || !benford[col]) return;
        
        const actual = benford[col].actual;
        const theoretical = benford[col].theoretical;
        
        const x = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];
        const yActual = x.map(digit => actual[digit] * 100);
        const yTheoretical = x.map(digit => theoretical[digit] * 100);
        
        const trace1 = {
            x: x,
            y: yActual,
            name: 'Actual Frequency',
            type: 'bar',
            marker: {
                color: 'rgba(99, 102, 241, 0.7)',
                line: { color: 'rgba(99, 102, 241, 1)', width: 1 }
            }
        };
        
        const trace2 = {
            x: x,
            y: yTheoretical,
            name: 'Benford\'s Expected',
            type: 'scatter',
            mode: 'lines+markers',
            line: { color: 'rgba(239, 68, 68, 1)', width: 2, dash: 'dash' },
            marker: { color: 'rgba(239, 68, 68, 1)', size: 6 }
        };
        
        const layout = {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            margin: { t: 40, b: 40, l: 50, r: 20 },
            xaxis: {
                title: 'First Significant Digit',
                color: '#94a3b8',
                gridcolor: '#1e293b'
            },
            yaxis: {
                title: 'Percentage (%)',
                color: '#94a3b8',
                gridcolor: '#1e293b'
            },
            legend: {
                font: { color: '#94a3b8' }
            }
        };
        
        Plotly.newPlot('benford-chart', [trace1, trace2], layout, {responsive: true, displayModeBar: false});
    }

    function updateHypothesisFields() {
        const testType = el.hypTestType ? el.hypTestType.value : '';
        const columns = state.datasetInfo ? state.datasetInfo.columns : [];
        const dtypes = state.datasetInfo ? state.datasetInfo.dtypes : {};
        const results = state.analysisResults ? state.analysisResults.results : null;
        
        if (!el.hypCol1 || !el.hypCol2) return;
        
        el.hypCol1.innerHTML = '';
        el.hypCol2.innerHTML = '';
        
        function isNumeric(col) {
            if (!results || !results.distributions || !results.distributions.features) {
                const dt = dtypes[col] || '';
                return dt.includes('int') || dt.includes('float') || dt.includes('double');
            }
            return results.distributions.features[col]?.type === 'numerical';
        }
        
        const numericCols = columns.filter(c => isNumeric(c));
        const categoricalCols = columns.filter(c => !isNumeric(c));
        
        el.hypCol2Group.classList.remove('hidden');
        el.hypPopMeanGroup.classList.add('hidden');
        
        if (testType === 't_test_1sample') {
            el.hypCol1Label.innerText = "Numerical Variable (Col A)";
            numericCols.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.innerText = c;
                el.hypCol1.appendChild(opt);
            });
            el.hypCol2Group.classList.add('hidden');
            el.hypPopMeanGroup.classList.remove('hidden');
            
        } else if (testType === 't_test_ind') {
            el.hypCol1Label.innerText = "Numerical Variable (Col A)";
            numericCols.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.innerText = c;
                el.hypCol1.appendChild(opt);
            });
            
            el.hypCol2Label.innerText = "Grouping Variable (Col B - Binary)";
            const binaryCols = categoricalCols.filter(c => {
                const feat = results ? results.distributions.features[c] : null;
                return feat ? feat.unique_count === 2 : true;
            });
            const targetCats = binaryCols.length > 0 ? binaryCols : categoricalCols;
            targetCats.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.innerText = c;
                el.hypCol2.appendChild(opt);
            });
            
        } else if (testType === 't_test_paired') {
            el.hypCol1Label.innerText = "Numerical Variable A";
            numericCols.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.innerText = c;
                el.hypCol1.appendChild(opt);
            });
            
            el.hypCol2Label.innerText = "Numerical Variable B";
            numericCols.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.innerText = c;
                el.hypCol2.appendChild(opt);
            });
            
        } else if (testType === 'anova' || testType === 'kruskal') {
            el.hypCol1Label.innerText = "Numerical Variable (Col A)";
            numericCols.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.innerText = c;
                el.hypCol1.appendChild(opt);
            });
            
            el.hypCol2Label.innerText = "Categorical Grouping Variable (Col B)";
            categoricalCols.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.innerText = c;
                el.hypCol2.appendChild(opt);
            });
            
        } else if (testType === 'shapiro') {
            el.hypCol1Label.innerText = "Numerical Variable";
            numericCols.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.innerText = c;
                el.hypCol1.appendChild(opt);
            });
            el.hypCol2Group.classList.add('hidden');
            
        } else if (testType === 'chisq') {
            el.hypCol1Label.innerText = "Categorical Variable A";
            categoricalCols.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.innerText = c;
                el.hypCol1.appendChild(opt);
            });
            
            el.hypCol2Label.innerText = "Categorical Variable B";
            categoricalCols.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.innerText = c;
                el.hypCol2.appendChild(opt);
            });
        }
    }

    function runHypothesisTestInCenter() {
        const testType = el.hypTestType.value;
        const col1 = el.hypCol1.value;
        const col2 = el.hypCol2.value;
        const popMean = parseFloat(el.hypPopMean.value) || 0.0;
        const alpha = parseFloat(el.hypConfidence.value) || 0.05;
        
        if (!col1) {
            showStatusMessage("Please select a target variable.", "error");
            return;
        }

        el.hypResultsEmpty.classList.add('hidden');
        el.hypResultsContent.classList.add('hidden');
        document.getElementById('hyp-results-card').querySelector('.card-title').innerText = 'Running statistical test...';

        fetch('/api/hypothesis/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Dataset-Id': state.activeDatasetId
            },
            body: JSON.stringify({
                test_type: testType,
                col1: col1,
                col2: col2 || null,
                pop_mean: popMean,
                alpha: alpha
            })
        })
        .then(res => res.json())
        .then(data => {
            document.getElementById('hyp-results-card').querySelector('.card-title').innerText = 'Test Results';
            if (data.status === 'error') {
                el.hypResultsEmpty.innerText = data.message;
                el.hypResultsEmpty.classList.remove('hidden');
                return;
            }

            el.hypResStat.innerText = typeof data.statistic === 'number' ? data.statistic.toFixed(4) : data.statistic;
            el.hypResPvalue.innerText = typeof data.p_value === 'number' ? (data.p_value < 0.001 ? data.p_value.toExponential(4) : data.p_value.toFixed(5)) : data.p_value;
            el.hypResInterpretation.innerText = data.interpretation;
            
            let powerHtml = `<strong>Achieved/Recommended sample sizes:</strong><br>${data.power_recommendation}`;
            if (data.effect_size) {
                powerHtml = `<strong>Effect Size (${data.effect_size.name}):</strong> <span class="text-indigo-400 font-semibold" style="color: #8b5cf6;">${data.effect_size.value.toFixed(3)} (${data.effect_size.interpretation})</span><br>` + powerHtml;
            }
            el.hypResPower.innerHTML = powerHtml;
            
            el.hypResultsContent.classList.remove('hidden');

            drawHypothesisPlot(data.plot_data, col1, col2);
        })
        .catch(err => {
            document.getElementById('hyp-results-card').querySelector('.card-title').innerText = 'Test Results';
            el.hypResultsEmpty.innerText = "Error executing test: " + err.message;
            el.hypResultsEmpty.classList.remove('hidden');
        });
    }

    function drawHypothesisPlot(plotData, col1, col2) {
        const chartDiv = el.hypPlotlyChart;
        if (!plotData) {
            chartDiv.innerHTML = '<div class="text-muted" style="text-align: center; padding: 40px;">No visualization available for this test.</div>';
            return;
        }

        let traces = [];
        let layout = {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            margin: { t: 30, b: 40, l: 50, r: 20 },
            xaxis: { tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)', title: { text: col1, font: { color: '#94a3b8' } } },
            yaxis: { tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' }
        };

        if (plotData.type === 'distribution_vs_line') {
            traces.push({
                x: plotData.values,
                type: 'histogram',
                name: 'Sample Distribution',
                marker: { color: 'rgba(99, 102, 241, 0.4)', line: { color: '#6366f1', width: 1 } }
            });
            
            layout.shapes = [
                {
                    type: 'line',
                    xref: 'x',
                    yref: 'paper',
                    x0: plotData.line_val,
                    y0: 0,
                    x1: plotData.line_val,
                    y1: 1,
                    line: { color: '#ef4444', width: 2, dash: 'dash' }
                },
                {
                    type: 'line',
                    xref: 'x',
                    yref: 'paper',
                    x0: plotData.mean_val,
                    y0: 0,
                    x1: plotData.mean_val,
                    y1: 1,
                    line: { color: '#10b981', width: 2 }
                }
            ];
            
            layout.annotations = [
                {
                    x: plotData.line_val,
                    y: 0.9,
                    yref: 'paper',
                    text: `H0 Mean: ${plotData.line_val}`,
                    showarrow: true,
                    arrowhead: 2,
                    arrowcolor: '#ef4444',
                    font: { color: '#ef4444', size: 9 },
                    bgcolor: 'rgba(15,23,42,0.8)'
                },
                {
                    x: plotData.mean_val,
                    y: 0.7,
                    yref: 'paper',
                    text: `Sample Mean: ${plotData.mean_val.toFixed(3)}`,
                    showarrow: true,
                    arrowhead: 2,
                    arrowcolor: '#10b981',
                    font: { color: '#10b981', size: 9 },
                    bgcolor: 'rgba(15,23,42,0.8)'
                }
            ];
            layout.showlegend = false;

        } else if (plotData.type === 'grouped_box') {
            traces.push({
                y: plotData.group1_values,
                type: 'box',
                name: plotData.group1_name,
                marker: { color: '#06b6d4' }
            });
            traces.push({
                y: plotData.group2_values,
                type: 'box',
                name: plotData.group2_name,
                marker: { color: '#8b5cf6' }
            });
            layout.xaxis = { title: { text: col2, font: { color: '#94a3b8' } } };
            layout.yaxis = { title: { text: col1, font: { color: '#94a3b8' } } };
            layout.showlegend = false;

        } else if (plotData.type === 'paired_scatter') {
            traces.push({
                x: plotData.x,
                y: plotData.y,
                mode: 'markers',
                type: 'scatter',
                marker: { color: 'rgba(16, 185, 129, 0.6)', size: 7 }
            });
            
            const minVal = Math.min(...plotData.x, ...plotData.y);
            const maxVal = Math.max(...plotData.x, ...plotData.y);
            traces.push({
                x: [minVal, maxVal],
                y: [minVal, maxVal],
                mode: 'lines',
                type: 'scatter',
                name: 'Equal Line',
                line: { color: '#cbd5e1', dash: 'dash', width: 1 }
            });
            
            layout.xaxis = { title: { text: plotData.labels[0], font: { color: '#94a3b8' } }, tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' };
            layout.yaxis = { title: { text: plotData.labels[1], font: { color: '#94a3b8' } }, tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' };
            layout.showlegend = false;

        } else if (plotData.type === 'multi_group_box') {
            plotData.groups.forEach(g => {
                traces.push({
                    y: g.values,
                    type: 'box',
                    name: g.name
                });
            });
            layout.xaxis = { title: { text: col2, font: { color: '#94a3b8' } }, tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' };
            layout.yaxis = { title: { text: col1, font: { color: '#94a3b8' } }, tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' };
            layout.showlegend = false;

        } else if (plotData.type === 'qq_plot') {
            traces.push({
                x: plotData.x,
                y: plotData.y,
                mode: 'markers',
                type: 'scatter',
                name: 'Sample points',
                marker: { color: '#8b5cf6', size: 5 }
            });
            
            const minX = Math.min(...plotData.x);
            const maxX = Math.max(...plotData.x);
            const n = plotData.y.length;
            const q25_y = plotData.y[Math.floor(n * 0.25)];
            const q75_y = plotData.y[Math.floor(n * 0.75)];
            const q25_x = -0.674;
            const q75_x = 0.674;
            const slope = (q75_y - q25_y) / (q75_x - q25_x);
            const intercept = q25_y - slope * q25_x;
            
            traces.push({
                x: [minX, maxX],
                y: [slope * minX + intercept, slope * maxX + intercept],
                mode: 'lines',
                type: 'scatter',
                name: 'Normal ref',
                line: { color: '#ef4444' }
            });
            
            layout.xaxis = { title: { text: 'Theoretical Quantiles', font: { color: '#94a3b8' } }, tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' };
            layout.yaxis = { title: { text: 'Sample Quantiles', font: { color: '#94a3b8' } }, tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' };
            layout.showlegend = false;

        } else if (plotData.type === 'contingency_heatmap') {
            traces.push({
                z: plotData.z,
                x: plotData.x,
                y: plotData.y,
                type: 'heatmap',
                colorscale: 'Blues'
            });
            
            layout.xaxis = { title: { text: col2, font: { color: '#94a3b8' } }, tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' };
            layout.yaxis = { title: { text: col1, font: { color: '#94a3b8' } }, tickcolor: '#94a3b8', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(255,255,255,0.05)' };
        }

        Plotly.newPlot(chartDiv, traces, layout, { responsive: true, displayModeBar: false });
    }

    // Trigger initialization on DOM Load
    document.addEventListener('DOMContentLoaded', init);
})();