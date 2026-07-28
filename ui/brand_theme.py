"""Lead & Connect brand theme — editorial creative style (inspired by portfolio aesthetics)."""

from __future__ import annotations

# Brand palette (Lead & Connect + warm editorial tones)
NAVY = "#00234E"
NAVY_DARK = "#001833"
NAVY_MID = "#003D7A"
ORANGE = "#D98328"
ORANGE_DARK = "#B86A1A"
ORANGE_LIGHT = "#E8A04E"
CREAM = "#FAF7F2"
CREAM_DARK = "#F0EBE3"
WARM_WHITE = "#FFFCF8"
CHARCOAL = "#1C1C1C"
WHITE = "#FFFFFF"
TEXT_MAIN = CHARCOAL
TEXT_SECONDARY = "#5C5C5C"
TEXT_MUTED = "#9A9A9A"
BORDER = "#E8E2D9"
BORDER_LIGHT = "#F0EBE3"
BG_PAGE = CREAM
BG_SUBTLE = WARM_WHITE
BG_HIGHLIGHT = "#FFF8F0"
BG_TOTAL_ROW = "#FFF4E8"

CARD_BG = WARM_WHITE

STATUS_CHART_COLORS = [
    ORANGE,
    NAVY,
    ORANGE_DARK,
    NAVY_MID,
    TEXT_SECONDARY,
    TEXT_MUTED,
    ORANGE_LIGHT,
    "#10B981",
    "#EF4444",
    "#8B5CF6",
    "#06B6D4",
    "#14B8A6",
]

FONT_SERIF = "'Cormorant Garamond', 'Playfair Display', Georgia, serif"
FONT_SANS = "'DM Sans', 'Segoe UI', system-ui, -apple-system, sans-serif"
FONT_STACK = FONT_SANS

GLOBAL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');

:root {{
    --lc-navy: {NAVY};
    --lc-orange: {ORANGE};
    --lc-cream: {CREAM};
    --lc-charcoal: {CHARCOAL};
    --lc-border: {BORDER};
    --lc-shadow: 0 12px 40px rgba(0, 35, 78, 0.08);
    --lc-shadow-hover: 0 20px 50px rgba(0, 35, 78, 0.14);
    --lc-radius: 18px;
    --lc-font-serif: {FONT_SERIF};
    --lc-font-sans: {FONT_SANS};
}}

/* ── Page background ── */
.stApp {{
    background: {CREAM} !important;
}}
/* ── Header: keep sidebar toggle, hide deploy toolbar ── */
header[data-testid="stHeader"] {{
    visibility: visible !important;
    display: block !important;
    height: auto !important;
    min-height: 3.25rem !important;
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
}}
[data-testid="stToolbar"] {{
    display: none !important;
}}
div[data-testid="stDecoration"] {{
    display: none !important;
}}
button[data-testid="collapsedControl"],
button[data-testid="stSidebarCollapsedControl"] {{
    visibility: visible !important;
    display: flex !important;
    color: {NAVY} !important;
    z-index: 999999 !important;
}}
[data-testid="stAppViewContainer"] {{
    top: 0 !important;
    background:
        radial-gradient(ellipse 80% 60% at 10% 0%, rgba(217, 131, 40, 0.07) 0%, transparent 55%),
        radial-gradient(ellipse 60% 50% at 95% 10%, rgba(0, 35, 78, 0.05) 0%, transparent 50%),
        linear-gradient(180deg, {CREAM} 0%, {WARM_WHITE} 40%, {CREAM} 100%) !important;
    font-family: var(--lc-font-sans);
}}
section.main > div {{
    padding-top: 0 !important;
}}
[data-testid="stMain"] {{ background: transparent !important; }}
[data-testid="stMain"] iframe {{
    background: {CREAM} !important;
}}
.block-container {{
    padding-top: 1.25rem !important;
    max-width: 100% !important;
    background: transparent !important;
}}

