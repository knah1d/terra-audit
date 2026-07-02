"""Liquid Glass presentation layer for terra-audit.

Pure CSS/UX polish injected via ``st.markdown(..., unsafe_allow_html=True)``.
Contains no business logic — safe to change freely without touching the
data/inference/carbon pipeline.

Light/Dark is driven by an explicit in-app toggle (``render_theme_toggle``),
not by Streamlit's native theme switcher — the switcher is disabled via
``.streamlit/config.toml`` so the two systems can't fight each other. Both
palettes below are literal, known-good color values, so switching is
guaranteed to produce correct contrast rather than depending on Streamlit
CSS variables that may or may not be reactive across versions.
"""

import streamlit as st

_RADII = {
    "xl": "24px",
    "lg": "20px",
    "md": "16px",
    "sm": "12px",
    "pill": "999px",
}

_PALETTES = {
    "dark": {
        "bg": "#0b0e14",
        "text": "#f5f5f7",
        "text_secondary": "#a1a1a9",
        "text_tertiary": "#75757e",
        "accent": "#00e6b8",
        "accent_strong": "#33ffd6",
        "accent_contrast": "#04150f",
        "accent_soft": "rgba(0, 230, 184, 0.16)",
        "glass": "rgba(255, 255, 255, 0.055)",
        "glass_strong": "rgba(255, 255, 255, 0.10)",
        "glass_solid": "#161b26",
        "border": "rgba(255, 255, 255, 0.14)",
        "border_strong": "rgba(255, 255, 255, 0.24)",
        "shadow": "0 10px 34px rgba(0, 0, 0, 0.45)",
        "shadow_sm": "0 4px 14px rgba(0, 0, 0, 0.35)",
        "success": "#30d158",
        "warning": "#ffb020",
        "error": "#ff5c5c",
        "info": "#0a84ff",
        "blob_1": "rgba(0, 230, 184, 0.14)",
        "blob_2": "rgba(124, 108, 240, 0.12)",
    },
    "light": {
        "bg": "#f5f6f8",
        "text": "#1d1d1f",
        "text_secondary": "#55555b",
        "text_tertiary": "#7b7b82",
        "accent": "#059669",
        "accent_strong": "#047857",
        "accent_contrast": "#ffffff",
        "accent_soft": "rgba(5, 150, 105, 0.12)",
        "glass": "rgba(255, 255, 255, 0.55)",
        "glass_strong": "rgba(255, 255, 255, 0.80)",
        "glass_solid": "#ffffff",
        "border": "rgba(15, 23, 42, 0.10)",
        "border_strong": "rgba(15, 23, 42, 0.20)",
        "shadow": "0 10px 30px rgba(15, 23, 42, 0.12)",
        "shadow_sm": "0 4px 12px rgba(15, 23, 42, 0.08)",
        "success": "#1f9d55",
        "warning": "#b45309",
        "error": "#dc2626",
        "info": "#0a66c2",
        "blob_1": "rgba(5, 150, 105, 0.10)",
        "blob_2": "rgba(99, 91, 255, 0.08)",
    },
}

_FONT = (
    '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", '
    '"Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif'
)


