"""
RSSB Bhayander Dera - Fan Dashboard (Streamlit version)

Run:   streamlit run app.py
Optional PIN:   ACCESS_PIN=1234 streamlit run app.py      (or put ACCESS_PIN in .streamlit/secrets.toml)
Optional data file location:   DATA_FILE=/path/to/data.json streamlit run app.py

All fan reports live in one JSON file that every open browser shares, and the
screen refreshes itself every few seconds so people see each other's updates.
"""
import hmac
import json
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

# --------------------------------------------------------------------------
# Config (same layout as the original app)
# --------------------------------------------------------------------------
COLS = [1, 3, 5, 7, 9]          # pole columns: 1xx, 3xx, 5xx, 7xx, 9xx
ROWS = 18                        # pole rows per column
FANS = 20                        # fans per pole
ISSUES = ["Vibration", "Bearing issue", "Capacitor issue", "Dead fan"]
DEAD = 3                         # index of "Dead fan" in ISSUES
SOON = ["Canteen", "Langar", "Outside"]
REFRESH_SECONDS = 5

DATA_FILE = Path(os.environ.get("DATA_FILE") or Path(__file__).with_name("data.json"))


def get_pin() -> str:
    pin = os.environ.get("ACCESS_PIN", "")
    if not pin:
        try:
            pin = str(st.secrets.get("ACCESS_PIN", ""))
        except Exception:
            pin = ""
    return pin


st.set_page_config(page_title="RSSB Bhayander Dera", page_icon="🌀", layout="centered")


# --------------------------------------------------------------------------
# Shared storage (one JSON file, safe for several browsers at once)
# --------------------------------------------------------------------------
@st.cache_resource
def _lock() -> threading.Lock:
    return threading.Lock()


def load_data() -> dict:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_FILE.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, DATA_FILE)  # atomic swap


def valid_pole(p: int) -> bool:
    return p // 100 in COLS and 1 <= p % 100 <= ROWS


def save_fan(pole: int, fan: int, issues: list, note: str) -> None:
    if not valid_pole(pole) or not 1 <= fan <= FANS:
        return
    issues = sorted({int(i) for i in issues if 0 <= int(i) < len(ISSUES)})
    note = (note or "")[:500]
    with _lock():
        data = load_data()
        key = f"{pole}-{fan}"
        if issues or note.strip():
            data[key] = {"i": issues, "n": note, "t": int(time.time() * 1000)}
        else:
            data.pop(key, None)
        _write(data)


def reset_all() -> None:
    with _lock():
        _write({})


# --------------------------------------------------------------------------
# Helpers for status / stats
# --------------------------------------------------------------------------
def fan_status(data: dict, pole: int, fan: int) -> str:
    d = data.get(f"{pole}-{fan}")
    if not d:
        return "ok"
    if DEAD in d.get("i", []):
        return "bad"
    if d.get("i"):
        return "warn"
    if d.get("n", "").strip():
        return "note"
    return "ok"


def pole_status(data: dict, pole: int):
    count, worst = 0, "ok"
    for n in range(1, FANS + 1):
        s = fan_status(data, pole, n)
        if s in ("bad", "warn"):
            count += 1
        if s == "bad":
            worst = "bad"
        elif s == "warn" and worst != "bad":
            worst = "warn"
        elif s == "note" and worst == "ok":
            worst = "note"
    return count, worst


def all_poles():
    return [c * 100 + r for r in range(1, ROWS + 1) for c in COLS]


def overall_stats(data: dict):
    faulty = dead = poles_hit = 0
    for p in all_poles():
        c, _ = pole_status(data, p)
        if c:
            poles_hit += 1
        for n in range(1, FANS + 1):
            s = fan_status(data, p, n)
            if s == "bad":
                dead += 1
                faulty += 1
            elif s == "warn":
                faulty += 1
    return faulty, dead, poles_hit