/* ── Sidebar — always visible & expanded ── */
section[data-testid="stSidebar"] {{
    display: block !important;
    visibility: visible !important;
    transform: translateX(0) !important;
    min-width: 21rem !important;
    width: 21rem !important;
    background: linear-gradient(165deg, {NAVY} 0%, {NAVY_DARK} 55%, #001020 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}}
section[data-testid="stSidebar"] > div {{
    transform: none !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
    visibility: visible !important;
}}
section[data-testid="stSidebar"]::before {{
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 20% 15%, rgba(217,131,40,0.12) 0%, transparent 45%);
    pointer-events: none;
}}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
    color: {WHITE} !important;
}}
section[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.12) !important;
    margin: 1rem 0 !important;
}}
section[data-testid="stSidebar"] [data-testid="stRadio"] label {{
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    padding: 0.45rem 0.65rem !important;
    margin-bottom: 4px !important;
    transition: all 0.2s ease !important;
}}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{
    background: rgba(217,131,40,0.15) !important;
    border-color: rgba(217,131,40,0.35) !important;
}}
section[data-testid="stSidebar"] button[kind="primary"] {{
    background: linear-gradient(135deg, {ORANGE}, {ORANGE_DARK}) !important;
    border: none !important;
    font-weight: 600 !important;
    color: {WHITE} !important;
    border-radius: 10px !important;
    letter-spacing: 0.04em !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}}
section[data-testid="stSidebar"] button[kind="primary"]:hover {{
    background: linear-gradient(135deg, {ORANGE_LIGHT}, {ORANGE}) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(217,131,40,0.35) !important;
}}
section[data-testid="stSidebar"] button[kind="secondary"] {{
    border-radius: 10px !important;
    border-color: rgba(255,255,255,0.2) !important;
    color: {WHITE} !important;
    background: rgba(255,255,255,0.06) !important;
}}
section[data-testid="stSidebar"] .nav-section {{
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: {ORANGE_LIGHT} !important;
    margin: 20px 0 8px 0;
    opacity: 0.9;
}}
section[data-testid="stSidebar"] .lc-sidebar-logo {{
    padding: 8px 4px 12px 4px;
    text-align: left;
}}
section[data-testid="stSidebar"] .lc-logo-sidebar-wrap {{
    background: {CREAM};
    border-radius: 12px;
    padding: 10px 12px;
    display: inline-block;
    margin-bottom: 10px;
}}
section[data-testid="stSidebar"] .lc-logo-sidebar-wrap img {{
    display: block !important;
    max-width: 176px !important;
    width: 100% !important;
    height: auto !important;
    margin: 0 !important;
}}
section[data-testid="stSidebar"] .lc-sidebar-logo [data-testid="stImage"] {{
    text-align: left;
    margin-left: 0 !important;
}}
section[data-testid="stSidebar"] .lc-sidebar-logo img {{
    margin: 0 !important;
}}
section[data-testid="stSidebar"] .brand-sub {{
    font-size: 0.68rem;
    color: rgba(255,255,255,0.55) !important;
    text-align: left;
    margin-top: 8px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}}

/* ── Main content typography ── */
[data-testid="stMain"] h1,
[data-testid="stMain"] h2,
[data-testid="stMain"] h3 {{
    font-family: var(--lc-font-serif) !important;
    color: {NAVY} !important;
    letter-spacing: 0.02em !important;
}}
.lc-page-hero {{
    padding: 28px 0 22px 0;
    margin-bottom: 8px;
    border-bottom: 1px solid {BORDER};
    position: relative;
}}
.lc-page-hero::after {{
    content: '';
    position: absolute;
    bottom: -1px; left: 0;
    width: 80px; height: 3px;
    background: linear-gradient(90deg, {ORANGE}, {ORANGE_LIGHT});
    border-radius: 2px;
}}
.lc-page-hero .lc-eyebrow {{
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: {ORANGE_DARK};
    margin-bottom: 8px;
}}
.lc-page-hero .lc-title {{
    font-family: var(--lc-font-serif);
    font-size: clamp(1.75rem, 3vw, 2.35rem);
    font-weight: 700;
    color: {NAVY};
    line-height: 1.15;
    margin: 0;
}}
.lc-page-hero .lc-title em {{
    color: {ORANGE};
    font-style: italic;
    font-weight: 600;
}}
.lc-page-hero .lc-subtitle {{
    font-size: 0.92rem;
    color: {TEXT_SECONDARY};
    margin-top: 10px;
    max-width: 640px;
    line-height: 1.55;
}}
.lc-badge {{
    display: inline-flex;
    align-items: center;
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 999px;
    padding: 8px 18px;
    font-size: 0.76rem;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    box-shadow: 0 4px 14px rgba(0,35,78,0.06);
    letter-spacing: 0.03em;
    white-space: nowrap;
}}
.lc-quote-block {{
    background: linear-gradient(135deg, {CARD_BG}, {BG_HIGHLIGHT});
    border-left: 4px solid {ORANGE};
    border-radius: 0 14px 14px 0;
    padding: 18px 22px;
    margin: 16px 0;
    font-family: var(--lc-font-serif);
    font-size: 1.05rem;
    font-style: italic;
    color: {NAVY};
    line-height: 1.5;
    box-shadow: var(--lc-shadow);
}}

