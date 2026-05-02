BOOKING_CSS = """
<style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0.3rem !important;
        max-width: 98% !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 3px !important;
        background: #f0f4ff !important;
        border-radius: 8px !important;
        padding: 3px !important;
        margin-bottom: 0px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px !important;
        padding: 4px 14px !important;
        font-weight: 600 !important;
        font-size: 0.83rem !important;
        color: #444 !important;
    }
    .stTabs [aria-selected="true"] {
        background: #003399 !important;
        color: white !important;
    }

    /* Form container */
    div[data-testid="stForm"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
    }

    /* Headings */
    h2 { font-size: 1.25rem !important; margin-bottom: 2px !important; margin-top: 0 !important; color: #111 !important; }
    h3 { font-size: 1rem !important;   margin-bottom: 2px !important; margin-top: 0 !important; color: #222 !important; }
    h4 { font-size: 0.9rem !important; margin-bottom: 2px !important; margin-top: 4px !important; color: #003399 !important; }

    /* Gap between elements — most important */
    div[data-testid="stVerticalBlock"]   { gap: 0.2rem !important; }
    div[data-testid="stHorizontalBlock"] { gap: 0.4rem !important; }

    /* Inputs */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        border-radius: 6px !important;
        border: 1px solid #cbd5e1 !important;
        padding: 2px 8px !important;
        min-height: 1.8rem !important;
        font-size: 0.83rem !important;
        background: #fafafa !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #003399 !important;
        background: #fff !important;
        box-shadow: 0 0 0 2px rgba(0,51,153,0.08) !important;
    }
    .stSelectbox > div > div {
        border-radius: 6px !important;
        border: 1px solid #cbd5e1 !important;
        min-height: 1.8rem !important;
        font-size: 0.83rem !important;
    }
    .stDateInput > div > div > input {
        border-radius: 6px !important;
        font-size: 0.83rem !important;
        min-height: 1.8rem !important;
        padding: 2px 8px !important;
    }

    /* Labels */
    label {
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        color: #374151 !important;
        margin-bottom: 0px !important;
        padding-bottom: 0px !important;
        line-height: 1.2 !important;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 6px !important;
        min-height: 1.8rem !important;
        font-size: 0.83rem !important;
        font-weight: 600 !important;
        padding: 2px 12px !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #003399, #0055cc) !important;
        border: none !important;
        color: white !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #002277, #0044aa) !important;
        box-shadow: 0 2px 8px rgba(0,51,153,0.25) !important;
    }

    /* Alert boxes */
    div[data-testid="stAlert"] {
        border-radius: 6px !important;
        padding: 4px 10px !important;
        margin: 2px 0 !important;
    }
    div[data-testid="stAlert"] p {
        font-size: 0.82rem !important;
        margin: 0 !important;
        line-height: 1.4 !important;
    }

    /* Metric cards — compact */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #f0f4ff, #e8eeff) !important;
        border: 1px solid #c7d4f5 !important;
        border-radius: 8px !important;
        padding: 6px 10px !important;
        margin: 0 !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1rem !important;
        font-weight: 700 !important;
        color: #003399 !important;
        line-height: 1.2 !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        color: #555 !important;
        line-height: 1.1 !important;
    }
    div[data-testid="stMetricDelta"] { display: none !important; }

    /* HR divider */
    hr { margin: 0.3em 0 !important; border-color: #e2e8f0 !important; }

    /* GR box */
    .gr-box {
        background: #f8faff;
        border: 1px solid #c7d4f5;
        border-radius: 8px;
        padding: 10px 12px;
        height: 100%;
    }

    /* Summary bar */
    .summary-bar {
        background: linear-gradient(135deg, #003399, #0055cc);
        border-radius: 8px;
        padding: 7px 14px;
        color: white;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 4px 0;
    }
    .summary-bar span { margin-right: 20px; }

    /* Confirm box */
    .confirm-box {
        background: #fffbeb;
        border: 1.5px solid #f59e0b;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 6px;
        font-size: 0.85rem;
    }

    /* File uploader */
    .stFileUploader section { padding: 4px !important; min-height: auto !important; }
    .stFileUploader label   { display: none !important; }
    .stFileUploader small   { display: none !important; }

    /* Selectbox dropdown arrow area */
    .stSelectbox [data-baseweb="select"] > div {
        min-height: 1.8rem !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }

    /* Remove extra top padding on form sections */
    div[data-testid="stForm"] > div { gap: 0.2rem !important; }

    /* Dataframe compact */
    .stDataFrame { font-size: 0.8rem !important; }

    /* Download button */
    .stDownloadButton > button {
        border-radius: 6px !important;
        font-size: 0.83rem !important;
        min-height: 1.8rem !important;
        padding: 2px 12px !important;
    }
</style>
"""
