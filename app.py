import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import io
import os
import json
from datetime import datetime
import google.generativeai as genai

# --- DEFAULT LIVING EXPENSES (Extracted from CSV) ---
DEFAULT_LIVING_EXPENSES_DATA = [
    {"Category": "Transport & Vehicle", "Item": "Vehicle registration", "Monthly Amount ($)": 125.0},
    {"Category": "Transport & Vehicle", "Item": "Vehicle maintenance", "Monthly Amount ($)": 25.0},
    {"Category": "Transport & Vehicle", "Item": "Vehicle insurance", "Monthly Amount ($)": 100.0},
    {"Category": "Transport & Vehicle", "Item": "Petrol", "Monthly Amount ($)": 100.0},
    {"Category": "Transport & Vehicle", "Item": "Public Transport", "Monthly Amount ($)": 21.67},
    {"Category": "Property Expenses", "Item": "Council Rates", "Monthly Amount ($)": 169.67},
    {"Category": "Property Expenses", "Item": "Home and contents insurances", "Monthly Amount ($)": 150.0},
    {"Category": "Services and Utilities", "Item": "Electricity", "Monthly Amount ($)": 250.0},
    {"Category": "Services and Utilities", "Item": "Gas", "Monthly Amount ($)": 83.33},
    {"Category": "Services and Utilities", "Item": "Water", "Monthly Amount ($)": 183.33},
    {"Category": "Services and Utilities", "Item": "Mobile telephone", "Monthly Amount ($)": 165.0},
    {"Category": "Services and Utilities", "Item": "Internet", "Monthly Amount ($)": 120.0},
    {"Category": "Food and Groceries", "Item": "Groceries", "Monthly Amount ($)": 866.67},
    {"Category": "Food and Groceries", "Item": "Restaurants", "Monthly Amount ($)": 433.33},
    {"Category": "Food and Groceries", "Item": "Takeaway food", "Monthly Amount ($)": 216.67},
    {"Category": "Recreation and Entertainment", "Item": "Subscription services (Pay TV, Music)", "Monthly Amount ($)": 160.0},
    {"Category": "Child Expenses", "Item": "Private school fees", "Monthly Amount ($)": 16.67},
    {"Category": "Child Expenses", "Item": "Medical", "Monthly Amount ($)": 50.0},
    {"Category": "Child Expenses", "Item": "Clothing and uniforms", "Monthly Amount ($)": 16.67},
    {"Category": "Health and Wellbeing", "Item": "Sports and gym fees", "Monthly Amount ($)": 80.0},
    {"Category": "Other Living Expenses", "Item": "Cigarettes and Alcohol", "Monthly Amount ($)": 50.0}
]

# --- PAGE SETUP ---
st.set_page_config(page_title="Investment Analysis", layout="wide")
st.title("🏙️ Property Investment Analyser")
st.markdown("---")

# --- LOCAL DATABASE CONFIG ---
HISTORY_FILE = "property_history.csv"

def save_to_history(name, url, params):
    """Saves property search and ALL parameters to local CSV."""
    if not url or url.strip() == "":
        url = "No Link Provided"
        
    entry_data = {
        "Date of PDF": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        "Property Name": [name],
        "Listing URL": [url],
        "Favorite": [False]
    }
    # Flatten params into the dictionary
    for key, value in params.items():
        entry_data[key] = [value]

    new_entry = pd.DataFrame(entry_data)
    
    if os.path.exists(HISTORY_FILE):
        history_df = pd.read_csv(HISTORY_FILE)
        history_df = pd.concat([history_df, new_entry], ignore_index=True)
    else:
        history_df = new_entry
        
    history_df = history_df.drop_duplicates(subset=["Property Name", "Listing URL"], keep="last")
    history_df.to_csv(HISTORY_FILE, index=False)

# --- 1. SESSION STATE (ENFORCING ALL KEYS) ---
if "form_data" not in st.session_state:
    st.session_state.form_data = {
        "prop_name": "2 Example Street MELBOURNE",
        "prop_url": "https://www.realestate.com.au/",
        "price": 650000.0,
        "beds": 2, 
        "baths": 1, 
        "cars": 1,
        "sal1": 3850.0,            
        "sal2": 8500.0,            
        "split": 50,
        "growth": 4.0, 
        "hold": 10,
        "living_expenses_json": json.dumps(DEFAULT_LIVING_EXPENSES_DATA),
        "ext_mortgage": 2921.0,    
        "ext_car_loan": 0.0,
        "ext_cc": 0.0,
        "ext_other": 0.0
    }