/* ── Metrics & cards ── */
div[data-testid="stMetric"] {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: var(--lc-radius);
    padding: 16px 18px;
    box-shadow: var(--lc-shadow);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}}
div[data-testid="stMetric"]:hover {{
    transform: translateY(-2px);
    box-shadow: var(--lc-shadow-hover);
}}
div[data-testid="stMetric"] label {{
    color: {TEXT_MUTED} !important;
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    color: {NAVY} !important;
    font-family: var(--lc-font-serif) !important;
    font-weight: 700 !important;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 6px;
    background: transparent;
}}
.stTabs [data-baseweb="tab"] {{
    color: {TEXT_SECONDARY} !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.04em !important;
    border-radius: 10px 10px 0 0 !important;
    padding: 10px 18px !important;
}}
.stTabs [aria-selected="true"] {{
    color: {NAVY} !important;
    border-bottom: 3px solid {ORANGE} !important;
    background: rgba(250,247,242,0.85) !important;
}}

/* ── Buttons (main area) ── */
[data-testid="stMain"] button[kind="primary"] {{
    background: linear-gradient(135deg, {NAVY}, {NAVY_MID}) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    transition: all 0.2s ease !important;
}}
[data-testid="stMain"] button[kind="primary"]:hover {{
    background: linear-gradient(135deg, {NAVY_MID}, {NAVY}) !important;
    box-shadow: 0 8px 24px rgba(0,35,78,0.2) !important;
    transform: translateY(-1px) !important;
}}

