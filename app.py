import io
import csv

import streamlit as st

from scraper import run_scraper, CSV_FIELDS

st.set_page_config(page_title="Scrapper — Target Price Scraper", page_icon="🔍", layout="wide")

st.title("🔍 Scrapper")
st.caption("Fetch live pricing data from Target.com by TCIN")

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
    progress_bar = st.progress(0, text="Starting…")
    log_area     = st.empty()
    log_lines: list[str] = []

    def progress_cb(i, total, tcin, rows, error):
        pct = i / total
        progress_bar.progress(pct, text=f"[{i}/{total}] TCIN {tcin}")
        if error:
            log_lines.append(f"✗ {tcin} — {error}")
        else:
            log_lines.append(f"✓ {tcin} — {len(rows)} row(s)")
        log_area.code("\n".join(log_lines[-20:]))  # show last 20 lines

    with st.spinner("Scraping…"):
        results = run_scraper(tcins, progress_cb=progress_cb)

    progress_bar.progress(1.0, text="Done")

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

    # ── Download ─────────────────────────────────────────────────────────────

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows(results)

    st.download_button(
        label="⬇  Download CSV",
        data=buf.getvalue().encode("utf-8"),
        file_name="target_prices.csv",
        mime="text/csv",
    )