# --- 2. LOAD PROPERTY FUNCTION (ENFORCING FLOATS) ---
def load_property(row):
    # 1. Update the 'Source of Truth' dictionary
    st.session_state.form_data = {
        "prop_name": row["Property Name"],
        "prop_url": row["Listing URL"],
        "price": float(row["purchase_price"]),
        "beds": int(row["beds"]),
        "baths": int(row["baths"]),
        "cars": int(row["cars"]),
        "sal1": float(row.get("salary_1", 3850.0)),
        "sal2": float(row.get("salary_2", 8500.0)),
        "split": int(row.get("ownership_split", 0.5) * 100),
        "growth": float(row.get("growth_rate", 0.04) * 100),
        "hold": int(row.get("holding_period", 10)),
        "living_expenses_json": row.get("living_expenses_json", json.dumps(DEFAULT_LIVING_EXPENSES_DATA)),
        "ext_mortgage": float(row.get("ext_mortgage", 2921.0)),
        "ext_car_loan": float(row.get("ext_car_loan", 0.0)),
        "ext_cc": float(row.get("ext_cc", 0.0)),
        "ext_other": float(row.get("ext_other", 0.0))
    }

    # 2. Clear widget keys to prevent 'StreamlitAPIException'
    widget_keys = [
        "sb_prop_name", "sb_prop_url", "sb_price", "sb_beds", 
        "sb_baths", "sb_cars", "salary_input_1", "salary_input_2",
        "s1_freq_selector", "s2_freq_selector"
    ]
    
    for key in widget_keys:
        if key in st.session_state:
            del st.session_state[key]
            
    # 3. Refresh the app to display loaded data
    st.rerun()

# --- GEMINI AI YIELD ESTIMATOR ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_market_yield(address, beds, baths, cars):
    """Fetches estimated market yield from Gemini based on location and specs."""
    try:
        # Load API key from Streamlit secrets
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        
        # Use flash for faster responses
        model = genai.GenerativeModel('gemini-2.0-flash') 
        
        prompt = (
            f"Estimate the average gross rental yield percentage for a {beds} bedroom, "
            f"{baths} bathroom, {cars} car space residential property located in or around '{address}'. "
            "Respond with ONLY a single numerical value representing the percentage (e.g., 4.5). "
            "Do not include the % sign or any other text. If exact data is unavailable, provide your best realistic estimate."
        )
        
        response = model.generate_content(prompt)
        
        # Clean the output to ensure it's a float
        clean_val = response.text.strip().replace('%', '').replace(',', '.')
        return float(clean_val)
    except Exception as e:
        # Fails gracefully if API is down, key is missing, or parsing fails
        return None

# --- 1. GLOBAL INPUTS (SIDEBAR) ---
st.sidebar.header("📍 Core Parameters")

property_name = st.sidebar.text_input(
    "Property Name/Address", 
    value=st.session_state.form_data["prop_name"],
    key="sb_prop_name"
)
property_url = st.sidebar.text_input(
    "Property Listing URL", 
    value=st.session_state.form_data["prop_url"],
    key="sb_prop_url"
)

col_spec1, col_spec2, col_spec3 = st.sidebar.columns(3)
beds = col_spec1.number_input(
    "Beds", 
    value=int(st.session_state.form_data["beds"]), 
    step=1,
    key="sb_beds"
)
baths = col_spec2.number_input(
    "Baths", 
    value=int(st.session_state.form_data["baths"]), 
    step=1,
    key="sb_baths"
)
cars = col_spec3.number_input(
    "Cars", 
    value=int(st.session_state.form_data["cars"]), 
    step=1,
    key="sb_cars"
)

purchase_price = st.sidebar.number_input(
    "Purchase Price ($)", 
    value=float(st.session_state.form_data["price"]), 
    step=10000.0,
    key="sb_price"
)

st.sidebar.subheader("Tax Profiles (Post-Tax)")

# Investor 1
col_s1_val, col_s1_freq = st.sidebar.columns([2, 1])
s1_input = col_s1_val.number_input(
    "Inv 1 Take-Home ($)", 
    value=float(st.session_state.form_data["sal1"]), 
    step=100.0,
    key="salary_input_1"  # Unique Key
)
s1_freq = col_s1_freq.selectbox(
    "Freq", 
    ["Fortnightly", "Monthly", "Annually"], 
    key="s1_freq_selector" # Unique Key
)

# Investor 2
col_s2_val, col_s2_freq = st.sidebar.columns([2, 1])
s2_input = col_s2_val.number_input(
    "Inv 2 Take-Home ($)", 
    value=float(st.session_state.form_data["sal2"]), 
    step=100.0,
    key="salary_input_2"  # Unique Key
)
s2_freq = col_s2_freq.selectbox(
    "Freq", 
    ["Monthly", "Fortnightly", "Annually"], 
    key="s2_freq_selector" # Unique Key
)

# --- Mapping for annualization ---
freq_map = {"Monthly": 12, "Fortnightly": 26, "Annually": 1}

# These must be the final annual take-home figures
salary_1_annual = float(s1_input * freq_map[s1_freq])
salary_2_annual = float(s2_input * freq_map[s2_freq])

# Define aliases for other tabs to ensure consistency
salary_1 = salary_1_annual
salary_2 = salary_2_annual
annual_net_1 = salary_1_annual 
annual_net_2 = salary_2_annual