/* ── Expanders & containers ── */
[data-testid="stExpander"] {{
    background: {CARD_BG} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 14px !important;
    box-shadow: 0 4px 16px rgba(0,35,78,0.04) !important;
}}
[data-testid="stFileUploader"] {{
    background: {CARD_BG};
    border: 1px dashed {BORDER};
    border-radius: 14px;
    padding: 8px;
}}
</style>
"""

OVERVIEW_CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: {FONT_SANS};
    background: {CREAM};
    color: {TEXT_MAIN};
    padding: 8px 4px 40px 4px;
}}
.wrap {{ max-width: 1400px; margin: 0 auto; }}

.hero {{
    display: flex; justify-content: space-between; align-items: flex-end;
    padding: 32px 0 24px 0; margin-bottom: 28px;
    border-bottom: 1px solid {BORDER};
    position: relative;
}}
.hero::after {{
    content: ''; position: absolute; bottom: -1px; left: 0;
    width: 100px; height: 3px;
    background: linear-gradient(90deg, {ORANGE}, {ORANGE_LIGHT});
    border-radius: 2px;
}}
.hero .eyebrow {{
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.2em;
    text-transform: uppercase; color: {ORANGE_DARK}; margin-bottom: 10px;
}}
.hero h1 {{
    font-family: {FONT_SERIF}; font-size: 2.4rem; font-weight: 700;
    color: {NAVY}; line-height: 1.1; letter-spacing: 0.01em;
}}
.hero h1 em {{ color: {ORANGE}; font-style: italic; font-weight: 600; }}
.hero p {{ font-size: 0.9rem; color: {TEXT_SECONDARY}; margin-top: 12px; line-height: 1.55; max-width: 520px; }}
.badge {{
    background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 999px;
    padding: 10px 20px; font-size: 0.76rem; font-weight: 600;
    color: {TEXT_SECONDARY}; box-shadow: 0 4px 16px rgba(0,35,78,0.06);
    letter-spacing: 0.04em;
}}

.kpi-grid {{
    display: grid; grid-template-columns: repeat(6, 1fr);
    gap: 16px; margin-bottom: 28px;
}}
.kpi {{
    background: {CARD_BG}; border-radius: 18px; padding: 20px 18px 18px 18px;
    box-shadow: 0 10px 32px rgba(0,35,78,0.07);
    border: 1px solid {BORDER_LIGHT};
    position: relative; overflow: hidden;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
}}
.kpi:hover {{
    transform: translateY(-4px);
    box-shadow: 0 18px 44px rgba(0,35,78,0.12);
}}
.kpi .num {{
    position: absolute; top: 12px; right: 14px;
    font-family: {FONT_SERIF}; font-size: 2rem; font-weight: 700;
    color: rgba(0,35,78,0.06); line-height: 1;
}}
.kpi::before {{
    content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
}}
.kpi.b::before {{ background: linear-gradient(180deg, {ORANGE}, {ORANGE_DARK}); }}
.kpi.g::before {{ background: linear-gradient(180deg, #10B981, #059669); }}
.kpi.o::before {{ background: linear-gradient(180deg, {ORANGE_LIGHT}, {ORANGE}); }}
.kpi.p::before {{ background: linear-gradient(180deg, {NAVY_MID}, {NAVY}); }}
.kpi.r::before {{ background: linear-gradient(180deg, #EF4444, #DC2626); }}
.kpi.s::before {{ background: linear-gradient(180deg, {TEXT_MUTED}, {TEXT_SECONDARY}); }}
.kpi-label {{
    font-size: 0.62rem; font-weight: 700; color: {TEXT_MUTED};
    text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 8px;
}}
.kpi-val {{
    font-family: {FONT_SERIF}; font-size: 1.85rem; font-weight: 700;
    color: {NAVY}; line-height: 1.05;
}}
.kpi-sub {{ font-size: 0.74rem; color: {TEXT_SECONDARY}; margin-top: 8px; line-height: 1.35; }}

.panels {{ display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 20px; margin-bottom: 22px; }}
.panel {{
    background: {CARD_BG}; border-radius: 20px; padding: 24px;
    box-shadow: 0 10px 36px rgba(0,35,78,0.07);
    border: 1px solid {BORDER_LIGHT};
}}
.panel-title {{
    font-size: 0.72rem; font-weight: 700; color: {NAVY};
    text-transform: uppercase; letter-spacing: 0.14em; margin-bottom: 16px;
    display: flex; align-items: center; gap: 10px;
}}
.panel-title::before {{
    content: ''; width: 24px; height: 2px;
    background: linear-gradient(90deg, {ORANGE}, transparent);
    border-radius: 1px;
}}
.store-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
.store-item {{
    background: linear-gradient(145deg, {BG_SUBTLE}, {CREAM});
    border: 1px solid {BORDER}; border-radius: 14px;
    padding: 16px 12px; text-align: center;
    transition: transform 0.2s ease;
}}
.store-item:hover {{ transform: scale(1.02); }}
.store-item .v {{
    font-family: {FONT_SERIF}; font-size: 1.35rem; font-weight: 700; color: {NAVY};
}}
.store-item .l {{ font-size: 0.66rem; color: {TEXT_SECONDARY}; margin-top: 5px; letter-spacing: 0.04em; }}

.modules {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }}
.mod {{
    background: {CARD_BG};
    border: 1px solid {BORDER}; border-radius: 16px; padding: 20px 18px;
    position: relative; overflow: hidden;
    transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}}
.mod:hover {{
    transform: translateY(-3px);
    box-shadow: 0 14px 36px rgba(0,35,78,0.1);
    border-color: rgba(217,131,40,0.35);
}}
.mod .mod-num {{
    font-family: {FONT_SERIF}; font-size: 2.2rem; font-weight: 700;
    color: rgba(0,35,78,0.07); position: absolute; top: 8px; right: 14px; line-height: 1;
}}
.mod h3 {{
    font-family: {FONT_SERIF}; font-size: 1rem; color: {NAVY};
    margin-bottom: 8px; font-weight: 700;
}}
.mod p {{ font-size: 0.76rem; color: {TEXT_SECONDARY}; line-height: 1.5; }}

.quote-strip {{
    background: linear-gradient(135deg, {CARD_BG} 0%, {BG_HIGHLIGHT} 100%);
    border-left: 4px solid {ORANGE}; border-radius: 0 16px 16px 0;
    padding: 20px 24px; margin-bottom: 22px;
    font-family: {FONT_SERIF}; font-size: 1.1rem; font-style: italic;
    color: {NAVY}; line-height: 1.5;
    box-shadow: 0 8px 28px rgba(0,35,78,0.06);
}}

.color-bars {{ display: flex; flex-direction: column; gap: 10px; }}
.color-row {{ display: flex; align-items: center; gap: 10px; font-size: 0.78rem; }}
.color-row .bar {{
    flex: 1; height: 8px; background: {BORDER}; border-radius: 4px; overflow: hidden;
}}
.color-row .fill {{ height: 100%; border-radius: 4px; }}
.dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}

@media (max-width: 1100px) {{
    .kpi-grid {{ grid-template-columns: repeat(3, 1fr); }}
    .panels {{ grid-template-columns: 1fr; }}
    .modules {{ grid-template-columns: 1fr; }}
    .hero h1 {{ font-size: 1.85rem; }}
}}
"""

