import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
from fpdf import FPDF
import matplotlib.pyplot as plt
import io
import os
from datetime import datetime

# --- PAGE SETUP ---
st.set_page_config(page_title="Investment Analysis", layout="wide")
st.title("🏙️ Property Investment Analyser")
st.markdown("---")

# --- 1. GLOBAL INPUTS (SIDEBAR) ---
st.sidebar.header("📍 Core Parameters")
property_name = st.sidebar.text_input("Property Name/Address", value="2 Example Street MELBOURNE")
purchase_price = st.sidebar.number_input("Purchase Price ($)", value=650000, step=10000)

st.sidebar.subheader("Tax Profiles (Joint Ownership)")
# Splitting the incomes ensures the marginal tax rates are calculated correctly per person
salary_1 = st.sidebar.number_input("Investor 1 Salary ($)", value=150000, step=5000)
salary_2 = st.sidebar.number_input("Investor 2 Salary ($)", value=150000, step=5000)
ownership_split = st.sidebar.slider("Ownership Split (Inv 1 %)", 0, 100, 50) / 100

st.sidebar.subheader("Projections")
growth_rate = st.sidebar.slider("Expected Annual Growth (%)", 0.0, 12.0, 4.0, step=0.5) / 100
holding_period = st.sidebar.slider("Holding Period (Years)", 1, 30, 10)

# --- 2. CREATE TABS ---
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
    stamp_duty = col1.number_input("Stamp Duty ($)", value=34100, step=1000)
    legal_fees = col2.number_input("Legal & Conveyancing ($)", value=1500, step=100)
    building_pest = col1.number_input("Building & Pest ($)", value=600, step=50)
    loan_setup = col2.number_input("Loan Setup Fees ($)", value=500, step=50)
    buyers_agent = col1.number_input("Buyers Agent ($)", value=5000, step=500)
    other_entry = col2.number_input("Other Entry Costs ($)", value=1000, step=100)
    
    total_acquisition_costs = stamp_duty + legal_fees + building_pest + loan_setup + buyers_agent + other_entry
    total_cost_base = purchase_price + total_acquisition_costs
    
    st.metric("Total Acquisition Costs", f"${total_acquisition_costs:,.0f}")
    st.metric("Total Required (Property + Costs)", f"${total_cost_base:,.0f}")

# --- TAB 2: INCOME & EXPENSES (Monthly Inputs) ---
with tab2:
    st.subheader("Cash Flow Essentials (Monthly Sourced)")
    c1, c2 = st.columns(2)
    
    # Income (Monthly)
    monthly_rent = c1.number_input("Monthly Rent Received ($)", value=3683.33, step=100.0)
    vacancy_pct = c1.number_input("Vacancy Rate (%)", value=5.0, step=1.0)
    
    annual_gross_income = (monthly_rent * 12) * (1 - (vacancy_pct / 100))
    
    # Expenses (Monthly)
    mgt_fee_m = c2.number_input("Property Management (Monthly $)", value=276.25, step=10.0)
    strata_m = c2.number_input("Strata/Body Corporate (Monthly $)", value=500.00, step=10.0)
    insurance_m = c2.number_input("Landlord Insurance (Monthly $)", value=45.00, step=5.0)
    rates_m = c2.number_input("Council Rates (Monthly $)", value=165.00, step=10.0)
    maint_m = c2.number_input("Maintenance (Monthly $)", value=150.00, step=10.0)
    water_m = c2.number_input("Water Service (Monthly $)", value=80.00, step=5.0)
    other_m = c2.number_input("Other (Monthly $)", value=25.00, step=5.0)
    
    total_monthly_expenses = mgt_fee_m + strata_m + insurance_m + rates_m + maint_m + water_m + other_m
    total_operating_expenses = total_monthly_expenses * 12
    
    st.divider()
    metric_col1, metric_col2 = st.columns(2)
    metric_col1.metric("Gross Annual Income", f"${annual_gross_income:,.2f}")
    metric_col2.metric("Total Annual Expenses", f"${total_operating_expenses:,.2f}")

# --- TAB 3: LOAN DETAILS ---
with tab3:
    st.subheader("Financing Structure")
    lvr_pct = st.slider("LVR (%)", 0, 100, 80) / 100
    interest_rate = st.number_input("Interest Rate (%)", value=5.49, step=0.01) / 100
    loan_term = st.number_input("Loan Term (Years)", value=30, step=1)
    loan_type = st.selectbox("Repayment Type", ["Interest Only", "Principal & Interest"])
    
    loan_amount = purchase_price * lvr_pct
    
    if loan_type == "Interest Only":
        annual_interest = loan_amount * interest_rate
        annual_repayment = annual_interest
    else:
        monthly_repayment = abs(npf.pmt(interest_rate/12, loan_term*12, loan_amount))
        annual_repayment = monthly_repayment * 12
        annual_interest = loan_amount * interest_rate 
        
    st.divider()
    l_col1, l_col2, l_col3 = st.columns(3)
    l_col1.metric("Loan Amount", f"${loan_amount:,.0f}")
    l_col2.metric("Annual Interest (Tax Deductible)", f"${annual_interest:,.0f}")
    l_col3.metric("Total Annual Repayment", f"${annual_repayment:,.0f}")

# --- TAB 4: DEPRECIATION ---
with tab4:
    st.subheader("Tax Depreciation (Non-Cash Deductions)")
    div_43 = st.number_input("Capital Works (Div 43) ($)", value=9000, step=500)
    div_40 = st.number_input("Plant & Equipment (Div 40) ($)", value=8500, step=500)
    total_depreciation = div_43 + div_40
    st.metric("Total Annual Depreciation", f"${total_depreciation:,.0f}")