ownership_split_val = st.sidebar.slider("Ownership Split (Inv 1 %)", 0, 100, st.session_state.form_data["split"])
ownership_split = ownership_split_val / 100

st.sidebar.subheader("Projections")
growth_rate_val = st.sidebar.slider("Expected Annual Growth (%)", 0.0, 12.0, st.session_state.form_data["growth"], step=0.5)
growth_rate = growth_rate_val / 100
holding_period = st.sidebar.slider("Holding Period (Years)", 1, 30, st.session_state.form_data["hold"])

# --- GLOBAL TAX CALCULATOR ---
def calculate_tax(income):
    """Calculates standard Australian income tax (excluding Medicare levy)."""
    if income <= 18200: return 0
    elif income <= 45000: return (income - 18200) * 0.16
    elif income <= 135000: return 4288 + (income - 45000) * 0.30
    elif income <= 190000: return 31288 + (income - 135000) * 0.37
    else: return 51638 + (income - 190000) * 0.45

# --- 2. CREATE TABS ---
# Reordered to put Summary first
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "📊 Summary Dashboard",
    "Property & Acquisition", 
    "Income & Expenses", 
    "Loan Details",
    "Cash Flow",
    "Depreciation", 
    "Tax & Gearing", 
    "10-Year Projections",
    "CGT Projection",
    "Search History",
    "Living Expenses"  # NEW TAB
])

# --- PRE-CALCULATE HOUSEHOLD OBLIGATIONS FOR ALL TABS ---
# 1. Living Expenses Calculation
current_expenses_raw = st.session_state.form_data.get("living_expenses_json", json.dumps(DEFAULT_LIVING_EXPENSES_DATA))
expenses_df = pd.DataFrame(json.loads(current_expenses_raw))
total_monthly_living = expenses_df["Monthly Amount ($)"].sum()

# 2. Existing Debt Calculation
# We pull these directly from session state so they are available globally
total_existing_debt_m = (
    float(st.session_state.form_data.get("ext_mortgage", 2921.0)) +
    float(st.session_state.form_data.get("ext_car_loan", 0.0)) +
    float(st.session_state.form_data.get("ext_cc", 0.0)) +
    float(st.session_state.form_data.get("ext_other", 0.0))
)

# --- TAB 1: ACQUISITION ---
with tab1:
    st.subheader("Initial Outlay")
    
    if property_url and property_url != "https://www.realestate.com.au/":
        st.markdown(f"🔗 **[View Real Estate Listing]({property_url})**")
        
    col1, col2 = st.columns(2)
    stamp_duty = col1.number_input("Stamp Duty ($)", value=34100, step=1000)
    legal_fees = col2.number_input("Legal & Conveyancing ($)", value=1500, step=100)
    building_pest = col1.number_input("Building & Pest ($)", value=600, step=50)
    loan_setup = col2.number_input("Loan Setup Fees ($)", value=500, step=50)
    buyers_agent = col1.number_input("Buyers Agent ($)", value=5000, step=500)
    other_entry = col2.number_input("Other Entry Costs ($)", value=1000, step=100)
    
    total_acquisition_costs = stamp_duty + legal_fees + building_pest + loan_setup + buyers_agent + other_entry
    total_cost_base = purchase_price + total_acquisition_costs
    
    st.metric("Total Acquisition Costs", f"${total_acquisition_costs:,.2f}")
    st.metric("Total Required (Property + Costs)", f"${total_cost_base:,.2f}")

# --- TAB 2: INCOME & EXPENSES ---
with tab2:
    st.subheader("Cash Flow Essentials (Monthly Sourced)")
    c1, c2 = st.columns(2)
    
    monthly_rent = c1.number_input("Monthly Rent Received ($)", value=3683.33, step=100.0)
    vacancy_pct = c1.number_input("Vacancy Rate (%)", value=5.0, step=1.0)
    annual_gross_income = (monthly_rent * 12) * (1 - (vacancy_pct / 100))
    
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
    
    c1, c2 = st.columns(2)
    lvr_pct = c1.slider("LVR (%)", 0, 100, 80) / 100
    interest_rate = c2.number_input("Interest Rate (%)", value=5.49, step=0.01) / 100
    loan_term = c1.number_input("Loan Term (Years)", value=30, step=1)
    
    loan_type = c2.selectbox("Active Repayment Type (For Cash Flow)", ["Interest Only", "Principal & Interest"])
    
    loan_amount = purchase_price * lvr_pct
    
    monthly_io = (loan_amount * interest_rate) / 12
    annual_io = loan_amount * interest_rate
    
    monthly_pi = abs(npf.pmt(interest_rate/12, loan_term*12, loan_amount))
    annual_pi = monthly_pi * 12
    
    savings_io = annual_pi - annual_io
    
    if loan_type == "Interest Only":
        annual_repayment = annual_io
        annual_interest = annual_io
    else:
        annual_repayment = annual_pi
        annual_interest = annual_io 
        
    st.divider()
    st.markdown(f"### Calculated Loan Amount: **${loan_amount:,.2f}**")
    
    col_pi, col_io = st.columns(2)
    with col_pi:
        st.markdown("#### Principal & Interest (P&I)")
        st.write(f"**Monthly P&I Repayment:** ${monthly_pi:,.2f}")
        st.write(f"**Annual Repayment:** ${annual_pi:,.2f}")
        
    with col_io:
        st.markdown("#### Interest Only (IO)")
        st.write(f"**Monthly I Repayment:** ${monthly_io:,.2f}")
        st.write(f"**Annual Repayment:** ${annual_io:,.2f}")