DATA_CLIENT_PAGE_CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: {FONT_SANS};
    background: {CREAM};
    color: {TEXT_MAIN};
    padding: 12px 24px 32px 24px;
}}
.wrap {{ max-width: 1380px; margin: 0 auto; }}

.hero {{
    display: flex; justify-content: space-between; align-items: flex-end;
    padding: 28px 0 22px 0; margin-bottom: 24px;
    border-bottom: 1px solid {BORDER}; position: relative;
}}
.hero::after {{
    content: ''; position: absolute; bottom: -1px; left: 0;
    width: 90px; height: 3px;
    background: linear-gradient(90deg, {ORANGE}, {ORANGE_LIGHT});
}}
.hero .eyebrow {{
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.2em;
    text-transform: uppercase; color: {ORANGE_DARK}; margin-bottom: 8px;
}}
.hero h1 {{
    font-family: {FONT_SERIF}; font-size: 2.1rem; font-weight: 700;
    color: {NAVY}; letter-spacing: 0.02em;
}}
.hero p {{ font-size: 0.85rem; color: {TEXT_SECONDARY}; margin-top: 10px; line-height: 1.5; }}
.badge {{
    background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 999px;
    padding: 10px 18px; font-size: 0.76rem; font-weight: 600;
    color: {TEXT_SECONDARY}; box-shadow: 0 4px 14px rgba(0,35,78,0.06);
}}

.kpi-grid {{
    display: grid; grid-template-columns: repeat(5, 1fr);
    gap: 16px; margin-bottom: 26px;
}}
.kpi {{
    background: {CARD_BG}; border-radius: 18px; padding: 20px 20px 18px 20px;
    box-shadow: 0 10px 32px rgba(0,35,78,0.07);
    border: 1px solid {BORDER_LIGHT};
    position: relative; overflow: hidden;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}}