# --------------------------------------------------------------------------
# Styling (colours match the original dashboard)
# --------------------------------------------------------------------------
CSS = """
<style>
.block-container{max-width:980px;padding-top:2rem;padding-bottom:4rem}
h1{font-family:Georgia,serif;letter-spacing:-.01em}

/* keep the pole map / fan grid as real grids on phones (Streamlit stacks columns by default) */
.st-key-map [data-testid="stHorizontalBlock"],
.st-key-fans [data-testid="stHorizontalBlock"]{flex-wrap:nowrap !important;gap:.35rem !important}
.st-key-map [data-testid="stColumn"],
.st-key-fans [data-testid="stColumn"]{min-width:0 !important;flex:1 1 0 !important;width:auto !important}
.st-key-map [data-testid="stVerticalBlock"],
.st-key-fans [data-testid="stVerticalBlock"]{gap:.35rem}
.st-key-map button,.st-key-fans button{width:100%;padding:.35rem 0;min-height:2.4rem;font-weight:600;border-width:2px}
.st-key-map button p,.st-key-fans button p{font-size:13px;white-space:nowrap}
.rowlabel{font-size:12px;color:#5a726f;text-align:right;padding-top:.6rem}
.colhead{font-size:12px;color:#5a726f;text-align:center;font-weight:600}

/* status colours (text colour is set too so it reads fine in light and dark themes) */
[class*="st-key-pole_ok_"] button,[class*="st-key-fan_ok_"] button{background:#dff1e6;border-color:#2f8a58;color:#1f6b41}
[class*="st-key-pole_warn_"] button,[class*="st-key-fan_warn_"] button{background:#fbeccb;border-color:#b57a00;color:#7d5400}
[class*="st-key-pole_bad_"] button,[class*="st-key-fan_bad_"] button{background:#f8dad5;border-color:#bf3b2b;color:#9a2a1d}
[class*="st-key-pole_note_"] button,[class*="st-key-fan_note_"] button{background:#dce8f5;border-color:#3a6ea5;color:#264f7c}
[class*="st-key-fan_"] button{border-radius:999px;aspect-ratio:1;min-height:0}

/* stat cards + legend */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:14px 0}
.stat{border:1px solid rgba(128,128,128,.35);border-radius:12px;padding:10px 14px}
.stat b{display:block;font:700 28px/1.1 Georgia,serif}
.stat span{opacity:.7;font-size:13px}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;opacity:.85;margin-bottom:10px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:4px;vertical-align:-1px;margin-right:6px;border:2px solid}
.l-ok{background:#dff1e6;border-color:#2f8a58}.l-warn{background:#fbeccb;border-color:#b57a00}
.l-bad{background:#f8dad5;border-color:#bf3b2b}.l-note{background:#dce8f5;border-color:#3a6ea5}

/* issue log buttons */
.st-key-log button{width:100%;text-align:left;justify-content:flex-start}
.st-key-log button p{text-align:left;white-space:pre-wrap}
</style>
"""

# --------------------------------------------------------------------------
# Navigation state + callbacks
# --------------------------------------------------------------------------
st.session_state.setdefault("view", "home")
st.session_state.setdefault("pole", None)
st.session_state.setdefault("fan", None)
st.session_state.setdefault("soon_name", "")
st.session_state.setdefault("confirm_reset", False)
st.session_state.setdefault("authed", False)


def go(view: str, name: str = ""):
    st.session_state.view = view
    st.session_state.soon_name = name
    st.session_state.pole = None
    st.session_state.fan = None
    st.session_state.confirm_reset = False


def open_pole(p: int):
    st.session_state.pole = p
    st.session_state.fan = None


def open_fan(p: int, n: int):
    data = load_data()
    d = data.get(f"{p}-{n}", {"i": [], "n": ""})
    st.session_state.pole = p
    st.session_state.fan = n
    for i in range(len(ISSUES)):
        st.session_state[f"iss_{i}"] = i in d.get("i", [])
    st.session_state["fan_note"] = d.get("n", "")


def back_to_pole():
    st.session_state.fan = None


def close_sheet():
    st.session_state.pole = None
    st.session_state.fan = None


def do_save(clear: bool = False):
    p, n = st.session_state.pole, st.session_state.fan
    if clear:
        save_fan(p, n, [], "")
        st.toast("Marked fixed")
    else:
        issues = [i for i in range(len(ISSUES)) if st.session_state.get(f"iss_{i}")]
        save_fan(p, n, issues, st.session_state.get("fan_note", ""))
        st.toast("Saved")
    st.session_state.fan = None


def do_reset():
    reset_all()
    st.session_state.confirm_reset = False
    st.toast("All reports cleared")


# --------------------------------------------------------------------------
# Screens
# --------------------------------------------------------------------------
def screen_home(data: dict):
    faulty, _, _ = overall_stats(data)
    st.title("RSSB Bhayander Dera")
    st.caption("Choose an area to check its fans and report problems.")
    total_poles = len(COLS) * ROWS
    summary = f"{faulty} fans need attention" if faulty else "No open issues"
    st.button(
        f"**Pandal**\n\n{total_poles} poles · {total_poles * FANS} fans · {summary}",
        key="tile_pandal", use_container_width=True, on_click=go, args=("pandal",),
    )
    cols = st.columns(len(SOON))
    for col, name in zip(cols, SOON):
        with col:
            st.button(f"**{name}**\n\nLayout coming soon", key=f"tile_{name}",
                      use_container_width=True, on_click=go, args=("soon", name))


def screen_soon():
    st.button("← Back", on_click=go, args=("home",))
    st.title(st.session_state.soon_name)
    st.caption("This layout hasn't been added yet. Share its sketch and it will appear here.")


def screen_fan_form():
    p, n = st.session_state.pole, st.session_state.fan
    st.button("✕ Close", key="close_form", on_click=close_sheet)
    st.header(f"Fan {n}")
    st.caption(f"Pole {p}")
    for i, name in enumerate(ISSUES):
        st.checkbox(name, key=f"iss_{i}")
    st.text_area("Note / feedback", key="fan_note", max_chars=500,
                 placeholder="Describe the problem, noise, or what was done")
    c1, c2, c3 = st.columns(3)
    c1.button("All fans", use_container_width=True, on_click=back_to_pole)
    c2.button("Mark fixed", use_container_width=True, on_click=do_save, args=(True,))
    c3.button("Save", type="primary", use_container_width=True, on_click=do_save)