# --- TAB 4: CASH FLOW ---
with tab4:
    st.subheader("Pre-Tax Cash Flow")
    
    net_operating_income = annual_gross_income - total_operating_expenses
    pre_tax_cashflow = net_operating_income - annual_repayment
    
    st.divider()
    cf_col1, cf_col2 = st.columns([1, 1])
    
    with cf_col1:
        st.write("**Annual Rental Income**")
        st.write("**Annual Operating Expenses**")
        st.write("**Net Operating Income (NOI)**")
        st.write(f"**Annual Debt Service ({'IO' if loan_type == 'Interest Only' else 'P&I'})**")
        st.markdown("### **Annual Cash Flow**")
        
    with cf_col2:
        st.write(f"${annual_gross_income:,.2f}")
        st.write(f"-${total_operating_expenses:,.2f}")
        st.write(f"**${net_operating_income:,.2f}**")
        st.write(f"-${annual_repayment:,.2f}")
        
        if pre_tax_cashflow < 0:
            st.markdown(f"<h3 style='color: #ff4b4b;'>-${abs(pre_tax_cashflow):,.2f}</h3>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h3 style='color: #00cc96;'>${pre_tax_cashflow:,.2f}</h3>", unsafe_allow_html=True)

# --- TAB 5: DEPRECIATION ---
with tab5:
    st.subheader("Tax Depreciation (Non-Cash Deductions)")
    div_43 = st.number_input("Capital Works (Div 43) ($)", value=9000, step=500)
    div_40 = st.number_input("Plant & Equipment (Div 40) ($)", value=8500, step=500)
    total_depreciation = div_43 + div_40
    st.metric("Total Annual Depreciation", f"${total_depreciation:,.2f}")

# --- TAB 6: TAX, GEARING & SERVICEABILITY ---
with tab6:
    st.subheader("Household Tax Impact & Cash Flow")
    st.info("💡 **Note:** Negative Gearing benefits are estimated based on your Take-Home pay figures. To calculate these, the app treats your inputs as the base taxable income.")
    
    def calculate_tax(income):
        if income <= 18200: return 0
        elif income <= 45000: return (income - 18200) * 0.16
        elif income <= 135000: return 4288 + (income - 45000) * 0.30
        elif income <= 190000: return 31288 + (income - 135000) * 0.37
        else: return 51638 + (income - 190000) * 0.45

    # 1. Tax & Gearing Calculations
    total_tax_deductions = total_operating_expenses + annual_interest + total_depreciation
    net_property_taxable_income = annual_gross_income - total_tax_deductions
    
    property_income_1 = net_property_taxable_income * ownership_split
    property_income_2 = net_property_taxable_income * (1 - ownership_split)
    
    base_tax_1 = calculate_tax(salary_1)
    new_tax_1 = calculate_tax(max(0, salary_1 + property_income_1))
    tax_variance_1 = base_tax_1 - new_tax_1
    
    base_tax_2 = calculate_tax(salary_2)
    new_tax_2 = calculate_tax(max(0, salary_2 + property_income_2))
    tax_variance_2 = base_tax_2 - new_tax_2
    
    total_tax_variance = tax_variance_1 + tax_variance_2
    post_tax_cashflow = pre_tax_cashflow + total_tax_variance

    # Display Tax Metrics
    t_col1, t_col2 = st.columns(2)
    t_col1.metric("Pre-Tax Cash Flow (Annual)", f"${pre_tax_cashflow:,.2f}")
    
    if total_tax_variance > 0:
        t_col2.metric("Combined Estimated Tax Refund", f"${total_tax_variance:,.2f}")
    else:
        t_col2.metric("Combined Estimated Tax Payable", f"${abs(total_tax_variance):,.2f}")
        
    st.metric("Household Net Post-Tax Cash Flow (Annual)", f"${post_tax_cashflow:,.2f}")

    st.divider()

    # 2. COMPREHENSIVE SERVICEABILITY CHECK
    st.subheader("🏦 Household Serviceability Check")
    st.markdown("This section evaluates if the household can support this loan after factoring in all living expenses and existing debts.")

    # Calculate Monthly Figures
    shaded_rent_m = (annual_gross_income / 12) * 0.80
    total_net_salary_m = (salary_1_annual + salary_2_annual) / 12
    
    # We use the PI amount for bank assessment standard
    assessment_mortgage_m = monthly_pi 
    
    total_monthly_inflow = total_net_salary_m + shaded_rent_m
    total_monthly_outflow = total_monthly_living + total_existing_debt_m + assessment_mortgage_m
    
    monthly_surplus = total_monthly_inflow - total_monthly_outflow
        
    # Display Serviceability Dashboard
    srv_col1, srv_col2 = st.columns(2)
    with srv_col1:
        st.write("**Monthly Inflows**")
        st.write(f"Total Net Salaries: `${total_net_salary_m:,.2f}`")
        st.write(f"Shaded Rental Income (80%): `${shaded_rent_m:,.2f}`")
        st.markdown(f"**Total Inflow: ${total_monthly_inflow:,.2f}**")
    with srv_col2:
        st.write("**Monthly Outflows**")
        st.write(f"Living Expenses: `${total_monthly_living:,.2f}`")
        st.write(f"Existing Debts: `${total_existing_debt_m:,.2f}`")
        st.write(f"New Loan (P&I Assessment): `${assessment_mortgage_m:,.2f}`")
        st.markdown(f"**Total Outflow: ${total_monthly_outflow:,.2f}**")

    if monthly_surplus > 0:
        st.success(f"### ✅ Serviceable\nMonthly household surplus: **${monthly_surplus:,.2f}**")
    else:
        st.error(f"### ⚠️ Warning: Deficit\nMonthly household deficit: **${abs(monthly_surplus):,.2f}**")

    st.divider()

    if monthly_surplus > 0:
        st.success(f"### ✅ Serviceable\nYour household has an estimated monthly surplus of **${monthly_surplus:,.2f}**.")
    else:
        st.error(f"### ⚠️ Serviceability Warning\nYour household has an estimated monthly deficit of **${abs(monthly_surplus):,.2f}**. This loan may be difficult to service under current bank assessment criteria.")