.kpi:hover {{ transform: translateY(-3px); box-shadow: 0 16px 40px rgba(0,35,78,0.11); }}
.kpi::before {{
    content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
}}
.kpi.b::before {{ background: linear-gradient(180deg,{ORANGE},{ORANGE_DARK}); }}
.kpi.p::before {{ background: linear-gradient(180deg,{NAVY_MID},{NAVY}); }}
.kpi.g::before {{ background: linear-gradient(180deg,#10B981,#059669); }}
.kpi.o::before {{ background: linear-gradient(180deg,{ORANGE_LIGHT},{ORANGE}); }}
.kpi.s::before {{ background: linear-gradient(180deg,{TEXT_MUTED},{TEXT_SECONDARY}); }}
.kpi-label {{
    font-size: 0.64rem; font-weight: 700; color: {TEXT_MUTED};
    text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 8px;
}}
.kpi-val {{
    font-family: {FONT_SERIF}; font-size: 2.1rem; font-weight: 700;
    color: {NAVY}; line-height: 1; letter-spacing: -0.02em;
}}
.kpi-pct {{ font-size: 0.88rem; font-weight: 600; color: {TEXT_SECONDARY}; }}
.kpi-desc {{ font-size: 0.74rem; color: {TEXT_MUTED}; margin-top: 8px; line-height: 1.35; }}

.panels {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 22px; }}
.panel {{
    background: {CARD_BG}; border-radius: 20px; padding: 24px;
    box-shadow: 0 10px 36px rgba(0,35,78,0.07);
    border: 1px solid {BORDER_LIGHT};
}}
.panel-head {{
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid {BORDER_LIGHT};
}}
.panel-num {{
    background: linear-gradient(135deg, {NAVY}, {NAVY_MID});
    color: {WHITE}; font-family: {FONT_SERIF}; font-size: 0.85rem; font-weight: 700;
    width: 32px; height: 32px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 12px rgba(0,35,78,0.2);
}}
.panel-title {{
    font-size: 0.78rem; font-weight: 700; color: {NAVY};
    text-transform: uppercase; letter-spacing: 0.1em;
}}
.panel-body {{ display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 14px; align-items: start; }}

table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
th {{
    text-align: left; padding: 10px 12px; background: {CREAM};
    color: {TEXT_SECONDARY}; font-size: 0.66rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em;
    border-bottom: 2px solid {BORDER};
}}
td {{ padding: 10px 12px; border-bottom: 1px solid {BORDER_LIGHT}; }}
tr:hover td {{ background: {BG_SUBTLE}; }}
tr.total td {{
    font-weight: 700; background: {BG_TOTAL_ROW}; color: {NAVY};
    border-top: 2px solid {ORANGE};
}}
.dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 7px; vertical-align: middle; }}
.pct-wrap {{ display: flex; align-items: center; gap: 7px; }}
.pct-bar {{ flex: 1; height: 6px; background: {BORDER}; border-radius: 3px; max-width: 72px; overflow: hidden; }}
.pct-fill {{ height: 100%; background: linear-gradient(90deg,{ORANGE},{ORANGE_LIGHT}); border-radius: 3px; }}
.chart-box {{ background: {CREAM}; border-radius: 14px; border: 1px solid {BORDER_LIGHT}; padding: 4px; min-height: 280px; }}

