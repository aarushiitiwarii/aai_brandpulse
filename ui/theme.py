"""BrandPulse design system (dark): CSS tokens + small HTML components for Streamlit.

Deep navy canvas with violet/blue glows, glass cards, Poppins display type, gradient pill
buttons. Status colors (good / warning / serious / critical) always ship with a text label.
"""
import html

import streamlit as st

PRODUCT = "BrandPulse"

TONES = {  # tone -> (foreground, translucent background, border)
    "critical": ("#ff8e9e", "rgba(255,77,109,0.14)", "rgba(255,77,109,0.38)"),
    "serious": ("#ffb17a", "rgba(255,138,61,0.14)", "rgba(255,138,61,0.36)"),
    "warning": ("#ffd66b", "rgba(250,190,40,0.13)", "rgba(250,190,40,0.34)"),
    "good": ("#6fe3a5", "rgba(46,204,113,0.13)", "rgba(46,204,113,0.34)"),
    "info": ("#a9b8ff", "rgba(124,108,255,0.16)", "rgba(124,108,255,0.40)"),
    "neutral": ("#c4c8e4", "rgba(255,255,255,0.06)", "rgba(255,255,255,0.12)"),
}
LEVEL_TONE = {"Low": "good", "Medium": "warning", "High": "serious", "Critical": "critical",
              "Warning": "warning", "Positive": "info"}
LEVEL_LABEL = {"Low": "Stable", "Medium": "Watch", "High": "Elevated", "Critical": "Crisis",
               "Warning": "Early warning", "Positive": "Positive"}
LEVEL_ICON = {"Low": "check_circle", "Medium": "visibility", "High": "trending_up", "Critical": "error",
              "Warning": "notifications_active", "Positive": "favorite"}

# chart colors tuned for the dark canvas
CHART = {"text": "#9aa0c3", "grid": "rgba(255,255,255,0.06)", "line": "#8b7bff",
         "positive": "#5b8cff", "neutral": "#5d6488", "negative": "#ff4d7d"}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Poppins:wght@400;500;600&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400..600,0..1,0&display=swap');

:root {
  --bp-bg: #070a1a; --bp-surface: rgba(255,255,255,0.035); --bp-surface-2: rgba(255,255,255,0.06);
  --bp-border: rgba(255,255,255,0.08); --bp-border-strong: rgba(255,255,255,0.16);
  --bp-text: #f2f3ff; --bp-text-2: #b8bcda; --bp-muted: #858bb0;
  --bp-primary: #7c6cff; --bp-primary-2: #4f8cff; --bp-primary-soft: rgba(124,108,255,0.16);
  --bp-radius: 20px; --bp-shadow: 0 10px 30px rgba(0,0,0,0.25);
  --bp-grad: linear-gradient(135deg, #7c6cff 0%, #4f8cff 100%);
}
.stApp {
  background:
    radial-gradient(900px 520px at 8% -8%, rgba(124,108,255,0.30), transparent 60%),
    radial-gradient(700px 480px at 100% 0%, rgba(79,140,255,0.16), transparent 60%),
    radial-gradient(800px 600px at 50% 120%, rgba(124,108,255,0.10), transparent 60%),
    #070a1a !important;
  background-attachment: fixed !important;
}
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp td, .stApp th, .bp {
  font-family: 'Inter', system-ui, sans-serif !important; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .bp-display { font-family: 'Poppins', 'Inter', sans-serif !important;
  color: var(--bp-text); letter-spacing: -0.015em; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], footer, #MainMenu { display: none !important; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1320px; }

/* Sidebar: dark glass rail */
[data-testid="stSidebar"] { background: rgba(10,13,32,0.88) !important; border-right: 1px solid var(--bp-border);
  backdrop-filter: blur(16px); }
[data-testid="stSidebarNav"] a { border-radius: 12px; }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: var(--bp-primary-soft) !important; }
[data-testid="stSidebarNavSeparator"] { border-color: var(--bp-border); }

/* Native containers / widgets as glass */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]),
div[data-testid="stVerticalBlock"][class*="border"] {
  background: var(--bp-surface); border-color: var(--bp-border) !important; border-radius: var(--bp-radius) !important;
  backdrop-filter: blur(12px); }
