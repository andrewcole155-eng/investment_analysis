import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf # You may need to: pip install numpy-financial

st.set_page_config(page_title="Investment Analysis", layout="wide")

st.title("🏙️ Melbourne Investment Property Tool")

# --- SIDEBAR: GLOBAL INPUTS ---
st.sidebar.header("📍 Property Basis")
purchase_price = st.sidebar.number_input("Purchase Price ($)", value=850000, step=5000)
growth_rate = st.sidebar.slider("Annual Growth (%)", 0.0, 10.0, 5.5) / 100

# --- TABS ---
tabs = st.tabs(["Property Summary", "Income & Expenses", "Loan Details", "10-Year Projection"])

with tabs[0]:
    st.subheader("Acquisition Costs")
    col1, col2 = st.columns(2)
    stamp_duty = col1.number_input("Stamp Duty", value=46000)
    legal = col2.number_input("Legal/Conveyancing", value=1800)
    total_entry = purchase_price + stamp_duty + legal
    st.metric("Total Cash Required (Approx)", f"${total_entry:,.0f}")

with tabs[1]:
    st.subheader("Cash Flow")
    weekly_rent = st.number_input("Weekly Rent ($)", value=750)
    mgt_fee_pct = st.number_input("Management Fee (%)", value=7.0) / 100
    annual_gross = weekly_rent * 52
    st.metric("Gross Annual Income", f"${annual_gross:,.0f}")

with tabs[2]:
    st.subheader("Financing & Mortgage")
    c1, c2 = st.columns(2)
    
    # Inputs
    lvr = c1.slider("LVR (%)", 0, 95, 80)
    interest_rate = c1.number_input("Interest Rate (%)", value=6.15) / 100
    loan_type = c2.selectbox("Loan Type", ["Interest Only", "Principal & Interest"])
    loan_term = c2.number_input("Loan Term (Years)", value=30)
    
    # Calculations
    loan_amount = purchase_price * (lvr / 100)
    
    if loan_type == "Interest Only":
        annual_repayment = loan_amount * interest_rate
        monthly_repayment = annual_repayment / 12
    else:
        # P&I Calculation using numpy_financial (pmt)
        monthly_repayment = abs(npf.pmt(interest_rate/12, loan_term*12, loan_amount))
        annual_repayment = monthly_repayment * 12

    st.divider()
    res1, res2, res3 = st.columns(3)
    res1.metric("Total Loan Amount", f"${loan_amount:,.0f}")
    res2.metric("Monthly Repayment", f"${monthly_repayment:,.2f}")
    res3.metric("Annual Debt Service", f"${annual_repayment:,.0f}")

with tabs[3]:
    st.subheader("Wealth Projection")
    years = np.arange(1, 11)
    future_vals = [purchase_price * (1 + growth_rate)**y for y in years]
    equity = [v - loan_amount for v in future_vals]
    
    df = pd.DataFrame({
        "Year": years, 
        "Property Value": future_vals,
        "Estimated Equity": equity
    }).set_index("Year")
    
    st.line_chart(df)