.chain-panel {{
    background: linear-gradient(135deg, {CARD_BG}, {BG_SUBTLE});
    border-radius: 20px; padding: 28px 32px; margin-bottom: 20px;
    box-shadow: 0 10px 36px rgba(0,35,78,0.07); border: 1px solid {BORDER_LIGHT};
}}
.chain-title {{
    font-family: {FONT_SERIF}; font-size: 1.05rem; font-weight: 700;
    color: {NAVY}; letter-spacing: 0.03em;
}}
.chain-sub {{ font-size: 0.78rem; color: {TEXT_SECONDARY}; margin: 6px 0 20px 0; }}
.chain-flow {{ display: flex; align-items: center; flex-wrap: wrap; gap: 10px; justify-content: center; }}
.chain-box {{
    background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 14px;
    padding: 16px 18px; text-align: center; min-width: 120px;
    box-shadow: 0 4px 14px rgba(0,35,78,0.05);
    transition: transform 0.2s ease;
}}
.chain-box:hover {{ transform: translateY(-2px); }}
.chain-box.end {{
    background: linear-gradient(145deg,{BG_HIGHLIGHT},{BG_TOTAL_ROW});
    border: 2px solid {ORANGE}; box-shadow: 0 8px 24px rgba(217,131,40,0.22);
}}
.chain-box .v {{
    font-family: {FONT_SERIF}; font-size: 1.4rem; font-weight: 700; color: {NAVY};
}}
.chain-box.end .v {{ color: {ORANGE_DARK}; }}
.chain-box .l {{ font-size: 0.66rem; color: {TEXT_SECONDARY}; margin-top: 5px; line-height: 1.3; }}
.chain-op {{ font-size: 1.4rem; color: {TEXT_MUTED}; font-weight: 300; padding: 0 4px; }}
.chain-op.minus {{ color: #EF4444; font-weight: 700; }}

.footer {{
    display: flex; justify-content: space-between; padding-top: 16px;
    font-size: 0.72rem; color: {TEXT_MUTED}; border-top: 1px solid {BORDER};
}}

.panels-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 22px; }}
@media (max-width: 1100px) {{ .panels-3 {{ grid-template-columns: 1fr; }} }}
"""

LOGIN_PAGE_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;0,9..40,800;1,9..40,400&display=swap');

[data-testid="stAppViewContainer"]:has(.lc-login-root-marker) section[data-testid="stSidebar"] {{
    display: none !important;
}}
[data-testid="stAppViewContainer"]:has(.lc-login-root-marker) header[data-testid="stHeader"] {{
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
}}
.lc-login-root-marker {{ display: none; }}

/* ── Carte principale unifiée ── */
.block-container:has(.lc-login-root-marker) [data-testid="stHorizontalBlock"]:has(.lc-col-brand-marker) {{
    background: {CREAM};
    border-radius: 28px;
    overflow: hidden;
    box-shadow:
        0 4px 6px rgba(0,35,78,0.04),
        0 20px 48px rgba(0,35,78,0.12);
    border: 1px solid {BORDER};
    width: min(940px, 100%);
    margin: 0 auto;
    animation: lcFadeUp 0.65s ease-out both;
}}
@keyframes lcFadeUp {{
    from {{ opacity: 0; transform: translateY(28px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}

/* ── Fond plein écran ── */
[data-testid="stAppViewContainer"]:has(.lc-login-root-marker) {{
    background:
        radial-gradient(ellipse 75% 60% at 8% 15%, rgba(217,131,40,0.10) 0%, transparent 55%),
        radial-gradient(ellipse 50% 45% at 92% 85%, rgba(0,35,78,0.06) 0%, transparent 50%),
        linear-gradient(165deg, {CREAM} 0%, {WARM_WHITE} 45%, {CREAM_DARK} 100%) !important;
}}
.block-container:has(.lc-login-root-marker) {{
    max-width: 100% !important;
    min-height: calc(100vh - 4rem);
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    align-items: center !important;
    padding: 2.5rem 1.5rem !important;
}}

/* ── Panneau gauche (brand) ── */
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-brand-marker) {{
    background: linear-gradient(165deg, {NAVY} 0%, {NAVY_DARK} 100%) !important;
    padding: 0 !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    min-height: 540px;
    position: relative;
    overflow: hidden;
}}
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-brand-marker)::before {{
    content: '';
    position: absolute; inset: 0;
    background:
        radial-gradient(circle at 20% 15%, rgba(217,131,40,0.25) 0%, transparent 45%),
        radial-gradient(circle at 80% 90%, rgba(0,168,150,0.15) 0%, transparent 40%);
    pointer-events: none;
}}
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-brand-marker)::after {{
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 200px; height: 200px;
    border-radius: 50%;
    border: 1px solid rgba(255,255,255,0.08);
    pointer-events: none;
}}
.lc-col-brand-marker {{ display: none; }}
.lc-brand-panel {{
    position: relative; z-index: 1;
    padding: 2.75rem 2.25rem 2.75rem 2.5rem;
    height: 100%;
    display: flex; flex-direction: column; justify-content: center;
}}
.lc-logo-card {{
    background: {CREAM};
    border-radius: 18px;
    padding: 1.5rem 1.25rem;
    width: fit-content;
    box-shadow: 0 16px 48px rgba(0,0,0,0.22);
    margin-bottom: 1.75rem;
}}
.lc-logo-card img, .lc-logo-img {{
    display: block !important;
    max-width: 240px !important;
    width: 100% !important;
    height: auto !important;
    margin: 0 !important;
}}
.lc-brand-eyebrow {{
    font-size: 0.68rem; font-weight: 700;
    letter-spacing: 0.2em; text-transform: uppercase;
    color: {ORANGE_LIGHT}; margin: 0 0 0.85rem 0;
}}
.lc-brand-title {{
    font-size: 1.75rem !important; font-weight: 800 !important;
    color: {WHITE} !important;
    line-height: 1.2 !important; margin: 0 0 0.75rem 0 !important;
    font-family: {FONT_SANS} !important;
    letter-spacing: -0.02em;
}}
.lc-brand-desc {{
    font-size: 0.88rem; color: rgba(255,255,255,0.62);
    line-height: 1.6; margin: 0; max-width: 300px;
}}

/* ── Panneau droit (formulaire) ── */
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-form-marker) {{
    background: {CREAM} !important;
    padding: 0 !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    min-height: 540px;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
}}
.lc-col-form-marker {{ display: none; }}
.lc-form-panel {{
    padding: 2.75rem 2.75rem 0 2.75rem;
}}
.lc-form-badge {{
    display: inline-block;
    background: linear-gradient(135deg, rgba(217,131,40,0.12), rgba(217,131,40,0.06));
    color: {ORANGE_DARK};
    font-size: 0.68rem; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase;
    padding: 6px 14px; border-radius: 999px;
    border: 1px solid rgba(217,131,40,0.25);
    margin-bottom: 1.25rem;
}}
.lc-form-title {{
    font-size: 2rem !important; font-weight: 800 !important;
    color: {NAVY} !important;
    margin: 0 0 0.4rem 0 !important;
    font-family: {FONT_SANS} !important;
    letter-spacing: -0.03em;
}}
.lc-form-sub {{
    font-size: 0.9rem; color: {TEXT_SECONDARY};
    margin: 0 0 0.25rem 0; line-height: 1.5;
}}

/* Formulaire Streamlit dans la carte */
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-form-marker) [data-testid="stForm"] {{
    padding: 1.5rem 2.75rem 2.75rem 2.75rem !important;
    border: none !important;
    background: transparent !important;
    margin-top: 0 !important;
}}
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-form-marker) [data-testid="stTextInput"] {{
    margin-bottom: 0.25rem;
}}
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-form-marker) [data-testid="stTextInput"] label {{
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: {TEXT_SECONDARY} !important;
    margin-bottom: 6px !important;
}}
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-form-marker) [data-testid="stTextInput"] input {{
    border-radius: 14px !important;
    border: 1.5px solid {BORDER} !important;
    padding: 0.75rem 1rem !important;
    font-size: 0.95rem !important;
    background: {WARM_WHITE} !important;
    transition: border-color 0.2s, box-shadow 0.2s, background 0.2s !important;
    color: {CHARCOAL} !important;
}}
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-form-marker) [data-testid="stTextInput"] input:focus {{
    border-color: {ORANGE} !important;
    background: {CARD_BG} !important;
    box-shadow: 0 0 0 4px rgba(217,131,40,0.12) !important;
}}
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-form-marker) button[kind="primary"] {{
    background: linear-gradient(135deg, {ORANGE} 0%, {ORANGE_DARK} 100%) !important;
    border: none !important;
    border-radius: 14px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.04em !important;
    padding: 0.8rem 1.2rem !important;
    margin-top: 1rem !important;
    box-shadow: 0 10px 28px rgba(217,131,40,0.38) !important;
    transition: transform 0.18s ease, box-shadow 0.18s ease !important;
}}
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-form-marker) button[kind="primary"]:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 14px 36px rgba(217,131,40,0.48) !important;
}}
.block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-form-marker) [data-testid="stAlert"] {{
    margin: 0 2.75rem 1rem 2.75rem !important;
    border-radius: 12px !important;
}}

@media (max-width: 768px) {{
    .block-container:has(.lc-login-root-marker) [data-testid="stHorizontalBlock"]:has(.lc-col-brand-marker) {{
        border-radius: 20px;
    }}
    .lc-brand-panel, .lc-form-panel {{
        padding: 2rem 1.5rem !important;
    }}
    .block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-brand-marker),
    .block-container:has(.lc-login-root-marker) [data-testid="column"]:has(.lc-col-form-marker) {{
        min-height: auto !important;
    }}
}}
</style>
"""