def _build_css(mode: str) -> str:
    p = _PALETTES[mode]
    r = _RADII

    return f"""
    <style>
    /* =====================================================================
       1. ROOT TOKENS — literal per-mode values, not Streamlit CSS vars.
       ===================================================================== */
    :root {{
        --ta-radius-xl: {r['xl']};
        --ta-radius-lg: {r['lg']};
        --ta-radius-md: {r['md']};
        --ta-radius-sm: {r['sm']};
        --ta-radius-pill: {r['pill']};

        --ta-fast: 180ms;
        --ta-med: 260ms;
        --ta-ease: cubic-bezier(0.4, 0, 0.2, 1);

        --ta-bg: {p['bg']};
        --ta-text: {p['text']};
        --ta-text-secondary: {p['text_secondary']};
        --ta-text-tertiary: {p['text_tertiary']};

        --ta-accent: {p['accent']};
        --ta-accent-strong: {p['accent_strong']};
        --ta-accent-contrast: {p['accent_contrast']};
        --ta-accent-soft: {p['accent_soft']};

        --ta-glass: {p['glass']};
        --ta-glass-strong: {p['glass_strong']};
        --ta-glass-solid: {p['glass_solid']};
        --ta-border: {p['border']};
        --ta-border-strong: {p['border_strong']};
        --ta-shadow: {p['shadow']};
        --ta-shadow-sm: {p['shadow_sm']};

        --ta-success: {p['success']};
        --ta-warning: {p['warning']};
        --ta-error: {p['error']};
        --ta-info: {p['info']};

        --ta-font: {_FONT};
    }}

    /* =====================================================================
       2. APP BACKGROUND
       ===================================================================== */
    .stApp {{
        background:
            radial-gradient(1200px 620px at 12% -8%, {p['blob_1']}, transparent 60%),
            radial-gradient(1000px 560px at 108% 8%, {p['blob_2']}, transparent 60%),
            var(--ta-bg) !important;
        background-attachment: fixed;
        font-family: var(--ta-font);
    }}

    [data-testid="stAppViewContainer"],
    [data-testid="stSidebar"],
    [data-testid="stHeader"] {{
        position: relative;
        z-index: 1;
    }}

    [data-testid="stHeader"] {{
        background: color-mix(in srgb, var(--ta-bg) 55%, transparent) !important;
        backdrop-filter: blur(14px) saturate(160%);
        -webkit-backdrop-filter: blur(14px) saturate(160%);
        border-bottom: 1px solid var(--ta-border);
    }}

    .block-container {{
        padding: 1.6rem clamp(1rem, 3vw, 3rem) 4rem !important;
        max-width: 1400px;
    }}

    ::selection {{
        background: var(--ta-accent-soft);
        color: var(--ta-text);
    }}

    button:focus-visible,
    input:focus-visible,
    textarea:focus-visible,
    [data-baseweb="radio"]:focus-within,
    [data-baseweb="checkbox"]:focus-within {{
        outline: 2px solid var(--ta-accent) !important;
        outline-offset: 2px;
    }}

    /* =====================================================================
       3. GLOBAL TEXT COLOR OVERRIDE
       Streamlit's own theme is pinned to a fixed dark base (see
       .streamlit/config.toml) so our manual toggle doesn't fight the
       native switcher. That means Streamlit's own text rendering never
       changes — we force it to follow OUR active palette instead.
       ===================================================================== */
    .stApp,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span,
    [data-testid="stMarkdownContainer"] strong,
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    [data-testid="stText"],
    [data-testid="stWidgetLabel"] p,
    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"],
    [data-testid="stMetricDelta"],
    [data-testid="stDateInputField"],
    .stApp label,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {{
        color: var(--ta-text) !important;
    }}

    /* =====================================================================
       4. HERO HEADER
       ===================================================================== */
    .ta-hero {{
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        padding: 1.4rem 1.8rem;
        margin-bottom: 1.4rem;
        border-radius: var(--ta-radius-xl);
        background: var(--ta-glass);
        border: 1px solid var(--ta-border);
        backdrop-filter: blur(24px) saturate(180%);
        -webkit-backdrop-filter: blur(24px) saturate(180%);
        box-shadow: var(--ta-shadow);
    }}

    .ta-hero .ta-hero-badge {{
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        width: fit-content;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--ta-accent-strong) !important;
        background: var(--ta-accent-soft);
        border: 1px solid color-mix(in srgb, var(--ta-accent) 35%, transparent);
        padding: 0.28rem 0.75rem;
        border-radius: var(--ta-radius-pill);
    }}

    .ta-hero .ta-hero-title {{
        margin: 0;
        font-size: clamp(1.6rem, 2.6vw, 2.2rem);
        font-weight: 700;
        letter-spacing: -0.01em;
        color: var(--ta-text) !important;
    }}

    .ta-hero .ta-hero-subtitle {{
        margin: 0;
        font-size: 0.92rem;
        color: var(--ta-text-secondary) !important;
    }}

    /* =====================================================================
       5. SIDEBAR
       ===================================================================== */
    [data-testid="stSidebar"] {{
        background: color-mix(in srgb, var(--ta-bg) 72%, transparent) !important;
        backdrop-filter: blur(22px) saturate(180%);
        -webkit-backdrop-filter: blur(22px) saturate(180%);
        border-right: 1px solid var(--ta-border);
    }}

    [data-testid="stSidebar"] .block-container {{
        padding: 1.4rem 1.1rem 2.5rem !important;
    }}

    [data-testid="stSidebar"] hr {{
        border-color: var(--ta-border);
        margin: 0.9rem 0;
    }}

    .ta-card {{
        background: var(--ta-glass);
        border: 1px solid var(--ta-border);
        border-radius: var(--ta-radius-md);
        padding: 0.9rem 1rem;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
    }}

    .ta-card .ta-card-eyebrow {{
        color: var(--ta-text-tertiary) !important;
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        font-weight: 600;
    }}

    .ta-card .ta-card-title {{
        color: var(--ta-accent-strong) !important;
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0.2rem 0 0.15rem;
    }}

    .ta-card .ta-card-body {{
        color: var(--ta-text) !important;
        font-size: 0.88rem;
    }}

    .ta-card .ta-card-meta {{
        color: var(--ta-text-secondary) !important;
        font-size: 0.78rem;
        margin-top: 0.4rem;
    }}

    .ta-progress-list {{
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
    }}

    .ta-progress-list .ta-progress-item {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.82rem;
        color: var(--ta-text-secondary) !important;
        background: var(--ta-glass);
        border: 1px solid var(--ta-border);
        border-radius: var(--ta-radius-sm);
        padding: 0.45rem 0.7rem;
    }}

    .ta-progress-list .ta-progress-item.done {{
        color: var(--ta-text) !important;
        border-color: color-mix(in srgb, var(--ta-success) 45%, transparent);
        background: color-mix(in srgb, var(--ta-success) 12%, transparent);
    }}

    /* =====================================================================
       6. BUTTONS
       ===================================================================== */
    .stButton > button,
    .stDownloadButton > button,
    .stFormSubmitButton > button {{
        border-radius: var(--ta-radius-sm) !important;
        border: 1px solid var(--ta-border-strong) !important;
        background: var(--ta-glass-strong) !important;
        color: var(--ta-text) !important;
        font-weight: 600 !important;
        padding: 0.55rem 1.2rem !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: var(--ta-shadow-sm);
        transition: transform var(--ta-fast) var(--ta-ease),
                    box-shadow var(--ta-fast) var(--ta-ease),
                    background var(--ta-fast) var(--ta-ease),
                    border-color var(--ta-fast) var(--ta-ease);
    }}

    .stButton > button:hover,
    .stDownloadButton > button:hover,
    .stFormSubmitButton > button:hover {{
        transform: translateY(-1px);
        border-color: color-mix(in srgb, var(--ta-accent) 55%, transparent);
        box-shadow: var(--ta-shadow);
    }}

    .stButton > button:active,
    .stDownloadButton > button:active,
    .stFormSubmitButton > button:active {{
        transform: translateY(0);
    }}

    .stButton > button[kind="primary"],
    .stDownloadButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {{
        background: linear-gradient(135deg, var(--ta-accent) 0%, var(--ta-accent-strong) 100%) !important;
        color: var(--ta-accent-contrast) !important;
        border: 1px solid color-mix(in srgb, var(--ta-accent) 60%, transparent) !important;
    }}

    .stButton > button[kind="primary"]:hover,
    .stDownloadButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover {{
        box-shadow: 0 10px 28px color-mix(in srgb, var(--ta-accent) 45%, transparent);
    }}

    /* =====================================================================
       7. TEXT / NUMBER / DATE INPUTS, TEXTAREAS
       ===================================================================== */
    .stTextInput input,
    .stNumberInput input,
    .stDateInput input,
    .stTextArea textarea {{
        background: var(--ta-glass) !important;
        border: 1px solid var(--ta-border) !important;
        border-radius: var(--ta-radius-sm) !important;
        color: var(--ta-text) !important;
        transition: border-color var(--ta-fast) var(--ta-ease),
                    box-shadow var(--ta-fast) var(--ta-ease);
    }}

    .stTextInput input:focus,
    .stNumberInput input:focus,
    .stDateInput input:focus,
    .stTextArea textarea:focus {{
        border-color: color-mix(in srgb, var(--ta-accent) 65%, transparent) !important;
        box-shadow: 0 0 0 3px var(--ta-accent-soft) !important;
    }}

    .stNumberInput button {{
        background: var(--ta-glass) !important;
        border-color: var(--ta-border) !important;
        color: var(--ta-text) !important;
    }}

    /* =====================================================================
       8. SELECT BOXES, DROPDOWN POPOVERS & CALENDAR
       ===================================================================== */
    [data-baseweb="select"] > div {{
        background: var(--ta-glass) !important;
        border-color: var(--ta-border) !important;
        border-radius: var(--ta-radius-sm) !important;
        color: var(--ta-text) !important;
        transition: border-color var(--ta-fast) var(--ta-ease);
    }}

    [data-baseweb="select"] > div:hover {{
        border-color: color-mix(in srgb, var(--ta-accent) 45%, transparent) !important;
    }}

    [data-baseweb="popover"] [role="listbox"],
    [data-baseweb="menu"],
    [data-baseweb="calendar"] {{
        background: var(--ta-glass-solid) !important;
        color: var(--ta-text) !important;
        backdrop-filter: blur(22px) saturate(180%);
        -webkit-backdrop-filter: blur(22px) saturate(180%);
        border: 1px solid var(--ta-border) !important;
        border-radius: var(--ta-radius-md) !important;
        box-shadow: var(--ta-shadow) !important;
    }}

    [data-baseweb="popover"] [role="option"]:hover {{
        background: var(--ta-accent-soft) !important;
    }}

    [data-baseweb="calendar"] * {{
        color: var(--ta-text) !important;
    }}

    /* =====================================================================
       9. RADIO & CHECKBOX
       ===================================================================== */
    .stRadio [role="radiogroup"][style*="row"] {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        background: var(--ta-glass);
        border: 1px solid var(--ta-border);
        border-radius: var(--ta-radius-pill);
        padding: 0.3rem;
        width: fit-content;
    }}

    .stRadio [role="radiogroup"][style*="row"] label {{
        margin: 0 !important;
        padding: 0.45rem 1rem;
        border-radius: var(--ta-radius-pill);
        transition: background var(--ta-fast) var(--ta-ease), color var(--ta-fast) var(--ta-ease);
    }}

    .stRadio [role="radiogroup"][style*="row"] label:hover {{
        background: var(--ta-glass-strong);
    }}

    .stRadio [role="radiogroup"][style*="row"] label:has(input:checked) {{
        background: linear-gradient(135deg, var(--ta-accent) 0%, var(--ta-accent-strong) 100%);
    }}

    .stRadio [role="radiogroup"][style*="row"] label:has(input:checked) div {{
        color: var(--ta-accent-contrast) !important;
    }}

    .stRadio [role="radiogroup"]:not([style*="row"]) label {{
        border-radius: var(--ta-radius-sm);
        padding: 0.4rem 0.6rem;
        transition: background var(--ta-fast) var(--ta-ease);
    }}

    .stRadio [role="radiogroup"]:not([style*="row"]) label:hover {{
        background: var(--ta-glass);
    }}

    .stCheckbox [data-baseweb="checkbox"] span:first-child {{
        background: var(--ta-glass) !important;
        border-color: var(--ta-border-strong) !important;
    }}

    /* =====================================================================
       10. FILE UPLOADER
       ===================================================================== */
    [data-testid="stFileUploaderDropzone"] {{
        background: var(--ta-glass) !important;
        border: 1.5px dashed var(--ta-border-strong) !important;
        border-radius: var(--ta-radius-md) !important;
        transition: border-color var(--ta-fast) var(--ta-ease), background var(--ta-fast) var(--ta-ease);
    }}

    [data-testid="stFileUploaderDropzone"]:hover {{
        border-color: var(--ta-accent) !important;
        background: var(--ta-accent-soft) !important;
    }}

    /* =====================================================================
       11. TABS
       ===================================================================== */
    .stTabs [data-baseweb="tab-list"] {{
        background: var(--ta-glass);
        border: 1px solid var(--ta-border);
        border-radius: var(--ta-radius-pill);
        padding: 0.3rem;
        gap: 0.2rem;
    }}

    .stTabs [data-baseweb="tab"] {{
        border-radius: var(--ta-radius-pill) !important;
        font-size: 0.85rem;
        font-weight: 600;
        padding: 0.5rem 1.1rem;
        color: var(--ta-text-secondary) !important;
        transition: background var(--ta-fast) var(--ta-ease), color var(--ta-fast) var(--ta-ease);
    }}

    .stTabs [data-baseweb="tab"]:hover {{
        background: var(--ta-glass-strong);
        color: var(--ta-text) !important;
    }}

    .stTabs [aria-selected="true"] {{
        background: linear-gradient(135deg, var(--ta-accent) 0%, var(--ta-accent-strong) 100%) !important;
        color: var(--ta-accent-contrast) !important;
    }}

    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] {{
        display: none !important;
    }}

    /* =====================================================================
       12. METRICS
       ===================================================================== */
    [data-testid="stMetric"] {{
        background: var(--ta-glass);
        border: 1px solid var(--ta-border);
        border-radius: var(--ta-radius-md);
        padding: 0.9rem 1.1rem !important;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        box-shadow: var(--ta-shadow-sm);
        transition: transform var(--ta-med) var(--ta-ease), box-shadow var(--ta-med) var(--ta-ease);
    }}

    [data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        box-shadow: var(--ta-shadow);
    }}

    [data-testid="stMetricLabel"] {{
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-size: 0.7rem !important;
    }}

    [data-testid="stMetricValue"] {{
        font-weight: 700 !important;
    }}

    /* =====================================================================
       13. EXPANDERS & BORDERED CONTAINERS
       ===================================================================== */
    [data-testid="stExpander"] {{
        background: var(--ta-glass);
        border: 1px solid var(--ta-border) !important;
        border-radius: var(--ta-radius-md) !important;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        overflow: hidden;
    }}

    [data-testid="stExpander"] summary {{
        transition: background var(--ta-fast) var(--ta-ease);
    }}

    [data-testid="stExpander"] summary:hover {{
        background: var(--ta-glass-strong);
    }}

    [data-testid="stVerticalBlockBorderWrapper"] {{
        border-radius: var(--ta-radius-md);
    }}

    /* =====================================================================
       14. ALERTS (info / success / warning / error)
       ===================================================================== */
    div[data-testid="stAlert"] {{
        background: var(--ta-glass) !important;
        color: var(--ta-text) !important;
        border-radius: var(--ta-radius-md) !important;
        border: 1px solid var(--ta-border) !important;
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        box-shadow: var(--ta-shadow-sm);
    }}

    div[data-testid="stAlert"] p {{
        color: var(--ta-text) !important;
    }}

    div[data-testid="stAlertContentSuccess"] {{ border-left: 4px solid var(--ta-success); padding-left: 0.6rem; }}
    div[data-testid="stAlertContentWarning"] {{ border-left: 4px solid var(--ta-warning); padding-left: 0.6rem; }}
    div[data-testid="stAlertContentError"]   {{ border-left: 4px solid var(--ta-error);   padding-left: 0.6rem; }}
    div[data-testid="stAlertContentInfo"]    {{ border-left: 4px solid var(--ta-info);    padding-left: 0.6rem; }}

    /* =====================================================================
       15. DATAFRAME / TABLE WRAPPER
       ===================================================================== */
    [data-testid="stDataFrame"],
    [data-testid="stTable"] {{
        border-radius: var(--ta-radius-md);
        overflow: hidden;
        border: 1px solid var(--ta-border);
        box-shadow: var(--ta-shadow-sm);
    }}

    /* =====================================================================
       16. CODE BLOCKS
       ===================================================================== */
    .stCodeBlock, pre {{
        border-radius: var(--ta-radius-sm) !important;
        border: 1px solid var(--ta-border);
    }}

    /* =====================================================================
       17. PLOTLY CHART & MAP (FOLIUM IFRAME) CONTAINERS
       ===================================================================== */
    [data-testid="stPlotlyChart"],
    [data-testid="stIFrame"] {{
        border-radius: var(--ta-radius-lg);
        overflow: hidden;
        border: 1px solid var(--ta-border);
        box-shadow: var(--ta-shadow);
    }}

    /* =====================================================================
       18. SCROLLBAR
       ===================================================================== */
    ::-webkit-scrollbar {{
        width: 10px;
        height: 10px;
    }}

    ::-webkit-scrollbar-track {{
        background: transparent;
    }}

    ::-webkit-scrollbar-thumb {{
        background: var(--ta-border-strong);
        border-radius: var(--ta-radius-pill);
    }}

    ::-webkit-scrollbar-thumb:hover {{
        background: color-mix(in srgb, var(--ta-accent) 40%, var(--ta-border-strong));
    }}

    /* =====================================================================
       19. ACCESSIBILITY — REDUCED MOTION
       ===================================================================== */
    @media (prefers-reduced-motion: reduce) {{
        * {{
            transition-duration: 0.01ms !important;
            animation-duration: 0.01ms !important;
        }}
    }}
    </style>
    """


def inject_theme(mode: str) -> None:
    """Injects the Liquid Glass CSS for the given mode. Presentation only."""
    st.markdown(_build_css(mode), unsafe_allow_html=True)


def get_theme_mode(default: str = "dark") -> str:
    """Reads the active toggle mode from session_state before the widget
    that owns it is instantiated later in the script run. Streamlit updates
    a widget's session_state entry before the script reruns, so this is
    safe to call at the top of app.py.
    """
    choice = st.session_state.get("ta_theme_choice")
    if choice is None:
        return default
    return "dark" if "Dark" in choice else "light"


def render_theme_toggle() -> str:
    """Renders the sidebar Appearance toggle and returns the active mode."""
    choice = st.radio(
        "Appearance",
        options=["🌙 Dark", "☀️ Light"],
        horizontal=True,
        label_visibility="collapsed",
        key="ta_theme_choice",
    )
    return "dark" if "Dark" in choice else "light"
