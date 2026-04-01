import csv
import io
import os

import streamlit as st

from scraper import run_scraper, CSV_FIELDS

st.set_page_config(page_title="Scrapper — Target Price Scraper", page_icon="🔍", layout="wide")

st.title("🔍 Scrapper")
st.caption("Fetch live pricing data from Target.com by TCIN")

# Temp file written incrementally during a run so partial data survives
# an app restart / Streamlit free-tier sleep.
PARTIAL_FILE = "/tmp/target_scrape_partial.csv"

# ── Previous-session recovery ─────────────────────────────────────────────────

if os.path.exists(PARTIAL_FILE):
    with open(PARTIAL_FILE, newline="", encoding="utf-8") as fh:
        saved_rows = list(csv.DictReader(fh))
    if saved_rows:
        with st.expander(
            f"♻️  Previous session data available — {len(saved_rows)} row(s) saved",
            expanded=True,
        ):
            st.caption(
                "The app was interrupted mid-scrape last time.  "
                "Download what was captured, then start a new run."
            )
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(saved_rows)
            st.download_button(
                label="⬇  Download partial results",
                data=buf.getvalue().encode("utf-8"),
                file_name="target_prices_partial.csv",
                mime="text/csv",
            )
            if st.button("🗑  Discard saved data"):
                os.remove(PARTIAL_FILE)
                st.rerun()

st.divider()

# ── Input ────────────────────────────────────────────────────────────────────

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("Enter TCINs")
    raw_text = st.text_area(
        "One TCIN per line, or space/comma separated",
        height=180,
        placeholder="93513795\n93513803\n93513797",
    )

with col_right:
    st.subheader("Or upload a file")
    uploaded = st.file_uploader("Plain text file, one TCIN per line", type=["txt", "csv"])
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

if tcins:
    st.info(f"**{len(tcins)} unique TCIN(s)** ready to scrape: {', '.join(tcins[:10])}{'…' if len(tcins) > 10 else ''}")

st.divider()

# ── Run ──────────────────────────────────────────────────────────────────────

run_btn = st.button("▶  Run Scraper", type="primary", disabled=not tcins)

if run_btn and tcins:
    progress_bar  = st.progress(0, text="Starting…")
    log_area      = st.empty()
    download_slot = st.empty()   # live download button updated as rows arrive
    log_lines: list[str] = []

    # Accumulate rows here so we can offer a live download at any point.
    live_results: list[dict] = []

    def _csv_bytes(rows: list[dict]) -> bytes:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
        return buf.getvalue().encode("utf-8")

    def progress_cb(i, total, tcin, rows, error):
        nonlocal live_results
        pct = i / total
        progress_bar.progress(pct, text=f"[{i}/{total}] TCIN {tcin}")
        if error:
            log_lines.append(f"✗ {tcin} — {error}")
        else:
            log_lines.append(f"✓ {tcin} — {len(rows)} row(s)")
        log_area.code("\n".join(log_lines[-20:]))

        # Update live_results and refresh the download button.
        if rows:
            live_results.extend(rows)
        if live_results:
            download_slot.download_button(
                label=f"⬇  Download {len(live_results)} row(s) so far",
                data=_csv_bytes(live_results),
                file_name="target_prices_partial.csv",
                mime="text/csv",
                key=f"live_dl_{i}",   # unique key so Streamlit re-renders it
            )

    with st.spinner("Scraping…"):
        results = run_scraper(tcins, progress_cb=progress_cb, output_path=PARTIAL_FILE)

    progress_bar.progress(1.0, text="Done")
    download_slot.empty()   # replace live button with the final one below

    st.success(f"Scraped **{len(results)} row(s)** from {len(tcins)} TCIN(s).")

    # ── Results table ────────────────────────────────────────────────────────

    st.subheader("Results")

    ok_rows  = [r for r in results if r["status"] == "OK"]
    err_rows = [r for r in results if r["status"] != "OK"]

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

    # ── Final download ────────────────────────────────────────────────────────

    st.download_button(
        label="⬇  Download CSV",
        data=_csv_bytes(results),
        file_name="target_prices.csv",
        mime="text/csv",
    )

    # Clean up temp file now that the user has the full results.
    if os.path.exists(PARTIAL_FILE):
        os.remove(PARTIAL_FILE)
