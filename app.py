import streamlit as st
import pandas as pd
import numpy as np
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Investment Property Pro", layout="wide")

# --- DATA LOADING LOGIC ---
EXCEL_PATH = r"C:\Trading System\Investment\Investment_Property.xlsx"

def load_excel_data(path):
    if os.path.exists(path):
        try:
            # We read the 'Property Summary' sheet as a starting point
            df = pd.read_excel(path, sheet_name="Property Summary")
            return df
        except Exception as e:
            st.error(f"Error reading Excel: {e}")
    return None

excel_data = load_excel_data(EXCEL_PATH)

# --- HEADER ---
st.title("🏠 Property Investment Analysis")
st.caption(f"Connected to: {EXCEL_PATH}")

# --- SIDEBAR: GLOBAL CONTROLS ---
st.sidebar.header("📍 Core Inputs")
purchase_price = st.sidebar.number_input("Purchase Price ($)", value=850000, step=10000)
growth_rate = st.sidebar.slider("Annual Growth (%)", 0.0, 10.0, 5.5) / 100
holding_period = st.sidebar.slider("Holding Period (Years)", 1, 30, 10)

# --- TABS (Mirroring your Screenshot) ---
tabs = st.tabs([
    "Property Summary", "Acquisition Costs", "Income", 
    "Operating Expenses", "Loan Details", "Depreciation", "10-Year Projections"
])

# 1. PROPERTY SUMMARY
with tabs[0]:
    st.subheader("Property Overview")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Property Address", value="Example Street, Brisbane")
        property_type = st.selectbox("Type", ["House", "Unit", "Townhouse", "Commercial"])
    with col2:
        land_size = st.number_input("Land Size (sqm)", value=450)
        year_built = st.number_input("Year Built", value=2010)

# 2. ACQUISITION COSTS
with tabs[1]:
    st.subheader("Upfront Costs")
    c1, c2 = st.columns(2)
    with c1:
        stamp_duty = st.number_input("Stamp Duty ($)", value=32000)
        legal_fees = st.number_input("Legal/Conveyancing ($)", value=1800)
    with c2:
        building_pest = st.number_input("Building & Pest ($)", value=650)
        entry_repairs = st.number_input("Initial Repairs ($)", value=0)
    
    total_entry = purchase_price + stamp_duty + legal_fees + building_pest + entry_repairs
    st.metric("Total Initial Investment", f"${total_entry:,.2f}")

# 3. INCOME
with tabs[2]:
    st.subheader("Rental Income")
    weekly_rent = st.number_input("Current Weekly Rent ($)", value=750)
    vacancy_weeks = st.slider("Vacancy (Weeks per Year)", 0, 5, 2)
    annual_gross = weekly_rent * (52 - vacancy_weeks)
    st.write(f"**Gross Annual Income:** ${annual_gross:,.2f}")

# 4. OPERATING EXPENSES
with tabs[3]:
    st.subheader("Annual Outgoings")
    rates = st.number_input("Council & Water Rates ($)", value=3500)
    mgt_fee_pct = st.number_input("Management Fee (%)", value=7.5) / 100
    insurance = st.number_input("Insurance (Landlord/Building) ($)", value=1500)
    
    total_ops = rates + insurance + (annual_gross * mgt_fee_pct)
    st.metric("Total Annual Expenses", f"${total_ops:,.2f}")

# 5. LOAN DETAILS
with tabs[4]:
    st.subheader("Financing Structure")
    lvr_pct = st.slider("LVR (%)", 0, 95, 80) / 100
    loan_amt = purchase_price * lvr_pct
    int_rate = st.number_input("Interest Rate (%)", value=6.15) / 100
    
    st.write(f"**Loan Amount:** ${loan_amt:,.2f}")
    st.write(f"**Annual Interest (IO):** ${loan_amt * int_rate:,.2f}")

# 6. DEPRECIATION
with tabs[5]:
    st.subheader("Tax Depreciation")
    div_43 = st.number_input("Building Write-off (Div 43) ($)", value=5000)
    div_40 = st.number_input("Plant & Equipment (Div 40) ($)", value=2500)
    st.info("These values reduce your taxable income but are non-cash expenses.")

# 7. PROJECTIONS (The "Brain")
with tabs[6]:
    st.subheader("10-Year Wealth Forecast")
    
    data = []
    current_val = purchase_price
    for year in range(1, holding_period + 1):
        current_val *= (1 + growth_rate)
        data.append({"Year": year, "Estimated Value": round(current_val, 2)})
    
    df_proj = pd.DataFrame(data).set_index("Year")
    st.line_chart(df_proj)
    st.table(df_proj)