# --- TAB 7: 10-YEAR PROJECTIONS ---
with tab7:
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

# --- TAB 8: CGT PROJECTION ---
with tab8:
    st.subheader("Capital Gains Tax (Year 10 Sale)")
    
    sale_price = future_values[-1] 
    capital_gain = sale_price - purchase_price
    cgt_discount = capital_gain * 0.50  
    
    est_marginal_rate = st.number_input("Marginal Tax Rate for Sale Year (%)", value=35.0) / 100
    
    cgt_payable = cgt_discount * est_marginal_rate
    net_profit_on_sale = capital_gain - cgt_payable

    st.divider()
    c_col1, c_col2 = st.columns(2)
    c_col1.metric("Estimated Sale Price (Year 10)", f"${sale_price:,.2f}")
    c_col1.metric("Gross Capital Gain", f"${capital_gain:,.2f}")
    
    c_col2.metric("Estimated CGT Payable", f"${cgt_payable:,.2f}")
    c_col2.metric("Net Profit After Tax", f"${net_profit_on_sale:,.2f}")

# --- TAB 0: SUMMARY DASHBOARD (NEW) ---
with tab0:
    st.subheader(f"📊 Summary: {property_name}")
    st.markdown(f"**Specs:** {beds} 🛏️ | {baths} 🛁 | {cars} 🚗")
    
    # KPIs
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Purchase Price", f"${purchase_price:,.0f}")
    kpi2.metric("Gross Yield", f"{(annual_gross_income / purchase_price)*100:.2f}%")
    kpi3.metric("Total Outlay", f"${(total_cost_base - loan_amount):,.0f}")
    kpi4.metric("Net Operating Income", f"${net_operating_income:,.0f}")
    
    st.divider()
    
    # Cash Flow Breakdown
    cf1, cf2, cf3 = st.columns(3)
    cf1.metric("Annual Pre-Tax", f"${pre_tax_cashflow:,.0f}", f"${pre_tax_cashflow/52:,.2f} pw")
    cf2.metric("Estimated Tax Impact", f"${total_tax_variance:,.0f}", delta_color="normal")
    cf3.metric("Annual Post-Tax", f"${post_tax_cashflow:,.0f}", f"${post_tax_cashflow/52:,.2f} pw")
    
    st.divider()
    
    # Visual Insight
    v1, v2 = st.columns([2, 1])
    with v1:
        st.write("### Equity & Growth Over Time")
        st.area_chart(df_chart)
    with v2:
        st.write("### Expense Ratio")
        expense_data = pd.DataFrame({
            "Type": ["Operating Expenses", "Interest Costs"],
            "Amount": [total_operating_expenses, annual_interest]
        })
        st.bar_chart(expense_data.set_index("Type"))

