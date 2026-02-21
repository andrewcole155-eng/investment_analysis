import streamlit as st
import pandas as pd
import numpy as np

# Page Configuration
st.set_page_config(page_title="MelbInvestments Analysis", layout="wide")

st.title("🏙️ Melbourne Investment Property Tool")
st.markdown("---")

# --- SIDEBAR (Global Variables) ---
st.sidebar.header("📍 Core Assumptions")
purchase_price = st.sidebar.number_input("Purchase Price ($)", value=850000, step=5000)
growth_rate = st.sidebar.slider("Expected Annual Growth (%)", 0.0, 10.0, 5.0) / 100

# --- TABS (Mirroring your Excel Worksheets) ---
tabs = st.tabs([
    "Property Summary", 
    "Acquisition Costs", 
    "Income", 
    "Operating Expenses", 
    "Loan Details", 
    "Depreciation",
    "10-Year Projection"
])

# Tab 1: Property Summary
with tabs[0]:
    st.subheader("Property Overview")
    st.text_input("Property Address", "Example St, Melbourne, VIC")
    st.date_input("Settlement Date")

# Tab 2: Acquisition Costs
with tabs[1]:
    st.subheader("Initial Outlay")
    col1, col2 = st.columns(2)
    stamp_duty = col1.number_input("Stamp Duty (VIC)", value=46000)
    legal_fees = col2.number_input("Legal/Conveyancing", value=1500)
    total_entry = purchase_price + stamp_duty + legal_fees
    st.metric("Total Initial Cost", f"${total_entry:,.0f}")

# Tab 3: Income
with tabs[2]:
    st.subheader("Rental Revenue")
    weekly_rent = st.number_input("Weekly Rent ($)", value=650)
    annual_income = weekly_rent * 52
    st.write(f"**Gross Annual Income:** ${annual_income:,.2f}")

# Tab 4: Operating Expenses
with tabs[3]:
    st.subheader("Annual Running Costs")
    rates = st.number_input("Rates & Water", value=2800)
    mgt_fee = st.number_input("Management Fee (%)", value=7.0) / 100
    insurance = st.number_input("Landlord Insurance", value=1200)
    total_exp = rates + insurance + (annual_income * mgt_fee)
    st.metric("Total Yearly Expenses", f"${total_exp:,.2f}")

# Tab 7: 10-Year Projection
with tabs[6]:
    st.subheader("Capital Growth & ROI")
    years = np.arange(1, 11)
    future_values = [purchase_price * (1 + growth_rate)**y for y in years]
    df = pd.DataFrame({"Year": years, "Estimated Value": future_values}).set_index("Year")
    
    st.line_chart(df)
    st.dataframe(df.style.format("${:,.0f}"))