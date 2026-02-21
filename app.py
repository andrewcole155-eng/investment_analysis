import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
from fpdf import FPDF
import matplotlib.pyplot as plt
import io
import os

# --- PAGE SETUP ---
st.set_page_config(page_title="Investment Analysis", layout="wide")
st.title("🏙️ Property Investment Analyzer")
st.markdown("---")

# --- 1. GLOBAL INPUTS (SIDEBAR) ---
st.sidebar.header("📍 Core Parameters")
purchase_price = st.sidebar.number_input("Purchase Price ($)", value=850000, step=10000)
salary = st.sidebar.number_input("Your Annual Salary ($)", value=120000, step=5000)
growth_rate = st.sidebar.slider("Expected Annual Growth (%)", 0.0, 12.0, 5.0, step=0.5) / 100
holding_period = st.sidebar.slider("Holding Period (Years)", 1, 30, 10)

# --- 2. CREATE TABS ---
# We define the tabs here, then fill them sequentially so variables pass down correctly.
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Property & Acquisition", 
    "Income & Expenses", 
    "Loan Details", 
    "Depreciation", 
    "Tax & Gearing", 
    "10-Year Projections",
    "CGT Projection"
])

# --- TAB 1: ACQUISITION ---
with tab1:
    st.subheader("Initial Outlay")
    col1, col2 = st.columns(2)
    stamp_duty = col1.number_input("Stamp Duty ($)", value=46000, step=1000)
    legal_fees = col2.number_input("Legal & Conveyancing ($)", value=1800, step=100)
    building_pest = col1.number_input("Building & Pest ($)", value=600, step=50)
    other_entry = col2.number_input("Other Entry Costs ($)", value=1000, step=100)
    
    total_acquisition_costs = stamp_duty + legal_fees + building_pest + other_entry
    total_cost_base = purchase_price + total_acquisition_costs
    
    st.metric("Total Acquisition Costs", f"${total_acquisition_costs:,.0f}")
    st.metric("Total Required (Property + Costs)", f"${total_cost_base:,.0f}")

# --- TAB 2: INCOME & EXPENSES ---
with tab2:
    st.subheader("Cash Flow Essentials")
    c1, c2 = st.columns(2)
    
    # Income
    weekly_rent = c1.number_input("Weekly Rent ($)", value=750, step=10)
    vacancy_weeks = c1.number_input("Vacancy (Weeks/Year)", value=2, step=1)
    annual_gross_income = weekly_rent * (52 - vacancy_weeks)
    
    # Expenses
    rates = c2.number_input("Council & Water Rates ($)", value=3200, step=100)
    insurance = c2.number_input("Landlord Insurance ($)", value=1500, step=100)
    mgt_fee_pct = c2.number_input("Management Fee (%)", value=7.5, step=0.5) / 100
    maintenance = c2.number_input("Maintenance Buffer ($)", value=1500, step=100)
    
    mgt_fee_cost = annual_gross_income * mgt_fee_pct
    total_operating_expenses = rates + insurance + mgt_fee_cost + maintenance
    
    st.divider()
    metric_col1, metric_col2 = st.columns(2)
    metric_col1.metric("Gross Annual Income", f"${annual_gross_income:,.0f}")
    metric_col2.metric("Total Annual Expenses", f"${total_operating_expenses:,.0f}")

# --- TAB 3: LOAN DETAILS ---
with tab3:
    st.subheader("Financing Structure")
    lvr_pct = st.slider("LVR (%)", 0, 100, 80) / 100
    interest_rate = st.number_input("Interest Rate (%)", value=6.15, step=0.1) / 100
    loan_term = st.number_input("Loan Term (Years)", value=30, step=1)
    loan_type = st.selectbox("Repayment Type", ["Interest Only", "Principal & Interest"])
    
    loan_amount = purchase_price * lvr_pct
    
    if loan_type == "Interest Only":
        annual_interest = loan_amount * interest_rate
        annual_repayment = annual_interest
    else:
        # P&I math using numpy_financial
        monthly_repayment = abs(npf.pmt(interest_rate/12, loan_term*12, loan_amount))
        annual_repayment = monthly_repayment * 12
        # For year 1 tax purposes, we estimate the interest portion
        annual_interest = loan_amount * interest_rate 
        
    st.divider()
    l_col1, l_col2, l_col3 = st.columns(3)
    l_col1.metric("Loan Amount", f"${loan_amount:,.0f}")
    l_col2.metric("Annual Interest (Tax Deductible)", f"${annual_interest:,.0f}")
    l_col3.metric("Total Annual Repayment", f"${annual_repayment:,.0f}")

