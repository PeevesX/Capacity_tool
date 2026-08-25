
import io

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from planner_core import (
    REQUIRED_CALENDAR_COLS,
    REQUIRED_ORDER_COLS,
    build_monthly_summary,
    process_orders,
    validate_columns,
)

st.set_page_config(page_title="Tarak Hattı Fizibilite Planlayıcı", layout="wide")
col1, col2 = st.columns([1, 5], vertical_alignment="center")
with col1:
    st.image("ototeks_logo.svg", width=600)   # bump this number until it looks right
with col2:
    st.title("Tarak Hattı Fizibilite Planlayıcı")


def read_any(uploaded_file) -> pd.DataFrame:
    """Read an uploaded .xlsx or .csv into a dataframe."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    return pd.read_excel(uploaded_file)


# ---------- Sidebar: uploads + OEE ----------
st.sidebar.header("1. Dosya Yükle")
calendar_file = st.sidebar.file_uploader(
    "Takvim (hat, ay, çalışma_günleri, günlük_çalışma_saati)",
    type=["xlsx", "csv"],
)
orders_file = st.sidebar.file_uploader(
    "Siparişler (sipariş no, ürün, hat, ay, birim, miktar,"
    " genişlik(m), uzunluk(m), metre_başına_çevrim_süresi(sn))",
    type=["xlsx", "csv"],
)

st.sidebar.header("2. Hat OEE Değerlerini Girin")
st.sidebar.caption("Algılanan hatlar için OEE değerleri dosyadan otomatik olarak doldurulur.")

# ---------- Main logic ----------
if not calendar_file or not orders_file:
    st.info("Başlamak için takvim ve sipariş dosyalarını sol sütundaki uygun yerlere yükleyin.")
    st.stop()

try:
    calendar_df = read_any(calendar_file)
    orders_df = read_any(orders_file)
    validate_columns(calendar_df, REQUIRED_CALENDAR_COLS, "Calendar file")
    validate_columns(orders_df, REQUIRED_ORDER_COLS, "Orders file")
except Exception as e:
    st.error(f"Dosya okunurken hata oluştu: {e}")
    st.stop()

lines = sorted(orders_df["line"].dropna().unique())
if not lines:
    st.error("Sipariş dosyasında 'hat' sütununda değer bulunamadı.")
    st.stop()

oee_by_line = {}
for line in lines:
    oee_by_line[line] = st.sidebar.number_input(
        f"OEE — {line}", min_value=0.01, max_value=1.0, value=0.78, step=0.01
    )

with st.expander("Önizleme: Takvim ve Siparişler"):
    c1, c2 = st.columns(2)
    c1.write("Calendar")
    c1.dataframe(calendar_df, use_container_width=True)
    c2.write("Orders")
    c2.dataframe(orders_df, use_container_width=True)

try:
    processed_orders = process_orders(orders_df, oee_by_line)
    summary = build_monthly_summary(processed_orders, calendar_df)
except Exception as e:
    st.error(f"Hesaplama hatası: {e}")
    st.stop()

# ---------- Results, one tab per line ----------
tabs = st.tabs(list(lines))
for tab, line in zip(tabs, lines):
    
    with tab:
        line_summary = summary[summary["line"] == line].reset_index(drop=True)
        st.subheader(f"{line} — aylık özet")

        col_table, col_chart = st.columns([2.5, 2])

        with col_table:
            line_summary_tr = line_summary.rename(columns={
                "month": "Ay",
                "working_days": "Çalışma Günleri",
                "hours_per_day": "Günlük Çalışma Saati",
                "capacity_hours": "Kapasite Saatleri",
                "required_hours": "Gereken Süre",
                "utilization_pct": "Doluluk %",
            })
            st.dataframe(
                line_summary_tr[
                    ["Ay", "Çalışma Günleri", "Günlük Çalışma Saati", "Kapasite Saatleri",
                     "Gereken Süre", "Doluluk %"]
                ].style.format({
                    "Kapasite Saatleri": "{:.0f}",
                    "Gereken Süre": "{:.1f}",
                    "Doluluk %": "{:.1f}%",
                }),
                use_container_width=True,
            )

        with col_chart:
            fig, ax1 = plt.subplots(figsize=(7, 5))
            x = range(len(line_summary))
            width = 0.35
            ax1.bar([i - width / 2 for i in x], line_summary["capacity_hours"],
                    width, label="Kapasite (sa)", color="#4C72B0")
            ax1.bar([i + width / 2 for i in x], line_summary["required_hours"],
                    width, label="Gereken (sa)", color="#DD8452")
            ax1.set_xticks(list(x))
            ax1.set_xticklabels(line_summary["month"], rotation=45)
            ax1.set_ylabel("Saatler")
            ax1.legend(loc="upper left")

            ax2 = ax1.twinx()
            ax2.plot(x, line_summary["utilization_pct"], color="black",
                      marker="o", label="Doluluk %")
            ax2.axhline(100, color="red", linestyle="--", linewidth=1)
            ax2.set_ylabel("Doluluk %")
            ax2.legend(loc="upper right")

            plt.title(f"{line}: Kapasite vs Gereken Süre ve Doluluk")
            fig.tight_layout()
            st.pyplot(fig)

        csv_bytes = line_summary.to_csv(index=False).encode("utf-8")
        st.download_button(
            f"Download {line} summary as CSV",
            data=csv_bytes,
            file_name=f"{line}_monthly_summary.csv",
            mime="text/csv",
        )