# --- TAB 5: TAX & NEGATIVE GEARING (Dual Salary Logic) ---
with tab5:
    st.subheader("Household Tax Impact & Cash Flow")
    
    def calculate_tax(income):
        if income <= 18200: return 0
        elif income <= 45000: return (income - 18200) * 0.16
        elif income <= 135000: return 4288 + (income - 45000) * 0.30
        elif income <= 190000: return 31288 + (income - 135000) * 0.37
        else: return 51638 + (income - 190000) * 0.45

    # Total Property Income/Loss
    total_tax_deductions = total_operating_expenses + annual_interest + total_depreciation
    net_property_taxable_income = annual_gross_income - total_tax_deductions
    
    # Split the loss/gain based on ownership
    property_income_1 = net_property_taxable_income * ownership_split
    property_income_2 = net_property_taxable_income * (1 - ownership_split)
    
    # Calculate Tax Variance for Investor 1
    base_tax_1 = calculate_tax(salary_1)
    new_tax_1 = calculate_tax(max(0, salary_1 + property_income_1))
    tax_variance_1 = base_tax_1 - new_tax_1
    
    # Calculate Tax Variance for Investor 2
    base_tax_2 = calculate_tax(salary_2)
    new_tax_2 = calculate_tax(max(0, salary_2 + property_income_2))
    tax_variance_2 = base_tax_2 - new_tax_2
    
    total_tax_variance = tax_variance_1 + tax_variance_2
    
    pre_tax_cashflow = annual_gross_income - (total_operating_expenses + annual_repayment)
    post_tax_cashflow = pre_tax_cashflow + total_tax_variance

    t_col1, t_col2 = st.columns(2)
    t_col1.metric("Pre-Tax Cash Flow (Annual)", f"${pre_tax_cashflow:,.2f}")
    
    if total_tax_variance > 0:
        t_col2.metric("Combined Estimated Tax Refund", f"${total_tax_variance:,.2f}")
    else:
        t_col2.metric("Combined Estimated Tax Payable", f"${abs(total_tax_variance):,.2f}")
        
    st.metric("Household Net Post-Tax Cash Flow (Annual)", f"${post_tax_cashflow:,.2f}")
    if post_tax_cashflow < 0:
        st.write(f"⚠️ This property costs your household **${abs(post_tax_cashflow)/52:,.2f} per week** out of pocket to hold.")
    else:
        st.write(f"✅ This property puts **${post_tax_cashflow/52:,.2f} per week** in your household's pocket.")

# --- TAB 6: 10-YEAR PROJECTIONS ---
with tab6:
    st.subheader("Equity & Growth Forecast")
    
    years = np.arange(1, holding_period + 1)
    future_values = [purchase_price * (1 + growth_rate)**y for y in years]
    equity = [val - loan_amount for val in future_values]
    
    df_chart = pd.DataFrame({
        "Year": years,
        "Property Value": future_values,
        "Equity": equity
    }).set_index("Year")
    
    st.line_chart(df_chart)
    
    st.write("Detailed Breakdown")
    st.dataframe(df_chart.style.format("${:,.0f}"))

# --- TAB 7: CGT PROJECTION ---
with tab7:
    st.subheader("Capital Gains Tax (Year 10 Sale)")
    
    sale_price = future_values[-1] 
    capital_gain = sale_price - purchase_price
    cgt_discount = capital_gain * 0.50  
    
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
            self.set_text_color(0, 0, 0)
            self.cell(0, 8, value, ln=True, border=0)

    pdf = InvestmentReportPDF()
    pdf.add_page()
    
    current_date = datetime.now().strftime("%d %B %Y")
    
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, f"Property: {property_name}", ln=True)
    
    pdf.set_font("helvetica", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f"Report Generated: {current_date}", ln=True)
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0) 
    
    # 1. Acquisition
    pdf.section_header("1. Acquisition & Capital Required")
    pdf.row("Purchase Price:", f"${purchase_price:,.0f}")
    pdf.row("Total Entry Costs:", f"${total_acquisition_costs:,.0f}")
    pdf.row("Total Funds Required:", f"${total_cost_base:,.0f}")
    pdf.ln(5)
    
    # 2. Cash Flow
    pdf.section_header("2. Annual Cash Flow & Household Tax Impact")
    pdf.row("Gross Annual Income:", f"${annual_gross_income:,.0f}")
    pdf.row("Total Operating Expenses:", f"${total_operating_expenses:,.0f}")
    pdf.row("Annual Debt Servicing:", f"${annual_repayment:,.0f}")
    pdf.row("Combined Tax Refund/Payable:", f"${total_tax_variance:,.0f}")
    pdf.row("Net Post-Tax Cash Flow:", f"${post_tax_cashflow:,.0f}")
    pdf.ln(5)
    
    # 3. Projections
    pdf.section_header("3. 10-Year Wealth Forecast")
    pdf.row("Estimated Property Value (Year 10):", f"${future_values[-1]:,.0f}")
    pdf.row("Estimated Equity (Year 10):", f"${equity[-1]:,.0f}")
    pdf.ln(5)

    # 4. CGT & Sale Profit
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
    
    if pdf.get_y() > 190:
        pdf.add_page()
        
    pdf.image(img_buffer, x=15, w=180)

    return bytes(pdf.output())

# --- DOWNLOAD BUTTON ---
pdf_bytes = generate_pdf()
st.download_button(
    label="⬇️ Download Professional PDF Report",
    data=pdf_bytes,
    file_name=f"{property_name.replace(' ', '_')}_Report.pdf",
    mime="application/pdf"
)