# --- TAB 9: SEARCH HISTORY LOG ---
with tab9:
    st.subheader("📚 Property Search History")
    if os.path.exists(HISTORY_FILE):
        history_df = pd.read_csv(HISTORY_FILE)
        
        # --- FIX: Handle old CSVs missing the 'Favorite' column ---
        if "Favorite" not in history_df.columns:
            history_df["Favorite"] = False
        # ----------------------------------------------------------
        
        # Sorting Logic: Favorites (True) first, then Date (Descending)
        history_df = history_df.sort_values(by=["Favorite", "Date of PDF"], ascending=[False, False]).reset_index(drop=True)
        
        for index, row in history_df.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([0.1, 0.4, 0.3, 0.2])
                
                # Favorite Toggle
                is_fav = "⭐" if row.get("Favorite", False) else "☆"
                if c1.button(is_fav, key=f"fav_{index}"):
                    history_df.at[index, "Favorite"] = not row.get("Favorite", False)
                    history_df.to_csv(HISTORY_FILE, index=False)
                    st.rerun()
                
                c2.write(f"**{row['Property Name']}**")
                c3.write(f"📅 {row['Date of PDF']}")
                
                # Revisit Action
                if c4.button("🔄 Revisit", key=f"rev_{index}"):
                    # We use .get() here as a safety net in case older rows are missing parameters
                    load_property(row)
                    st.rerun()
                st.divider()

        if st.button("🗑️ Clear History"):
            os.remove(HISTORY_FILE)
            st.rerun()
    else:
        st.info("Download a PDF to save to history.")

# --- TAB 10: LIVING EXPENSES & SERVICING ---
with tab10:
    st.subheader("Household Living Expenses (Monthly)")
    st.markdown("Modify the default values or add new rows below. Your custom expenses will be saved with this property search.")
    
    # Safer way to load expenses: use .get() to provide a fallback if the key is missing
    expenses_raw = st.session_state.form_data.get("living_expenses_json", json.dumps(DEFAULT_LIVING_EXPENSES_DATA))
    current_expenses = pd.DataFrame(json.loads(expenses_raw))
    
    edited_expenses = st.data_editor(
        current_expenses,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Monthly Amount ($)": st.column_config.NumberColumn(
                "Monthly Amount ($)",
                min_value=0.0,
                step=10.0,
                format="$%.2f",
            )
        },
        key="living_expenses_editor"
    )
    
    total_monthly_living = edited_expenses["Monthly Amount ($)"].sum()
    st.session_state.form_data["living_expenses_json"] = edited_expenses.to_json(orient="records")

    st.divider()
    
    # --- NEW: EXISTING DEBT COMMITMENTS ---
    st.subheader("💳 Existing Debt Commitments (Monthly)")
    d1, d2, d3, d4 = st.columns(4)
    
    # Using float() here acts as a safety shield against data type errors
    ext_mortgage = d1.number_input("Existing Mortgage(s) ($)", value=float(st.session_state.form_data["ext_mortgage"]), step=100.0)
    ext_car_loan = d2.number_input("Car Loan(s) ($)", value=float(st.session_state.form_data["ext_car_loan"]), step=50.0)
    ext_cc = d3.number_input("Credit Card Payments ($)", value=float(st.session_state.form_data["ext_cc"]), step=50.0, help="Typically assessed at 3-4% of total limit")
    ext_other = d4.number_input("Other Loans ($)", value=float(st.session_state.form_data["ext_other"]), step=50.0)
    
    total_existing_debt_m = ext_mortgage + ext_car_loan + ext_cc + ext_other
    
    st.divider()
    
# --- NEW: SERVICING OVERVIEW ---
    st.subheader("⚖️ Monthly Serviceability Overview")
    
    # Inflows: Net inputs combined and divided into months
    total_net_income_m = (annual_net_1 + annual_net_2) / 12
    
    # 2. Bank Rental Shading (80%)
    shaded_rent_m = monthly_rent * 0.80
    
    # 3. New Mortgage Commitment
    new_mortgage_m = monthly_io if loan_type == "Interest Only" else monthly_pi
    
    # 4. Final Totals
    total_income_m = total_net_income_m + shaded_rent_m
    total_commitments_m = total_monthly_living + total_existing_debt_m + new_mortgage_m
    monthly_surplus = total_income_m - total_commitments_m
    
    srv1, srv2 = st.columns([1, 1])
    with srv1:
        st.write("**INFLOWS (Actual Take-Home)**")
        st.write(f"Inv 1 Net ({s1_freq}): **${s1_input:,.2f}**")
        st.write(f"Inv 2 Net ({s2_freq}): **${s2_input:,.2f}**")
        st.write(f"Proposed Rent (80% Bank Shade): **${shaded_rent_m:,.2f}**")
        st.markdown(f"### Total Monthly Inflow: <span style='color:#00cc96'>${total_income_m:,.2f}</span>", unsafe_allow_html=True)
        
    with srv2:
        st.write("**OUTFLOWS**")
        st.write(f"Living Expenses: **${total_monthly_living:,.2f}**")
        st.write(f"Existing Debts/Mortgages: **${total_existing_debt_m:,.2f}**")
        st.write(f"NEW Property Mortgage: **${new_mortgage_m:,.2f}**")
        st.markdown(f"### Total Commitments: <span style='color:#ff4b4b'>${total_commitments_m:,.2f}</span>", unsafe_allow_html=True)
        
    st.divider()
    
    if monthly_surplus >= 0:
        st.success(f"You have an estimated household surplus of **${monthly_surplus:,.2f} per month**.")
    else:
        st.error(f"Warning: Estimated household deficit of **${abs(monthly_surplus):,.2f} per month**.")