# --- TAB 4: DEPRECIATION ---
with tab4:
    st.subheader("Tax Depreciation (Non-Cash Deductions)")
    div_43 = st.number_input("Capital Works (Div 43) ($)", value=6000, step=500)
    div_40 = st.number_input("Plant & Equipment (Div 40) ($)", value=2500, step=500)
    total_depreciation = div_43 + div_40
    st.metric("Total Annual Depreciation", f"${total_depreciation:,.0f}")

# --- TAB 5: TAX & NEGATIVE GEARING ---
with tab5:
    st.subheader("Tax Impact & Cash Flow")
    
    # 1. Tax Logic (Stage 3 Australian Tax Brackets)
    def calculate_tax(income):
        if income <= 18200: return 0
        elif income <= 45000: return (income - 18200) * 0.16
        elif income <= 135000: return 4288 + (income - 45000) * 0.30
        elif income <= 190000: return 31288 + (income - 135000) * 0.37
        else: return 51638 + (income - 190000) * 0.45

    # 2. Accounting logic for Year 1
    total_tax_deductions = total_operating_expenses + annual_interest + total_depreciation
    taxable_property_income = annual_gross_income - total_tax_deductions
    
    # 3. Tax Refund Calculation
    base_tax = calculate_tax(salary)
    new_taxable_income = max(0, salary + taxable_property_income)
    new_tax = calculate_tax(new_taxable_income)
    tax_variance = base_tax - new_tax
    
    # 4. Out of Pocket Cash Flow Logic
    pre_tax_cashflow = annual_gross_income - (total_operating_expenses + annual_repayment)
    post_tax_cashflow = pre_tax_cashflow + tax_variance

    t_col1, t_col2 = st.columns(2)
    t_col1.metric("Pre-Tax Cash Flow (Annual)", f"${pre_tax_cashflow:,.0f}")
    
    if tax_variance > 0:
        t_col2.metric("Estimated Tax Refund", f"${tax_variance:,.0f}")
    else:
        t_col2.metric("Estimated Tax Payable", f"${abs(tax_variance):,.0f}")
        
    st.metric("Net Post-Tax Cash Flow (Annual)", f"${post_tax_cashflow:,.0f}")
    if post_tax_cashflow < 0:
        st.write(f"⚠️ This property costs you **${abs(post_tax_cashflow)/52:,.0f} per week** out of pocket to hold.")
    else:
        st.write(f"✅ This property puts **${post_tax_cashflow/52:,.0f} per week** in your pocket.")

# --- TAB 6: 10-YEAR PROJECTIONS ---
with tab6:
    st.subheader("Equity & Growth Forecast")
    
    years = np.arange(1, holding_period + 1)
    # Simple compound growth
    future_values = [purchase_price * (1 + growth_rate)**y for y in years]
    # Simple equity (Assuming interest-only for the chart to keep it clean)
    equity = [val - loan_amount for val in future_values]
    
    df_chart = pd.DataFrame({
        "Year": years,
        "Property Value": future_values,
        "Equity": equity
    }).set_index("Year")
    
    st.line_chart(df_chart)
    
    # Show data table
    st.write("Detailed Breakdown")
    st.dataframe(df_chart.style.format("${:,.0f}"))

# --- TAB 7: CGT PROJECTION ---
with tab7:
    st.subheader("Capital Gains Tax (Year 10 Sale)")
    
    # We grab the Year 10 value from the projections
    sale_price = future_values[-1] 
    
    # Matching your Excel logic
    capital_gain = sale_price - purchase_price
    cgt_discount = capital_gain * 0.50  # 50% discount for holding > 12 months
    
    # Estimate marginal tax rate based on salary (or allow manual input like your Excel)
    est_marginal_rate = st.number_input("Marginal Tax Rate for Sale Year (%)", value=35.0) / 100
    
    cgt_payable = cgt_discount * est_marginal_rate
    net_profit_on_sale = capital_gain - cgt_payable

    st.divider()
    c_col1, c_col2 = st.columns(2)
    c_col1.metric("Estimated Sale Price (Year 10)", f"${sale_price:,.0f}")
    c_col1.metric("Gross Capital Gain", f"${capital_gain:,.0f}")
    
    c_col2.metric("Estimated CGT Payable", f"${cgt_payable:,.0f}")
    c_col2.metric("Net Profit After Tax", f"${net_profit_on_sale:,.0f}")