[data-testid="stExpander"] details { background: var(--bp-surface); border: 1px solid var(--bp-border); border-radius: 14px; }
[data-testid="stExpander"] summary p { font-weight: 500; font-size: 14px; }
.stButton > button, .stDownloadButton > button { border-radius: 999px; font-weight: 500; font-size: 14px;
  background: var(--bp-surface-2); border: 1px solid var(--bp-border-strong); color: var(--bp-text); }
.stButton > button:hover { border-color: var(--bp-primary); color: #fff; }
.stButton > button[kind="primary"] { background: var(--bp-grad); border: none; color: #fff;
  box-shadow: 0 6px 20px rgba(124,108,255,0.45); }
[data-testid="stTabs"] button p { font-size: 14px; font-weight: 500; }
[data-testid="stDataFrame"] { border: 1px solid var(--bp-border); border-radius: 14px; overflow: hidden; }
[data-testid="stPlotlyChart"] { background: var(--bp-surface); border: 1px solid var(--bp-border);
  border-radius: var(--bp-radius); padding: 10px 10px 2px; backdrop-filter: blur(12px); }
.js-plotly-plot .modebar-container { display: none !important; }
[data-baseweb="select"] > div, [data-baseweb="input"] > div, .stTextArea textarea { border-radius: 12px !important; }
[data-testid="stSegmentedControl"] button, [data-testid="stBaseButton-segmented_control"],
[data-testid="stBaseButton-segmented_controlActive"] { border-radius: 999px !important; }
[data-testid="stProgress"] > div > div > div > div { background: var(--bp-grad) !important; }

/* Components */
.bp .ms { font-family: 'Material Symbols Rounded' !important; font-weight: normal; font-style: normal;
  line-height: 1; display: inline-block; vertical-align: middle; font-variation-settings: 'FILL' 0, 'wght' 450; }
.bp-header { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; margin-bottom: 22px; flex-wrap: wrap; }
.bp-header h1 { font-size: 30px !important; font-weight: 500 !important; margin: 0 !important; padding: 0 !important; }
.bp-header p { color: var(--bp-muted); margin: 6px 0 0 !important; font-size: 14px; max-width: 760px; }
.bp-chip { display: inline-flex; align-items: center; gap: 8px; padding: 7px 14px; border: 1px solid var(--bp-border);
  background: var(--bp-surface); border-radius: 999px; font-size: 13px; color: var(--bp-text-2); white-space: nowrap; }
.bp-chip .dot { width: 8px; height: 8px; border-radius: 50%; background: #6fe3a5; box-shadow: 0 0 10px #6fe3a5; }

.bp-badge { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 600; border: 1px solid; white-space: nowrap; }
.bp-badge .ms { font-size: 14px; }

/* Hero (home) */
.bp-hero { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; flex-wrap: wrap; margin: 4px 0 22px; }
.bp-hero h1 { font-family: 'Poppins', sans-serif !important; font-size: 40px !important; font-weight: 400 !important;
  margin: 0 !important; padding: 0 !important; line-height: 1.15; }
.bp-hero h1 span { background: linear-gradient(90deg, #b3a8ff, #7cb0ff); -webkit-background-clip: text; color: transparent; }
.bp-hero .sub { color: var(--bp-muted); font-size: 14px; margin-top: 8px; }
.bp-pills { display: flex; gap: 18px; margin-top: 16px; flex-wrap: wrap; }
.bp-pill-stat .l { font-size: 12px; color: var(--bp-muted); margin-bottom: 6px; }
.bp-pill-stat .p { display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 999px; font-size: 13px;
  font-weight: 600; min-width: 64px; }
.bp-bignums { display: flex; gap: 28px; }
.bp-bignum { display: flex; align-items: center; gap: 12px; }
.bp-bignum .ic { width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.bp-bignum .ic .ms { font-size: 20px; }
.bp-bignum .v { font-family: 'Poppins', sans-serif; font-size: 40px; font-weight: 400; color: var(--bp-text); line-height: 1; }
.bp-bignum .l { font-size: 12px; color: var(--bp-muted); margin-top: 4px; }

.bp-banner { display: flex; gap: 16px; align-items: flex-start; padding: 18px 20px; border-radius: var(--bp-radius);
  border: 1px solid; margin: 4px 0 22px; background: var(--bp-surface); backdrop-filter: blur(12px); }
.bp-banner .icon { width: 44px; height: 44px; border-radius: 14px; display: flex; align-items: center; justify-content: center; flex: none; }
.bp-banner .icon .ms { font-size: 24px; }
.bp-banner .title { font-size: 17px; font-weight: 600; color: var(--bp-text); margin: 6px 0 4px; }
.bp-banner .body { font-size: 14px; color: var(--bp-text-2); }
.bp-banner .action { margin-top: 10px; font-size: 13px; color: var(--bp-text); display: flex; gap: 6px; align-items: center; }

.bp-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 22px; }
.bp-kpi { background: var(--bp-surface); border: 1px solid var(--bp-border); border-radius: var(--bp-radius);
  padding: 18px 20px; backdrop-filter: blur(12px); }
.bp-kpi .label { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--bp-muted); font-weight: 500; }
.bp-kpi .label .ms { font-size: 18px; color: #a99dff; }
.bp-kpi .value { font-family: 'Poppins', sans-serif; font-size: 30px; font-weight: 500; color: var(--bp-text); margin: 10px 0 6px; }
.bp-kpi .value small { font-family: 'Inter', sans-serif; font-size: 14px; color: var(--bp-muted); font-weight: 500; }
.bp-kpi .sub { font-size: 12.5px; color: var(--bp-muted); display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.bp-delta { font-weight: 600; display: inline-flex; align-items: center; gap: 2px; }
.bp-delta .ms { font-size: 16px; }

/* Highlight card (blue gradient, like an active-incident widget) */
.bp-feature { border-radius: var(--bp-radius); padding: 20px; color: #fff; position: relative; overflow: hidden;
  background: linear-gradient(160deg, #5b6cff 0%, #3a5bff 45%, #2a3fd6 100%); box-shadow: 0 14px 40px rgba(58,91,255,0.35); }
.bp-feature .k { font-size: 12px; opacity: .85; display: flex; align-items: center; gap: 6px; }
.bp-feature .t { font-family: 'Poppins', sans-serif; font-size: 20px; font-weight: 500; margin: 10px 0 6px; line-height: 1.25; }
.bp-feature .d { font-size: 13px; opacity: .9; }
.bp-feature .row { margin-top: 14px; display: flex; flex-direction: column; gap: 8px; }
.bp-feature .item { background: rgba(255,255,255,0.14); border: 1px solid rgba(255,255,255,0.18); border-radius: 12px;
  padding: 9px 12px; font-size: 13px; display: flex; justify-content: space-between; gap: 8px; }

.bp-section { margin: 30px 0 12px; }
.bp-section h3 { font-size: 18px !important; font-weight: 500 !important; margin: 0 !important; padding: 0 !important; }
.bp-section p { font-size: 13.5px; color: var(--bp-muted); margin: 4px 0 0 !important; }

.bp-card-title { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.bp-card-title .ic { width: 36px; height: 36px; border-radius: 12px; background: var(--bp-primary-soft); color: #b3a8ff;
  display: flex; align-items: center; justify-content: center; flex: none; }
.bp-card-title .ic .ms { font-size: 20px; }
.bp-card-title .t { font-weight: 600; font-size: 15.5px; color: var(--bp-text); line-height: 1.25; }
.bp-meta { font-size: 13px; color: var(--bp-text-2); margin: 6px 0; line-height: 1.5; }
.bp-meta b { color: var(--bp-text); }
.bp-tags { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; }
.bp-tag { font-size: 12px; padding: 4px 10px; border-radius: 999px; background: var(--bp-surface-2); color: var(--bp-text-2);
  border: 1px solid var(--bp-border); }
.bp-tag b { color: var(--bp-text); font-weight: 600; }
.bp-action { font-size: 13px; color: var(--bp-text); display: flex; gap: 6px; align-items: flex-start; margin-top: 10px;
  padding-top: 12px; border-top: 1px solid var(--bp-border); }
.bp-action .ms { font-size: 18px; color: #a99dff; }

.bp-post { font-size: 14px; color: var(--bp-text); line-height: 1.55; padding: 12px 14px; background: rgba(255,255,255,0.03);
  border: 1px solid var(--bp-border); border-radius: 14px; margin: 10px 0; }
.bp-author { display: flex; align-items: center; gap: 10px; }
.bp-avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--bp-grad); color: #fff;
  display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 13px; flex: none; }
.bp-author .name { font-weight: 600; font-size: 14px; color: var(--bp-text); }
.bp-author .sub { font-size: 12px; color: var(--bp-muted); }

.bp-list { display: flex; flex-direction: column; }
.bp-row { display: flex; gap: 12px; padding: 12px 4px; border-bottom: 1px solid var(--bp-border); align-items: flex-start; }
.bp-row:last-child { border-bottom: none; }
.bp-row .ic { color: #a99dff; } .bp-row .ic .ms { font-size: 20px; }
.bp-row .t { font-weight: 600; font-size: 14px; color: var(--bp-text); }
.bp-row .d { font-size: 13px; color: var(--bp-text-2); margin-top: 2px; }
.bp-row .time { margin-left: auto; font-size: 12px; color: var(--bp-muted); white-space: nowrap; }

.bp-step { display: flex; gap: 12px; padding: 10px 0; border-bottom: 1px dashed var(--bp-border); }
.bp-step:last-child { border-bottom: none; }
.bp-step .n { width: 24px; height: 24px; border-radius: 50%; background: var(--bp-primary-soft); color: #b3a8ff;
  font-size: 12px; font-weight: 600; display: flex; align-items: center; justify-content: center; flex: none; }
.bp-step .t { font-weight: 600; font-size: 13.5px; color: var(--bp-text); }
.bp-step .d { font-size: 13px; color: var(--bp-text-2); }
.bp-step .ms_r { margin-left: auto; font-size: 12px; color: var(--bp-muted); white-space: nowrap; }

.bp-bar { flex: 1; height: 8px; background: rgba(255,255,255,0.07); border-radius: 4px; overflow: hidden; }
.bp-bar > div { height: 100%; background: var(--bp-grad); border-radius: 4px; }
.bp-side-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: var(--bp-muted); margin: 6px 0 4px; }
.bp-clock { font-family: 'Poppins', sans-serif; font-size: 16px; font-weight: 500; color: var(--bp-text); }
"""


def inject():
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""))


def icon(name: str, size: int = 18, color: str | None = None, fill: bool = False) -> str:
    style = f"font-size:{size}px;" + (f"color:{color};" if color else "") + \
            ("font-variation-settings:'FILL' 1,'wght' 500;" if fill else "")
    return f'<span class="ms" style="{style}">{name}</span>'


def render(markup: str):
    st.markdown(f'<div class="bp">{markup}</div>', unsafe_allow_html=True)


def badge(text: str, tone: str = "neutral", icon_name: str | None = None) -> str:
    fg, bg, bd = TONES[tone]
    ic = icon(icon_name, 14) if icon_name else ""
    return f'<span class="bp-badge" style="color:{fg};background:{bg};border-color:{bd}">{ic}{esc(text)}</span>'


def level_badge(level: str) -> str:
    return badge(LEVEL_LABEL.get(level, level), LEVEL_TONE.get(level, "neutral"), LEVEL_ICON.get(level))


def page_header(title: str, subtitle: str, chip_text: str | None = None):
    chip = f'<span class="bp-chip"><span class="dot"></span>{esc(chip_text)}</span>' if chip_text else ""
    render(f'<div class="bp-header"><div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>{chip}</div>')


def section(title: str, subtitle: str | None = None):
    sub = f"<p>{esc(subtitle)}</p>" if subtitle else ""
    render(f'<div class="bp-section"><h3>{esc(title)}</h3>{sub}</div>')


def banner(level: str, title: str, body: str = "", action: str | None = None):
    tone = LEVEL_TONE.get(level, "neutral")
    fg, bg, bd = TONES[tone]
    act = f'<div class="action">{icon("subdirectory_arrow_right", 18, fg)}<span><b>Recommended action:</b> {esc(action)}</span></div>' \
        if action else ""
    render(f'<div class="bp-banner" style="border-color:{bd}">'
           f'<div class="icon" style="background:{bg};color:{fg}">{icon(LEVEL_ICON.get(level, "info"), 24, fg, fill=True)}</div>'
           f'<div style="flex:1"><div>{level_badge(level)}</div><div class="title">{esc(title)}</div>'
           f'<div class="body">{esc(body)}</div>{act}</div></div>')


def kpi(label: str, value: str, icon_name: str, sub: str = "", delta: float | None = None,
        delta_suffix: str = "", good_when_up: bool = True, unit: str = "") -> str:
    d = ""
    if delta is not None and delta != 0:
        up = delta > 0
        color = TONES["good" if up == good_when_up else "critical"][0]
        d = (f'<span class="bp-delta" style="color:{color}">{icon("arrow_upward" if up else "arrow_downward", 16)}'
             f'{abs(delta):g}{esc(delta_suffix)}</span>')
    u = f" <small>{esc(unit)}</small>" if unit else ""
    return (f'<div class="bp-kpi"><div class="label">{icon(icon_name)}{esc(label)}</div>'
            f'<div class="value">{value}{u}</div><div class="sub">{d}<span>{sub}</span></div></div>')


def kpi_row(cards: list[str]):
    render(f'<div class="bp-kpis">{"".join(cards)}</div>')


def card_title(icon_name: str, title: str, right: str = "") -> str:
    return (f'<div class="bp-card-title"><div class="ic">{icon(icon_name, 20)}</div>'
            f'<div class="t" style="flex:1">{esc(title)}</div>{right}</div>')


def author(handle: str, sub: str) -> str:
    initials = esc(handle.lstrip("@")[:2].upper())
    return (f'<div class="bp-author"><div class="bp-avatar">{initials}</div>'
            f'<div><div class="name">{esc(handle)}</div><div class="sub">{sub}</div></div></div>')


def post(text: str) -> str:
    return f'<div class="bp-post">{esc(text)}</div>'


def pill_stat(label: str, value: str, color: str, text_color: str = "#0b0d1f") -> str:
    return (f'<div class="bp-pill-stat"><div class="l">{esc(label)}</div>'
            f'<div class="p" style="background:{color};color:{text_color}">{esc(value)}</div></div>')


def bignum(value: str, label: str, icon_name: str, tone: str) -> str:
    fg, bg, _ = TONES[tone]
    return (f'<div class="bp-bignum"><div class="ic" style="background:{bg};color:{fg}">{icon(icon_name, 20, fg, fill=True)}</div>'
            f'<div><div class="v">{esc(value)}</div><div class="l">{esc(label)}</div></div></div>')


def bar(label: str, value: float, maximum: float, right: str) -> str:
    pct = 100 * value / maximum if maximum else 0
    return (f'<div style="display:flex;align-items:center;gap:10px;margin:8px 0;font-size:13px">'
            f'<div style="width:150px;color:var(--bp-text-2)">{esc(label)}</div>'
            f'<div class="bp-bar"><div style="width:{pct:.0f}%"></div></div>'
            f'<div style="width:46px;text-align:right;color:var(--bp-text);font-weight:600">{esc(right)}</div></div>')