# --- PDF GENERATION LOGIC ---
st.markdown("---")
st.subheader("📄 Export Analysis Report")

def generate_pdf(salary_1_annual, salary_2_annual, total_monthly_living, total_existing_debt_m):
    # 1. Fetch AI Market Yield Data
    market_yield = fetch_market_yield(property_name, beds, baths, cars)
    property_yield = (annual_gross_income / purchase_price) * 100

    class InvestmentReportPDF(FPDF):
        def header(self):
            logo_path = "AQI_Logo.png" 
            if os.path.exists(logo_path):
                self.image(logo_path, 10, 8, 30)
            self.set_font("helvetica", "B", 20)
            self.set_text_color(0, 51, 102)
            self.cell(40) 
            self.cell(0, 15, "Investment Portfolio Analysis", new_x="LMARGIN", new_y="NEXT", align="L")
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font("helvetica", "I", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 5, "*Disclaimer: Suburb yield and serviceability are estimates for guidance only.", align="C", new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 5, f"Page {self.page_no()}", align="C")

        def section_header(self, title):
            self.set_font("helvetica", "B", 13)
            self.set_fill_color(230, 240, 255)
            self.set_text_color(0, 0, 0)
            self.cell(0, 10, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
            self.ln(2)

        def row(self, label, value, label2="", value2=""):
            self.set_font("helvetica", "", 10)
            self.cell(50, 7, label, border=0)
            self.set_font("helvetica", "B", 10)
            self.cell(45, 7, str(value), border=0)
            if label2:
                self.set_font("helvetica", "", 10)
                self.cell(50, 7, label2, border=0)
                self.set_font("helvetica", "B", 10)
                self.cell(0, 7, str(value2), border=0, new_x="LMARGIN", new_y="NEXT")
            else:
                self.ln(7)

    pdf = InvestmentReportPDF()
    pdf.add_page()
    
    # --- HEADER ---
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 8, property_name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 7, f"Configuration: {beds} Bed | {baths} Bath | {cars} Car", new_x="LMARGIN", new_y="NEXT")
    if property_url and property_url.strip() != "" and property_url != "https://www.realestate.com.au/":
        pdf.set_font("helvetica", "U", 9)
        pdf.set_text_color(0, 102, 204) 
        pdf.cell(0, 6, "View Listing Online", link=property_url, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0) 
    pdf.ln(3)

    # --- 1. ACQUISITION & FINANCE ---
    cash_outlay = total_cost_base - loan_amount
    pdf.section_header("1. Acquisition & Finance")
    pdf.row("Purchase Price:", f"${purchase_price:,.0f}", "Loan Amount:", f"${loan_amount:,.0f}")
    pdf.row("Interest Rate:", f"{interest_rate*100:.2f}%", "Loan Type:", f"{loan_type}")
    pdf.row("Total Entry Costs:", f"${total_acquisition_costs:,.0f}", "Total Cash Outlay:", f"${cash_outlay:,.0f}")
    pdf.ln(3)

    # --- 2. YIELD ANALYSIS & MARKET COMPARISON ---
    pdf.section_header("2. Yield Analysis & Market Comparison (AI Estimated)")
    pdf.row("Property Gross Yield:", f"{property_yield:.2f}%")
    if market_yield:
        variance = property_yield - market_yield
        pdf.set_text_color(0, 128, 0) if variance >= 0 else pdf.set_text_color(200, 0, 0)
        status = f"{'Outperforming' if variance >= 0 else 'Underperforming'} by {abs(variance):.2f}%"
        pdf.row("Est. Suburb Average:", f"{market_yield:.2f}%", "Market Status:", status)
    else:
        pdf.set_text_color(128, 128, 128)
        pdf.row("Est. Suburb Average:", "Data Unavailable", "Market Status:", "N/A")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    # --- 3. PROPERTY PERFORMANCE (ANNUAL PRE-TAX) ---
    pdf.section_header("3. Property Performance (Annual Pre-Tax)")
    pdf.row("Gross Annual Rent:", f"${annual_gross_income:,.0f}", "Operating Expenses:", f"-${total_operating_expenses:,.0f}")
    pdf.row("Loan Interest Expense:", f"-${annual_interest:,.0f}", "Net Property Cash Flow:", f"${pre_tax_cashflow:,.2f}")
    pdf.set_font("helvetica", "I", 10)
    pdf.set_text_color(0, 102, 204)
    pdf.cell(0, 7, f"Est. Additional Annual Tax Refund (Gearing): ${total_tax_variance:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    # --- 4. MONTHLY HOUSEHOLD SERVICEABILITY (FIXED MATH) ---
    pdf.section_header("4. Monthly Household Serviceability")
    # Take-Home salaries passed in are already annual totals, we only divide by 12 once.
    total_household_net_m = (salary_1_annual + salary_2_annual) / 12
    shaded_rent_m = (monthly_rent * 0.80) 
    new_mortgage_m = monthly_io if loan_type == "Interest Only" else monthly_pi
    
    monthly_inflow = total_household_net_m + shaded_rent_m
    monthly_outflow = total_monthly_living + total_existing_debt_m + new_mortgage_m
    net_monthly_surplus = monthly_inflow - monthly_outflow

    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 7, "Serviceability Breakdown (Monthly):", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    pdf.row("Take-Home Pay:", f"${total_household_net_m:,.2f}", "Living Expenses:", f"-${total_monthly_living:,.2f}")
    pdf.row("Rental Income (80%):", f"${shaded_rent_m:,.2f}", "Existing Debts:", f"-${total_existing_debt_m:,.2f}")
    pdf.row("New Property Loan:", f"-${new_mortgage_m:,.2f}")
    
    pdf.ln(2)
    if net_monthly_surplus >= 0:
        pdf.set_text_color(0, 128, 0)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, f"ESTIMATED MONTHLY SURPLUS: ${net_monthly_surplus:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_text_color(200, 0, 0)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, f"ESTIMATED MONTHLY DEFICIT: ${abs(net_monthly_surplus):,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # --- 5. EXIT STRATEGY & CGT PROJECTION ---
    pdf.section_header(f"5. Exit Strategy & CGT Projection (Year {holding_period})")
    pdf.row("Est. Sale Price:", f"${future_values[-1]:,.0f}", "Gross Capital Gain:", f"${capital_gain:,.0f}")
    pdf.row("Marginal Tax Rate:", f"{est_marginal_rate*100:.1f}%", "Est. CGT Payable:", f"${cgt_payable:,.0f}")
    pdf.set_font("helvetica", "B", 10)
    pdf.row("NET PROFIT ON SALE:", f"${net_profit_on_sale:,.0f}")
    pdf.ln(3)

    # --- 6. PROJECTED WEALTH MILESTONES ---
    pdf.section_header("6. Projected Wealth Milestones")
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(30, 7, "Year", border=1, align="C", fill=True)
    pdf.cell(80, 7, "Estimated Value", border=1, align="C", fill=True)
    pdf.cell(80, 7, "Estimated Equity", border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font("helvetica", "", 9)
    for yr in [1, 3, 5, 10]:
        if yr <= holding_period:
            val = purchase_price * (1 + growth_rate)**yr
            eq = val - loan_amount
            pdf.cell(30, 7, f"Year {yr}", border=1, align="C")
            pdf.cell(80, 7, f"${val:,.0f}", border=1, align="C")
            pdf.cell(80, 7, f"${eq:,.0f}", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    
    # --- PAGE 2: RESTORED CHARTS ---
    pdf.section_header("7. Equity & Value Projections")
    fig, ax = plt.subplots(figsize=(8, 4.5)) 
    ax.plot(df_chart.index, df_chart["Property Value"], label="Market Value", color="#003366", linewidth=2.5)
    ax.plot(df_chart.index, df_chart["Equity"], label="Equity Position", color="#2ca02c", linewidth=2.5)
    ax.fill_between(df_chart.index, df_chart["Equity"], color="#2ca02c", alpha=0.1)
    ax.set_title(f"Equity Projection ({growth_rate*100:.1f}% Annual Growth)", fontsize=12, fontweight='bold', pad=15)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f'${x:,.0f}'))
    ax.grid(True, axis='y', linestyle="--", alpha=0.5)
    ax.legend(frameon=False, loc="upper left")
    plt.tight_layout()
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format="png", bbox_inches="tight", dpi=200) 
    pdf.image(img_buffer, x=15, w=180)
    plt.close()

    return bytes(pdf.output())

# --- DOWNLOAD BUTTON ---
pdf_bytes = generate_pdf(
    salary_1_annual, 
    salary_2_annual, 
    total_monthly_living, 
    total_existing_debt_m
)

st.download_button(
    label="⬇️ Download Full Summary PDF",
    data=pdf_bytes,
    file_name=f"{property_name.replace(' ', '_')}_Summary.pdf",
    mime="application/pdf",
    on_click=save_to_history,
    args=(property_name, property_url, {
        "purchase_price": purchase_price,
        "beds": beds, "baths": baths, "cars": cars,
        "salary_1": salary_1_annual,
        "salary_2": salary_2_annual,
        "ownership_split": ownership_split,
        "growth_rate": growth_rate,
        "holding_period": holding_period,
        "living_expenses_json": st.session_state.form_data["living_expenses_json"],
        "ext_mortgage": float(st.session_state.form_data.get("ext_mortgage", 0.0)),
        "ext_car_loan": float(st.session_state.form_data.get("ext_car_loan", 0.0)),
        "ext_cc": float(st.session_state.form_data.get("ext_cc", 0.0)),
        "ext_other": float(st.session_state.form_data.get("ext_other", 0.0))
    })
)