# --- PDF GENERATION LOGIC ---
st.markdown("---")
st.subheader("📄 Export Analysis Report")

def generate_pdf():
    class InvestmentReportPDF(FPDF):
        def header(self):
            # FIXED LOGO PATH (Relative path - ensure image is in same folder as app.py)
            logo_path = "AQI_Logo.png" 
            if os.path.exists(logo_path):
                self.image(logo_path, 10, 8, 30)
            
            self.set_font("helvetica", "B", 20)
            self.set_text_color(0, 51, 102)
            self.cell(40) 
            self.cell(0, 15, "Property Investment Analysis", ln=True, align="L")
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font("helvetica", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, f"Page {self.page_no()}", align="C")

        def section_header(self, title):
            self.set_font("helvetica", "B", 14)
            self.set_fill_color(230, 240, 255)
            self.set_text_color(0, 0, 0)
            self.cell(0, 10, f"  {title}", ln=True, fill=True)
            self.ln(3)

        def row(self, label, value):
            self.set_font("helvetica", "", 12)
            self.cell(90, 8, label, border=0)
            self.set_font("helvetica", "B", 12)
            self.cell(0, 8, value, ln=True, border=0)

    pdf = InvestmentReportPDF()
    pdf.add_page()
    
    # 1. Acquisition
    pdf.section_header("1. Acquisition & Capital Required")
    pdf.row("Purchase Price:", f"${purchase_price:,.0f}")
    pdf.row("Total Entry Costs:", f"${total_acquisition_costs:,.0f}")
    pdf.row("Total Funds Required:", f"${total_cost_base:,.0f}")
    pdf.ln(5)
    
    # 2. Cash Flow
    pdf.section_header("2. Annual Cash Flow & Tax Impact")
    pdf.row("Gross Annual Income:", f"${annual_gross_income:,.0f}")
    pdf.row("Total Operating Expenses:", f"${total_operating_expenses:,.0f}")
    pdf.row("Annual Debt Servicing:", f"${annual_repayment:,.0f}")
    pdf.row("Net Post-Tax Cash Flow:", f"${post_tax_cashflow:,.0f}")
    pdf.ln(5)
    
    # 3. Projections
    pdf.section_header("3. 10-Year Wealth Forecast")
    pdf.row("Estimated Property Value (Year 10):", f"${future_values[-1]:,.0f}")
    pdf.row("Estimated Equity (Year 10):", f"${equity[-1]:,.0f}")
    pdf.ln(5)

    # 4. CGT & Sale Profit (NEW)
    pdf.section_header("4. Sale & Capital Gains Tax (Year 10)")
    pdf.row("Estimated Capital Gain:", f"${capital_gain:,.0f}")
    pdf.row("Estimated CGT Payable:", f"${cgt_payable:,.0f}")
    pdf.row("Net Profit (After Tax):", f"${net_profit_on_sale:,.0f}")
    pdf.ln(5)

    # Chart Generation
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(df_chart.index, df_chart["Property Value"], label="Property Value", color="#1f77b4", linewidth=2)
    ax.plot(df_chart.index, df_chart["Equity"], label="Equity", color="#2ca02c", linewidth=2)
    
    ax.set_title("10-Year Growth & Equity Accumulation", fontsize=14, pad=10)
    ax.set_xlabel("Holding Year", fontsize=10)
    ax.set_ylabel("Value ($)", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(loc="upper left")
    ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: "{:,}".format(int(x))))
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format="png", bbox_inches="tight", dpi=150)
    img_buffer.seek(0)
    
    # Since we added a new section, we check if we need a page break before the chart
    if pdf.get_y() > 200:
        pdf.add_page()
        
    pdf.image(img_buffer, x=15, w=180)

    return bytes(pdf.output())

# --- DOWNLOAD BUTTON ---
pdf_bytes = generate_pdf()
st.download_button(
    label="⬇️ Download Professional PDF Report",
    data=pdf_bytes,
    file_name="AQI_Investment_Report.pdf",
    mime="application/pdf"
)