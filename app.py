import csv
import io
import os
import queue
import threading
import time

import streamlit as st

from scraper import run_scraper, CSV_FIELDS

st.set_page_config(page_title="Scrapper — Target Price Scraper", page_icon="🔍", layout="wide")

st.title("🔍 Scrapper")
st.caption("Fetch live pricing data from Target.com by TCIN")

# Temp file written incrementally so partial data survives an app restart.
PARTIAL_FILE = "/tmp/target_scrape_partial.csv"

# ── Session-state bootstrap ───────────────────────────────────────────────────

def _init_state():
    defaults = {
        "scraping":        False,   # thread is running
        "paused":          False,   # user hit Pause
        "pause_event":     threading.Event(),
        "scraper_thread":  None,
        "update_queue":    queue.Queue(),
        "results":         [],      # rows settled so far
        "processed_tcins": [],      # TCINs attempted (success or error)
        "input_tcins":     [],      # full list for the current run
        "log_lines":       [],
        "progress":        (0, 0),  # (done, total)
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _csv_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _tcins_bytes(tcins: list[str]) -> bytes:
    return "\n".join(tcins).encode("utf-8")


def _pending_tcins() -> list[str]:
    done = set(st.session_state.processed_tcins)
    return [t for t in st.session_state.input_tcins if t not in done]


def _drain_queue():
    """Pull all pending progress updates from the background thread into state."""
    q = st.session_state.update_queue
    while not q.empty():
        try:
            item = q.get_nowait()
        except queue.Empty:
            break
        kind = item["kind"]
        if kind == "progress":
            st.session_state.progress = (item["i"], item["total"])
            st.session_state.log_lines.append(item["msg"])
            st.session_state.processed_tcins.append(item["tcin"])
            if item["rows"]:
                st.session_state.results.extend(item["rows"])
        elif kind == "done":
            st.session_state.scraping = False

# ── Previous-session recovery ─────────────────────────────────────────────────

if os.path.exists(PARTIAL_FILE) and not st.session_state.scraping:
    with open(PARTIAL_FILE, newline="", encoding="utf-8") as fh:
        saved_rows = list(csv.DictReader(fh))
    if saved_rows:
        with st.expander(
            f"♻️  Previous session data — {len(saved_rows)} row(s) saved",
            expanded=True,
        ):
            st.caption("The app was interrupted mid-scrape. Download what was captured.")
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(saved_rows)
            st.download_button(
                label="⬇  Download partial results",
                data=buf.getvalue().encode("utf-8"),
                file_name="target_prices_partial.csv",
                mime="text/csv",
                key="recovery_dl",
            )
            if st.button("🗑  Discard saved data", key="discard_recovery"):
                os.remove(PARTIAL_FILE)
                st.rerun()

st.divider()

# ── Input ─────────────────────────────────────────────────────────────────────

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("Enter TCINs")
    raw_text = st.text_area(
        "One TCIN per line, or space/comma separated",
        height=180,
        placeholder="93513795\n93513803\n93513797",
        disabled=st.session_state.scraping,
    )

with col_right:
    st.subheader("Or upload a file")
    uploaded = st.file_uploader(
        "Plain text file, one TCIN per line",
        type=["txt", "csv"],
        disabled=st.session_state.scraping,
    )
    if uploaded:
        content = uploaded.read().decode("utf-8", errors="ignore")
        st.caption(f"Loaded file: **{uploaded.name}**")


def collect_tcins() -> list[str]:
    lines = []
    if raw_text:
        for part in raw_text.replace(",", " ").split():
            lines.append(part.strip())
    if uploaded:
        for line in content.splitlines():
            line = line.strip()
            if line.isdigit():
                lines.append(line)
    seen = set()
    return [t for t in lines if t.isdigit() and not (t in seen or seen.add(t))]


tcins = collect_tcins()

if tcins and not st.session_state.scraping:
    st.info(
        f"**{len(tcins)} unique TCIN(s)** ready: "
        f"{', '.join(tcins[:10])}{'…' if len(tcins) > 10 else ''}"
    )

st.divider()

# ── Controls: Run / Pause / Resume ────────────────────────────────────────────

ctrl_cols = st.columns([1, 1, 4])

with ctrl_cols[0]:
    run_btn = st.button(
        "▶  Run Scraper",
        type="primary",
        disabled=st.session_state.scraping or not tcins,
    )

with ctrl_cols[1]:
    pause_btn = st.button(
        "⏸  Pause" if not st.session_state.paused else "▶  Resume",
        disabled=not st.session_state.scraping and not st.session_state.paused,
    )

# ── Start a new run ───────────────────────────────────────────────────────────

if run_btn and tcins:
    # Reset state for a fresh run.
    st.session_state.results         = []
    st.session_state.processed_tcins = []
    st.session_state.log_lines       = []
    st.session_state.progress        = (0, 0)
    st.session_state.paused          = False
    st.session_state.pause_event     = threading.Event()
    st.session_state.update_queue    = queue.Queue()
    st.session_state.input_tcins     = tcins
    st.session_state.scraping        = True

    q   = st.session_state.update_queue
    evt = st.session_state.pause_event

    def _progress_cb(i, total, tcin, rows, error):
        msg = (
            f"✗ {tcin} — {error}"
            if error and not str(error).startswith("HTTP 403")   # 403 retries shown inline
            else (f"✓ {tcin} — {len(rows)} row(s)" if rows else f"… {tcin} — {error}")
        )
        q.put({"kind": "progress", "i": i, "total": total,
               "tcin": tcin, "rows": rows or [], "msg": msg})

    def _scraper_thread():
        run_scraper(
            tcins,
            progress_cb=_progress_cb,
            output_path=PARTIAL_FILE,
            pause_event=evt,
        )
        q.put({"kind": "done"})

    t = threading.Thread(target=_scraper_thread, daemon=True)
    t.start()
    st.session_state.scraper_thread = t
    st.rerun()

# ── Handle Pause / Resume ─────────────────────────────────────────────────────

if pause_btn:
    if not st.session_state.paused:
        # Pause: signal the thread to stop after current TCIN.
        st.session_state.pause_event.set()
        st.session_state.paused = True
    else:
        # Resume: start a new thread on the remaining TCINs.
        remaining = _pending_tcins()
        if remaining:
            st.session_state.paused      = False
            st.session_state.scraping    = True
            st.session_state.pause_event = threading.Event()
            st.session_state.update_queue = queue.Queue()

            q   = st.session_state.update_queue
            evt = st.session_state.pause_event

            def _progress_cb_resume(i, total, tcin, rows, error):
                msg = (
                    f"✗ {tcin} — {error}"
                    if error and not str(error).startswith("HTTP 403")
                    else (f"✓ {tcin} — {len(rows)} row(s)" if rows else f"… {tcin} — {error}")
                )
                q.put({"kind": "progress", "i": i, "total": total,
                       "tcin": tcin, "rows": rows or [], "msg": msg})

            def _resume_thread():
                run_scraper(
                    remaining,
                    progress_cb=_progress_cb_resume,
                    output_path=PARTIAL_FILE,
                    pause_event=evt,
                )
                q.put({"kind": "done"})

            t = threading.Thread(target=_resume_thread, daemon=True)
            t.start()
            st.session_state.scraper_thread = t
    st.rerun()

# ── Live progress UI ──────────────────────────────────────────────────────────

_drain_queue()

if st.session_state.scraping or st.session_state.paused or st.session_state.results:
    done, total = st.session_state.progress
    results     = st.session_state.results
    pending     = _pending_tcins()

    # Progress bar
    if total:
        label = (
            f"[{done}/{total}] {'Paused' if st.session_state.paused else 'Scraping…'}"
        )
        st.progress(done / total, text=label)

    # Log
    if st.session_state.log_lines:
        st.code("\n".join(st.session_state.log_lines[-20:]))

    # Download row — three buttons side by side
    dl_cols = st.columns(3)
    with dl_cols[0]:
        if results:
            st.download_button(
                label=f"⬇  Results so far ({len(results)} rows)",
                data=_csv_bytes(results),
                file_name="target_prices_partial.csv",
                mime="text/csv",
                key="live_results_dl",
            )
    with dl_cols[1]:
        if pending:
            st.download_button(
                label=f"⬇  Pending TCINs ({len(pending)})",
                data=_tcins_bytes(pending),
                file_name="pending_tcins.txt",
                mime="text/plain",
                key="pending_dl",
            )
    with dl_cols[2]:
        if st.session_state.processed_tcins:
            st.download_button(
                label=f"⬇  Processed TCINs ({len(st.session_state.processed_tcins)})",
                data=_tcins_bytes(st.session_state.processed_tcins),
                file_name="processed_tcins.txt",
                mime="text/plain",
                key="processed_dl",
            )

    # Auto-refresh while the thread is alive.
    if st.session_state.scraping:
        time.sleep(0.5)
        st.rerun()

# ── Final results (run complete, not paused) ──────────────────────────────────

if not st.session_state.scraping and not st.session_state.paused and st.session_state.results:
    results  = st.session_state.results
    ok_rows  = [r for r in results if r["status"] == "OK"]
    err_rows = [r for r in results if r["status"] != "OK"]

    st.success(f"Scraped **{len(results)} row(s)** from {len(st.session_state.processed_tcins)} TCIN(s).")

    st.subheader("Results")
    tab_all, tab_ok, tab_err = st.tabs([
        f"All ({len(results)})",
        f"OK ({len(ok_rows)})",
        f"Errors ({len(err_rows)})",
    ])

    def show_table(rows):
        if not rows:
            st.write("No rows.")
            return
        st.dataframe(rows, use_container_width=True)

    with tab_all:
        show_table(results)
    with tab_ok:
        show_table(ok_rows)
    with tab_err:
        show_table(err_rows)

    st.download_button(
        label="⬇  Download full CSV",
        data=_csv_bytes(results),
        file_name="target_prices.csv",
        mime="text/csv",
        key="final_dl",
    )

    # Clean up the temp file only when everything completed (not just paused).
    if os.path.exists(PARTIAL_FILE):
        os.remove(PARTIAL_FILE)