def screen_pole(data: dict):
    p = st.session_state.pole
    st.button("✕ Close", key="close_pole", on_click=close_sheet)
    st.header(f"Pole {p}")
    st.caption("Tap a fan to report an issue")
    with st.container(key="fans"):
        n = 1
        for _ in range(FANS // 5):
            cols = st.columns(5)
            for col in cols:
                with col:
                    s = fan_status(data, p, n)
                    st.button(str(n), key=f"fan_{s}_{n}", on_click=open_fan, args=(p, n))
                n += 1


def screen_pandal(data: dict):
    faulty, dead, poles_hit = overall_stats(data)
    st.button("← Back", on_click=go, args=("home",))
    st.title("Pandal")
    st.caption("Tap a pole to open its 20 fans.")

    st.markdown(
        f"""<div class="stats">
        <div class="stat"><b>{len(COLS) * ROWS * FANS}</b><span>Total fans</span></div>
        <div class="stat"><b>{faulty}</b><span>Fans with issues</span></div>
        <div class="stat"><b>{dead}</b><span>Dead fans</span></div>
        <div class="stat"><b>{poles_hit}</b><span>Poles affected</span></div></div>
        <div class="legend"><span><i class="l-ok"></i>All fine</span><span><i class="l-warn"></i>Has issues</span>
        <span><i class="l-bad"></i>Dead fan</span><span><i class="l-note"></i>Note only</span></div>""",
        unsafe_allow_html=True,
    )

    # pole map
    with st.container(key="map"):
        head = st.columns([0.6] + [1] * len(COLS))
        for col, c in zip(head[1:], COLS):
            col.markdown(f'<div class="colhead">{c}xx</div>', unsafe_allow_html=True)
        for r in range(1, ROWS + 1):
            row = st.columns([0.6] + [1] * len(COLS))
            row[0].markdown(f'<div class="rowlabel">{r:02d}</div>', unsafe_allow_html=True)
            for col, c in zip(row[1:], COLS):
                p = c * 100 + r
                count, worst = pole_status(data, p)
                label = f"{p}" + (f"·{count}" if count else "")
                col.button(label, key=f"pole_{worst}_{p}", on_click=open_pole, args=(p,),
                           help=f"Pole {p}: {count} faulty fans")

    # issue log
    st.subheader("Issue log")
    items = []
    for p in all_poles():
        for n in range(1, FANS + 1):
            d = data.get(f"{p}-{n}")
            if d and (d.get("i") or d.get("n", "").strip()):
                items.append((p, n, d))
    if not items:
        st.info("No issues reported yet. Open a pole and tap a fan to add one.")
    with st.container(key="log"):
        for p, n, d in items:
            kinds = ", ".join(ISSUES[i] for i in d.get("i", [])) or "Note only"
            when = datetime.fromtimestamp(d["t"] / 1000).strftime("%d %b %Y, %H:%M") if d.get("t") else ""
            label = f"**{p} · Fan {n}** — {kinds}"
            if d.get("n", "").strip():
                label += f"\n\n{d['n']}"
            if when:
                label += f"\n\n_{when}_"
            st.button(label, key=f"log_{p}_{n}", on_click=open_fan, args=(p, n))

    # reset
    st.write("")
    if not st.session_state.confirm_reset:
        st.button("Clear all reports", key="ask_reset",
                  on_click=lambda: st.session_state.update(confirm_reset=True))
    else:
        st.warning("Clear every fan report for EVERYONE? This can't be undone.")
        a, b = st.columns(2)
        a.button("Yes, clear everything", type="primary", use_container_width=True, on_click=do_reset)
        b.button("Cancel", use_container_width=True,
                 on_click=lambda: st.session_state.update(confirm_reset=False))


# --------------------------------------------------------------------------
# Main (wrapped in a fragment so it refreshes itself to show other people's updates)
# --------------------------------------------------------------------------
def main():
    data = load_data()
    view = st.session_state.view
    if view == "soon":
        screen_soon()
    elif view == "pandal":
        if st.session_state.pole is not None and st.session_state.fan is not None:
            screen_fan_form()
        elif st.session_state.pole is not None:
            screen_pole(data)
        else:
            screen_pandal(data)
    else:
        screen_home(data)


st.markdown(CSS, unsafe_allow_html=True)

PIN = get_pin()
if PIN and not st.session_state.authed:
    st.title("RSSB Bhayander Dera")
    entered = st.text_input("Enter access PIN", type="password")
    if entered:
        if hmac.compare_digest(entered, PIN):
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Wrong PIN")
else:
    # Auto-refresh every few seconds, except while someone is typing in the fan form
    editing = st.session_state.pole is not None and st.session_state.fan is not None
    st.fragment(main, run_every=None if editing else REFRESH_SECONDS)()
