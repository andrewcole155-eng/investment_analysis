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
        try:
            history_df = pd.read_csv(HISTORY_FILE)
            # CRITICAL FIX: Explicitly drop the old version of this property so the new one saves
            history_df = history_df[~((history_df["Property Name"] == name) & (history_df["Listing URL"] == url))]
            history_df = pd.concat([history_df, new_entry], ignore_index=True)
        except pd.errors.EmptyDataError:
            history_df = new_entry
    else:
        history_df = new_entry
        
    history_df.to_csv(HISTORY_FILE, index=False)

# --- 1. SESSION STATE (FIXED FOR RAW INPUTS & EQUITY LOAN) ---
if "form_data" not in st.session_state:
    st.session_state.form_data = {
        "prop_name": "2 Example Street MELBOURNE",
        "prop_url": "https://www.realestate.com.au/",
        "price": 650000.0,
        "beds": 2, "baths": 1, "cars": 1,
        "s1_input": 3811.78, "s1_freq": "Fortnightly",  
        "s2_input": 8429.83, "s2_freq": "Monthly",      
        "split": 50,
        "growth": 4.0, "hold": 10,
        "living_expenses_json": json.dumps(DEFAULT_LIVING_EXPENSES_DATA),
        "ext_mortgage": 2921.0, "ext_car_loan": 0.0, "ext_cc": 0.0, "ext_other": 0.0,
        "use_eq": True, "eq_amount": 170000.0, "eq_rate": 6.20,
        # NEW AI-DRIVEN DEFAULTS:
        "stamp_duty": 34100.0, "legal_fees": 1500.0, "building_pest": 600.0,
        "loan_setup": 500.0, "buyers_agent": 5000.0, "other_entry": 1000.0,
        "monthly_rent": 3683.33, "vacancy_pct": 5.0, "mgt_fee_m": 276.25,
        "strata_m": 500.0, "insurance_m": 45.0, "rates_m": 165.0,
        "maint_m": 150.0, "water_m": 80.0, "other_m": 25.0,
        "div_43": 9000.0, "div_40": 8500.0,
        "is_ai_estimated": False  # <-- NEW FLAG TO TRACK AI USAGE
    }
    
    # PRE-LOAD WIDGET KEYS TO PREVENT STREAMLIT WARNINGS
    st.session_state.sb_prop_name = "2 Example Street MELBOURNE"
    st.session_state.sb_prop_url = "https://www.realestate.com.au/"
    st.session_state.sb_price = 650000.0
    st.session_state.sb_beds = 2
    st.session_state.sb_baths = 1
    st.session_state.sb_cars = 1
    st.session_state.salary_input_1 = 3811.78
    st.session_state.s1_freq_selector = "Fortnightly"
    st.session_state.salary_input_2 = 8429.83
    st.session_state.s2_freq_selector = "Monthly"
    st.session_state.sb_ext_mortgage = 2921.0
    st.session_state.sb_ext_car_loan = 0.0
    st.session_state.sb_ext_cc = 0.0
    st.session_state.sb_ext_other = 0.0

# --- 2. LOAD PROPERTY FUNCTION (CALLBACK VERSION) ---
def load_property(row):
    st.session_state.form_data = {
        "prop_name": row["Property Name"],
        "prop_url": row["Listing URL"],
        "price": float(row["purchase_price"]),
        "beds": int(row["beds"]), "baths": int(row["baths"]), "cars": int(row["cars"]),
        "s1_input": float(row.get("s1_input", 3811.78)),
        "s1_freq": row.get("s1_freq", "Fortnightly"),
        "s2_input": float(row.get("s2_input", 8429.83)),
        "s2_freq": row.get("s2_freq", "Monthly"),
        "split": int(row.get("ownership_split", 0.5) * 100),
        "growth": float(row.get("growth_rate", 0.04) * 100),
        "hold": int(row.get("holding_period", 10)),
        "living_expenses_json": row.get("living_expenses_json", json.dumps(DEFAULT_LIVING_EXPENSES_DATA)),
        "ext_mortgage": float(row.get("ext_mortgage", 2921.0)),
        "ext_car_loan": float(row.get("ext_car_loan", 0.0)),
        "ext_cc": float(row.get("ext_cc", 0.0)),
        "ext_other": float(row.get("ext_other", 0.0)),
        "use_eq": bool(row.get("use_eq", True)),
        "eq_amount": float(row.get("eq_amount", 170000.0)),
        "eq_rate": float(row.get("eq_rate", 6.20)),
        
        # NEW AI-DRIVEN FIELDS WITH FALLBACKS:
        "stamp_duty": float(row.get("stamp_duty", 34100.0)),
        "legal_fees": float(row.get("legal_fees", 1500.0)),
        "building_pest": float(row.get("building_pest", 600.0)),
        "loan_setup": float(row.get("loan_setup", 500.0)),
        "buyers_agent": float(row.get("buyers_agent", 5000.0)),
        "other_entry": float(row.get("other_entry", 1000.0)),
        "monthly_rent": float(row.get("monthly_rent", 3683.33)),
        "vacancy_pct": float(row.get("vacancy_pct", 5.0)),
        "mgt_fee_m": float(row.get("mgt_fee_m", 276.25)),
        "strata_m": float(row.get("strata_m", 500.0)),
        "insurance_m": float(row.get("insurance_m", 45.0)),
        "rates_m": float(row.get("rates_m", 165.0)),
        "maint_m": float(row.get("maint_m", 150.0)),
        "water_m": float(row.get("water_m", 80.0)),
        "other_m": float(row.get("other_m", 25.0)),
        "div_43": float(row.get("div_43", 9000.0)),
        "div_40": float(row.get("div_40", 8500.0))
    }

    st.session_state.sb_prop_name = st.session_state.form_data["prop_name"]
    st.session_state.sb_prop_url = st.session_state.form_data["prop_url"]
    st.session_state.sb_price = st.session_state.form_data["price"]
    st.session_state.sb_beds = st.session_state.form_data["beds"]
    st.session_state.sb_baths = st.session_state.form_data["baths"]
    st.session_state.sb_cars = st.session_state.form_data["cars"]
    st.session_state.salary_input_1 = st.session_state.form_data["s1_input"]
    st.session_state.s1_freq_selector = st.session_state.form_data["s1_freq"]
    st.session_state.salary_input_2 = st.session_state.form_data["s2_input"]
    st.session_state.s2_freq_selector = st.session_state.form_data["s2_freq"]
    st.session_state.sb_ext_mortgage = st.session_state.form_data["ext_mortgage"]
    st.session_state.sb_ext_car_loan = st.session_state.form_data["ext_car_loan"]
    st.session_state.sb_ext_cc = st.session_state.form_data["ext_cc"]
    st.session_state.sb_ext_other = st.session_state.form_data["ext_other"]

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

# --- COMPREHENSIVE AI ESTIMATOR ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_comprehensive_estimates(address, price, beds, baths, cars):
    """Fetches comprehensive property estimates returned as a JSON object."""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        
        # Using gemini-2.0-flash as per system preference
        model = genai.GenerativeModel('gemini-2.0-flash') 
        
        prompt = f"""
        You are an expert Australian real estate AI. Provide realistic estimated investment figures for a {beds} bed, {baths} bath, {cars} car property located in '{address}' purchasing for ${price}.
        
        Return ONLY a valid JSON object with the following exact keys and numerical values (no symbols, no text outside the JSON). If exact data is unknown, provide realistic state/suburb averages:
        {{
            "stamp_duty": 34100.0,
            "legal_fees": 1500.0,
            "building_pest": 600.0,
            "monthly_rent": 3683.33,
            "vacancy_pct": 5.0,
            "mgt_fee_m": 276.25,
            "strata_m": 500.0,
            "insurance_m": 45.0,
            "rates_m": 165.0,
            "maint_m": 150.0,
            "water_m": 80.0,
            "div_43": 9000.0,
            "div_40": 8500.0,
            "expected_annual_growth": 5.0
        }}
        """
        
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        return json.loads(response.text)
    except Exception as e:
        # Print the exact error to your terminal/console so you can debug it
        print(f"⚠️ AI API Error: {e}")
        return None

# --- NEW: AI TAX STRATEGY SUMMARY ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_tax_strategy_summary(address, gross_1, gross_2, split, net_tax_loss, pre_tax_cashflow, total_tax_variance):
    """Fetches a strategic tax summary for the PDF report using Gemini."""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        high_earner = "Investor 1" if gross_1 > gross_2 else "Investor 2"
        high_gross = max(gross_1, gross_2)
        
        # Calculate Tax Savings Efficiency
        out_of_pocket = abs(pre_tax_cashflow) if pre_tax_cashflow < 0 else 0
        tse = (total_tax_variance / out_of_pocket) * 100 if out_of_pocket > 0 else 0

        prompt = f"""
        Act as an Australian Tax Strategist. Based on the property data and the dual-investor profile provided, generate a detailed expansion for 'Section 3: Property Performance' of the Investment Report.

        Context Variables:
        - Property: {address}
        - Investor 1 Gross Income: ${gross_1:,.0f}
        - Investor 2 Gross Income: ${gross_2:,.0f}
        - Ownership Split: {split*100}% to Investor 1
        - Total Annual Taxable Property Loss: ${abs(net_tax_loss):,.0f}
        - Pre-Tax Cash Flow: ${pre_tax_cashflow:,.0f}
        - Total Tax Refund: ${total_tax_variance:,.0f}
        - Tax Savings Efficiency: {tse:.1f}%

        Instructions:
        1. Performance Expansion: Analyze the Pre-Tax vs. Post-Tax Cash Flow. Explain how the 'paper loss' (Depreciation + Interest) converts a negative pre-tax position into a stronger household net position. Mention the calculated Tax Savings Efficiency.
        2. High-Income Earner Strategy (Focus on {high_earner} earning ${high_gross:,.0f}): Detail Marginal Relief (how every $1 of property loss offsets their specific salary reducing tax at their highest marginal rate), Medicare Levy Impact (2% saving), and Optimal Ownership Rationale (explain why the split maximizes 'Tax Arbitrage' between high-income tax savings today and discounted CGT in the future).
        3. Tone & Format: Use professional, clinical financial language. 
        CRITICAL FORMATTING REQUIREMENT: Return ONLY plain text separated by double line breaks for new paragraphs. Do NOT use markdown bolding (**), hash symbols (#), bullet points, or any other markdown styling, as it will cause errors in the PDF renderer.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ AI API Error (Tax Strategy): {e}")
        return None


# --- 1. GLOBAL INPUTS (SIDEBAR) ---
st.sidebar.header("📍 Core Parameters")

property_name = st.sidebar.text_input("Property Name/Address", key="sb_prop_name")
property_url = st.sidebar.text_input("Property Listing URL", key="sb_prop_url")

col_spec1, col_spec2, col_spec3 = st.sidebar.columns(3)
beds = col_spec1.number_input("Beds", step=1, key="sb_beds")
baths = col_spec2.number_input("Baths", step=1, key="sb_baths")
cars = col_spec3.number_input("Cars", step=1, key="sb_cars")

purchase_price = st.sidebar.number_input("Purchase Price ($)", step=10000.0, key="sb_price")

st.sidebar.subheader("Tax Profiles (Post-Tax)")

# Investor 1
col_s1_val, col_s1_freq = st.sidebar.columns([2, 1])
s1_input = col_s1_val.number_input("Inv 1 Take-Home ($)", step=100.0, key="salary_input_1")
s1_freq = col_s1_freq.selectbox("Freq", ["Fortnightly", "Monthly", "Annually"], key="s1_freq_selector")

# Investor 2
col_s2_val, col_s2_freq = st.sidebar.columns([2, 1])
s2_input = col_s2_val.number_input("Inv 2 Take-Home ($)", step=100.0, key="salary_input_2")
s2_freq = col_s2_freq.selectbox("Freq", ["Monthly", "Fortnightly", "Annually"], key="s2_freq_selector")

# --- Mapping for annualization ---
freq_map = {"Monthly": 12, "Fortnightly": 26, "Annually": 1}
salary_1_annual = float(s1_input * freq_map[s1_freq])
salary_2_annual = float(s2_input * freq_map[s2_freq])
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

# --- AI AUTO-FILL TRIGGER ---
st.sidebar.markdown("---")
st.sidebar.subheader("✨ AI Automation")
if st.sidebar.button("Auto-Estimate Fields", use_container_width=True):
    with st.spinner("Analyzing location and property specs..."):
        # Clear the cache so it forces a fresh API call if it failed previously
        fetch_comprehensive_estimates.clear()
        estimates = fetch_comprehensive_estimates(property_name, purchase_price, beds, baths, cars)
        
        # CRITICAL FIX: Explicitly check that estimates is a valid dictionary
        if estimates and isinstance(estimates, dict):
            st.session_state.form_data.update({
                "stamp_duty": float(estimates.get("stamp_duty", 34100.0)),
                "legal_fees": float(estimates.get("legal_fees", 1500.0)),
                "building_pest": float(estimates.get("building_pest", 600.0)),
                "monthly_rent": float(estimates.get("monthly_rent", 3683.33)),
                "vacancy_pct": float(estimates.get("vacancy_pct", 5.0)),
                "mgt_fee_m": float(estimates.get("mgt_fee_m", 276.25)),
                "strata_m": float(estimates.get("strata_m", 500.0)),
                "insurance_m": float(estimates.get("insurance_m", 45.0)),
                "rates_m": float(estimates.get("rates_m", 165.0)),
                "maint_m": float(estimates.get("maint_m", 150.0)),
                "water_m": float(estimates.get("water_m", 80.0)),
                "div_43": float(estimates.get("div_43", 9000.0)),
                "div_40": float(estimates.get("div_40", 8500.0)),
                "growth": float(estimates.get("expected_annual_growth", st.session_state.form_data["growth"])),
                "is_ai_estimated": True
            })
            st.sidebar.success("Fields updated!")
            st.rerun() 
        else:
            # Graceful failure message
            st.sidebar.error("AI failed to return valid data. Check your terminal logs for the error.")

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
    stamp_duty = col1.number_input("Stamp Duty ($)", value=float(st.session_state.form_data.get("stamp_duty", 34100.0)), step=1000.0)
    legal_fees = col2.number_input("Legal & Conveyancing ($)", value=float(st.session_state.form_data.get("legal_fees", 1500.0)), step=100.0)
    building_pest = col1.number_input("Building & Pest ($)", value=float(st.session_state.form_data.get("building_pest", 600.0)), step=50.0)
    loan_setup = col2.number_input("Loan Setup Fees ($)", value=float(st.session_state.form_data.get("loan_setup", 500.0)), step=50.0)
    buyers_agent = col1.number_input("Buyers Agent ($)", value=float(st.session_state.form_data.get("buyers_agent", 5000.0)), step=500.0)
    other_entry = col2.number_input("Other Entry Costs ($)", value=float(st.session_state.form_data.get("other_entry", 1000.0)), step=100.0)
    
    total_acquisition_costs = stamp_duty + legal_fees + building_pest + loan_setup + buyers_agent + other_entry
    total_cost_base = purchase_price + total_acquisition_costs
    
    st.metric("Total Acquisition Costs", f"${total_acquisition_costs:,.2f}")
    st.metric("Total Required (Property + Costs)", f"${total_cost_base:,.2f}")

# --- TAB 2: INCOME & EXPENSES ---
with tab2:
    st.subheader("Cash Flow Essentials (Monthly Sourced)")
    c1, c2 = st.columns(2)
    
    monthly_rent = c1.number_input("Monthly Rent Received ($)", value=float(st.session_state.form_data.get("monthly_rent", 3683.33)), step=100.0)
    vacancy_pct = c1.number_input("Vacancy Rate (%)", value=float(st.session_state.form_data.get("vacancy_pct", 5.0)), step=1.0)
    
    # ---> THE MISSING MATH LINE IS BACK <---
    annual_gross_income = (monthly_rent * 12) * (1 - (vacancy_pct / 100))
    
    mgt_fee_m = c2.number_input("Property Management (Monthly $)", value=float(st.session_state.form_data.get("mgt_fee_m", 276.25)), step=10.0)
    strata_m = c2.number_input("Strata/Body Corporate (Monthly $)", value=float(st.session_state.form_data.get("strata_m", 500.0)), step=10.0)
    insurance_m = c2.number_input("Landlord Insurance (Monthly $)", value=float(st.session_state.form_data.get("insurance_m", 45.0)), step=5.0)
    rates_m = c2.number_input("Council Rates (Monthly $)", value=float(st.session_state.form_data.get("rates_m", 165.0)), step=10.0)
    maint_m = c2.number_input("Maintenance (Monthly $)", value=float(st.session_state.form_data.get("maint_m", 150.0)), step=10.0)
    water_m = c2.number_input("Water Service (Monthly $)", value=float(st.session_state.form_data.get("water_m", 80.0)), step=5.0)
    other_m = c2.number_input("Other (Monthly $)", value=float(st.session_state.form_data.get("other_m", 25.0)), step=5.0)
    
    # ---> THE EXPENSE MATH LINES ARE BACK <---
    total_monthly_expenses = mgt_fee_m + strata_m + insurance_m + rates_m + maint_m + water_m + other_m
    total_operating_expenses = total_monthly_expenses * 12
    
    st.divider()
    metric_col1, metric_col2 = st.columns(2)
    metric_col1.metric("Gross Annual Income", f"${annual_gross_income:,.2f}")
    metric_col2.metric("Total Annual Expenses", f"${total_operating_expenses:,.2f}")

# --- TAB 3: LOAN DETAILS (UPDATED FOR EQUITY FUNDING) ---
with tab3:
    st.subheader("1. Core Investment Loan (Secured by Investment)")
    
    c1, c2 = st.columns(2)
    lvr_pct = c1.slider("LVR (%)", 0, 100, 80) / 100
    interest_rate = c2.number_input("Interest Rate (%)", value=5.49, step=0.01) / 100
    loan_term = c1.number_input("Loan Term (Years)", value=30, step=1)
    loan_type = c2.selectbox("Active Repayment Type (For Cash Flow)", ["Interest Only", "Principal & Interest"])
    
    loan_amount = purchase_price * lvr_pct
    monthly_io = (loan_amount * interest_rate) / 12
    monthly_pi = abs(npf.pmt(interest_rate/12, loan_term*12, loan_amount))
    
    if loan_type == "Interest Only":
        core_annual_repayment = monthly_io * 12
    else:
        core_annual_repayment = monthly_pi * 12
    core_annual_interest = loan_amount * interest_rate 
        
    st.divider()
    st.subheader("2. Deposit Funding (Equity Release Loan)")
    st.info("💡 Interest on equity loans used to fund deposits/stamp duty is tax-deductible.")
    
    # Safety check to prevent KeyErrors
    use_equity = st.checkbox("Fund Deposit via Equity Release?", value=st.session_state.form_data.get("use_eq", True))
    
    eq1, eq2 = st.columns(2)
    if use_equity:
        eq_amount = eq1.number_input("Equity Loan Amount ($)", value=float(st.session_state.form_data.get("eq_amount", 170000.0)), step=5000.0)
        eq_rate = eq2.number_input("Equity Loan Rate (%)", value=float(st.session_state.form_data.get("eq_rate", 6.20)), step=0.01) / 100
        
        # Equity loans are assumed 30-year P&I as per user notes
        eq_monthly_pi = abs(npf.pmt(eq_rate/12, 30*12, eq_amount))
        eq_annual_repayment = eq_monthly_pi * 12
        eq_annual_interest = eq_amount * eq_rate
    else:
        eq_amount = 0.0; eq_rate = 0.0; eq_monthly_pi = 0.0; eq_annual_repayment = 0.0; eq_annual_interest = 0.0

    # AGGREGATE TOTALS FOR DOWNSTREAM TABS
    total_annual_debt_repayment = core_annual_repayment + eq_annual_repayment
    total_tax_deductible_interest = core_annual_interest + eq_annual_interest
    actual_cash_outlay = total_cost_base - loan_amount - eq_amount

    # CRITICAL FIX: Re-declare legacy variables so Tab 0, Tab 6, and PDF don't crash
    annual_interest = total_tax_deductible_interest
    annual_repayment = total_annual_debt_repayment

# --- TAB 4: CASH FLOW ---
with tab4:
    st.subheader("Pre-Tax Cash Flow")
    
    net_operating_income = annual_gross_income - total_operating_expenses
    pre_tax_cashflow = net_operating_income - total_annual_debt_repayment
    
    st.divider()
    cf_col1, cf_col2 = st.columns([1, 1])
    with cf_col1:
        st.write("**Annual Rental Income**")
        st.write("**Annual Operating Expenses**")
        st.write("**Net Operating Income (NOI)**")
        st.write(f"**Total Debt Service (Core + Equity Loan)**")
        st.markdown("### **Annual Cash Flow**")
    with cf_col2:
        st.write(f"${annual_gross_income:,.2f}")
        st.write(f"-${total_operating_expenses:,.2f}")
        st.write(f"**${net_operating_income:,.2f}**")
        st.write(f"-${total_annual_debt_repayment:,.2f}")
        if pre_tax_cashflow < 0:
            st.markdown(f"<h3 style='color: #ff4b4b;'>-${abs(pre_tax_cashflow):,.2f}</h3>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h3 style='color: #00cc96;'>${pre_tax_cashflow:,.2f}</h3>", unsafe_allow_html=True)

# --- TAB 5: DEPRECIATION ---
with tab5:
    st.subheader("Tax Depreciation (Non-Cash Deductions)")
    div_43 = st.number_input("Capital Works (Div 43) ($)", value=float(st.session_state.form_data.get("div_43", 9000.0)), step=500.0)
    div_40 = st.number_input("Plant & Equipment (Div 40) ($)", value=float(st.session_state.form_data.get("div_40", 8500.0)), step=500.0)
    total_depreciation = div_43 + div_40
    st.metric("Total Annual Depreciation", f"${total_depreciation:,.2f}")

# --- TAB 6: TAX, GEARING & SERVICEABILITY ---
with tab6:
    st.subheader("Household Tax Impact & Cash Flow")
    st.info("💡 **Note:** To calculate accurate negative gearing benefits, the ATO applies property losses against your **Pre-Tax (Gross)** income. Enter your Gross incomes below.")
    
    # --- NEW: Gross Income Inputs for Accurate Tax Brackets ---
    g1, g2 = st.columns(2)
    gross_income_1 = g1.number_input("Inv 1 Gross Taxable Income ($)", value=99106.28, step=5000.0, key="gross_1")
    gross_income_2 = g2.number_input("Inv 2 Gross Taxable Income ($)", value=101157.96, step=5000.0, key="gross_2")

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
    
    # --- FIX: Tax Variance now uses Gross Income ---
    base_tax_1 = calculate_tax(gross_income_1)
    new_tax_1 = calculate_tax(max(0, gross_income_1 + property_income_1))
    tax_variance_1 = base_tax_1 - new_tax_1
    
    base_tax_2 = calculate_tax(gross_income_2)
    new_tax_2 = calculate_tax(max(0, gross_income_2 + property_income_2))
    tax_variance_2 = base_tax_2 - new_tax_2
    
    total_tax_variance = tax_variance_1 + tax_variance_2
    post_tax_cashflow = pre_tax_cashflow + total_tax_variance

    # Display Tax Metrics
    st.divider()
    t_col1, t_col2 = st.columns(2)
    t_col1.metric("Pre-Tax Cash Flow (Annual)", f"${pre_tax_cashflow:,.2f}")
    
    if total_tax_variance > 0:
        t_col2.metric("Combined Estimated Tax Refund", f"${total_tax_variance:,.2f}")
    else:
        t_col2.metric("Combined Estimated Tax Payable", f"${abs(total_tax_variance):,.2f}")
        
    st.metric("Household Net Post-Tax Cash Flow (Annual)", f"${post_tax_cashflow:,.2f}")

    st.divider()

    # 2. COMPREHENSIVE SERVICEABILITY CHECK (Remains based on Take-Home Pay)
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
        st.write("**Monthly Inflows (Take-Home)**")
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
                
                # CRITICAL FIX: The Revisit button now uses a Callback (on_click)
                c4.button("🔄 Revisit", key=f"rev_{index}", on_click=load_property, args=(row,))
                
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

    # Restored 'value=' parameters to keep your defaults, removed 'key=' to prevent warnings
    ext_mortgage = d1.number_input("Existing Mortgage(s) ($)", value=float(st.session_state.form_data.get("ext_mortgage", 2921.0)), step=100.0)
    ext_car_loan = d2.number_input("Car Loan(s) ($)", value=float(st.session_state.form_data.get("ext_car_loan", 0.0)), step=50.0)
    ext_cc = d3.number_input("Credit Card Payments ($)", value=float(st.session_state.form_data.get("ext_cc", 0.0)), step=50.0, help="Typically assessed at 3-4% of total limit")
    ext_other = d4.number_input("Other Loans ($)", value=float(st.session_state.form_data.get("ext_other", 0.0)), step=50.0)
    
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

# ==========================================================
# --- EXPORT & SAVE SECTION (BOTTOM OF SCRIPT) ---
# ==========================================================
st.markdown("---")
st.subheader("📄 Export Analysis Report")

def generate_pdf(salary_1_annual, salary_2_annual, total_monthly_living, total_existing_debt_m, gross_1, gross_2, net_taxable_income, pre_tax_cf, tax_variance):
    # 1. ADD THESE TWO LINES RIGHT HERE AT THE TOP
    is_ai = st.session_state.form_data.get("is_ai_estimated", False)
    ai_tag = " (AI Estimated)" if is_ai else " (Manual/Default)"

    market_yield = fetch_market_yield(property_name, beds, baths, cars)
    property_yield = (annual_gross_income / purchase_price) * 100

    class InvestmentReportPDF(FPDF):
        def header(self):
            logo_path = "AQI_Logo.png" 
            if os.path.exists(logo_path): self.image(logo_path, 10, 8, 30)
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
            else: self.ln(7)

    pdf = InvestmentReportPDF()
    pdf.add_page()
    
    # --- HEADER ---
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 8, property_name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 7, f"Configuration: {beds} Bed | {baths} Bath | {cars} Car", new_x="LMARGIN", new_y="NEXT")
    if property_url and property_url.strip() != "" and property_url != "https://www.realestate.com.au/":
        pdf.set_font("helvetica", "U", 9); pdf.set_text_color(0, 102, 204) 
        pdf.cell(0, 6, "View Listing Online", link=property_url, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0) 
    pdf.ln(3)

    # --- 1. ACQUISITION & FINANCE ---
    # 2. UPDATE THIS HEADER TO INCLUDE THE AI TAG
    pdf.section_header(f"1. Acquisition & Finance (100% Debt Funded Structure){ai_tag}")
    
    pdf.row("Purchase Price:", f"${purchase_price:,.0f}", "Core Loan Amount:", f"${loan_amount:,.0f} ({lvr_pct*100:.0f}% LVR)")
    
    if use_equity:
        pdf.row("Total Entry Costs:", f"${total_acquisition_costs:,.0f}", "Equity Release Loan:", f"${eq_amount:,.0f}")
        pdf.set_text_color(0, 128, 0) # Green for zero cash
        pdf.row("Total Capital Required:", f"${total_cost_base:,.0f}", "CASH FROM SAVINGS:", f"${actual_cash_outlay:,.0f}")
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.row("Total Entry Costs:", f"${total_acquisition_costs:,.0f}", "Total Cash Outlay:", f"${actual_cash_outlay:,.0f}")
        
    pdf.ln(3)

    # --- 2. YIELD ANALYSIS ---
    pdf.section_header("2. Yield Analysis & Market Comparison (AI Estimated)")
    net_yield = ((annual_gross_income - total_operating_expenses) / purchase_price) * 100
    pdf.row("Property Gross Yield:", f"{property_yield:.2f}%", "Property Net Yield:", f"{net_yield:.2f}%")
    if market_yield:
        variance = property_yield - market_yield
        pdf.set_text_color(0, 128, 0) if variance >= 0 else pdf.set_text_color(200, 0, 0)
        status = f"{'Outperforming' if variance >= 0 else 'Underperforming'} by {abs(variance):.2f}%"
        pdf.row("Est. Suburb Average:", f"{market_yield:.2f}%", "Market Status:", status)
    else:
        pdf.set_text_color(128, 128, 128); pdf.row("Est. Suburb Average:", "Data Unavailable", "Market Status:", "N/A")
    pdf.set_text_color(0, 0, 0); pdf.ln(3)

    # --- 3. PROPERTY PERFORMANCE ---
    pdf.section_header(f"3. Property Performance (Annual Pre-Tax){ai_tag}")
    
    if actual_cash_outlay > 0:
        cash_on_cash = f"{(pre_tax_cf / actual_cash_outlay) * 100:.2f}%"
    else:
        cash_on_cash = "Infinite (100% Financed)"

    pdf.row(f"Gross Rent ({vacancy_pct:.1f}% Vac):", f"${annual_gross_income:,.0f}", "Operating Expenses:", f"-${total_operating_expenses:,.0f}")
    pdf.set_font("helvetica", "I", 8); pdf.set_text_color(120, 120, 120)
    pdf.cell(95, 4, "", border=0); pdf.cell(0, 4, f"(Strata: ${strata_m*12:,.0f} | Mgt: ${mgt_fee_m*12:,.0f} | Other: ${(rates_m+water_m+insurance_m+maint_m+other_m)*12:,.0f})", border=0, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0); pdf.ln(1)
    
    pdf.row("Total Interest Deductible:", f"-${total_tax_deductible_interest:,.0f}", "Net Property Cash Flow:", f"${pre_tax_cf:,.2f}")
    
    pdf.set_font("helvetica", "I", 10); pdf.set_text_color(0, 102, 204)
    pdf.cell(50, 7, "Cash-on-Cash Return:", border=0); pdf.set_font("helvetica", "B", 10); pdf.cell(45, 7, f"{cash_on_cash}", border=0)
    pdf.set_font("helvetica", "I", 10); pdf.cell(50, 7, "Est. Additional Tax Refund:", border=0); pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 7, f"${tax_variance:,.2f}", border=0, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0); pdf.ln(3)

    # --- INJECT AI TAX STRATEGY HERE ---
    pdf.section_header("Strategic Taxation Analysis (AI Generated)")
    tax_strategy_text = fetch_tax_strategy_summary(property_name, gross_1, gross_2, ownership_split, net_taxable_income, pre_tax_cf, tax_variance)
    
    pdf.set_font("helvetica", "", 10)
    if tax_strategy_text:
        # FPDF handles multi_cell for paragraph wrapping. Cleaned to prevent unicode/smart-quote crashes.
        clean_text = tax_strategy_text.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 6, clean_text)
    else:
        pdf.multi_cell(0, 6, "AI Tax Strategy could not be generated at this time. Please check your API limits or connection.")
    pdf.ln(5)

    # --- 4. HOUSEHOLD SERVICEABILITY ---
    pdf.section_header("4. Monthly Household Serviceability")
    total_household_net_m = (salary_1_annual + salary_2_annual) / 12
    shaded_rent_m = (monthly_rent * 0.80) 
    core_mortgage_m = monthly_io if loan_type == "Interest Only" else monthly_pi
    prop_expenses_m = total_operating_expenses / 12
    
    # 1. Real World Math
    net_monthly_surplus = (total_household_net_m + shaded_rent_m) - (total_monthly_living + total_existing_debt_m + core_mortgage_m + eq_monthly_pi + prop_expenses_m)

    # 2. Bank Stress Test Math (+3% on new loans, +30% repayment buffer on existing mortgage)
    stress_core_pi = abs(npf.pmt((interest_rate+0.03)/12, loan_term*12, loan_amount))
    stress_eq_pi = abs(npf.pmt((eq_rate+0.03)/12, 30*12, eq_amount)) if use_equity else 0
    stressed_existing_mortgage = ext_mortgage * 1.30 
    stressed_other_debt = total_existing_debt_m - ext_mortgage
    total_stressed_existing = stressed_existing_mortgage + stressed_other_debt
    
    bank_assessed_surplus = (total_household_net_m + shaded_rent_m) - (total_monthly_living + total_stressed_existing + stress_core_pi + stress_eq_pi + prop_expenses_m)

    # Print the distinct breakdown
    pdf.set_font("helvetica", "B", 10); pdf.cell(0, 7, "Serviceability Breakdown (Monthly):", new_x="LMARGIN", new_y="NEXT"); pdf.set_font("helvetica", "", 10)
    pdf.row("Take-Home Pay:", f"${total_household_net_m:,.2f}", "Living Expenses:", f"-${total_monthly_living:,.2f}")
    pdf.row("Rental Income (80%):", f"${shaded_rent_m:,.2f}", "Prop. Operating Exp:", f"-${prop_expenses_m:,.2f}")
    
    # Splitting out the loans
    pdf.row("Existing Debts (PPOR):", f"-${total_existing_debt_m:,.2f}", "New Equity Loan:", f"-${eq_monthly_pi:,.2f}" if use_equity else "$0.00")
    pdf.row("New Core Loan:", f"-${core_mortgage_m:,.2f}", "", "")
    
    pdf.ln(2)
    
    # Print Real-World Surplus (Green/Red)
    if net_monthly_surplus >= 0:
        pdf.set_text_color(0, 128, 0); pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 7, f"REAL-WORLD MONTHLY SURPLUS: ${net_monthly_surplus:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_text_color(200, 0, 0); pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 7, f"REAL-WORLD MONTHLY DEFICIT: ${abs(net_monthly_surplus):,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
        
    # Print Bank Assessed Surplus (Blue/Red)
    if bank_assessed_surplus >= 0:
        pdf.set_text_color(0, 102, 204); pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 7, f"BANK ASSESSED SURPLUS (Stressed): ${bank_assessed_surplus:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_text_color(200, 0, 0); pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 7, f"BANK ASSESSED DEFICIT (Stressed): ${abs(bank_assessed_surplus):,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    
    # DTI and Disclaimer
    total_new_debt_amount = loan_amount + eq_amount
    dti = total_new_debt_amount / (salary_1_annual + salary_2_annual) if (salary_1_annual + salary_2_annual) > 0 else 0

    pdf.set_text_color(100, 100, 100); pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 5, f"New Debt to Net Income (DTI): {dti:.1f}x  |  Bank assessment assumes +3% P&I and +30% on existing mortgages", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0); pdf.ln(3)

    # --- 5. EXIT STRATEGY ---
    pdf.section_header(f"5. Exit Strategy & CGT Projection (Year {holding_period})")
    pdf.row("Est. Sale Price:", f"${future_values[-1]:,.0f}", "Gross Capital Gain:", f"${capital_gain:,.0f}")
    pdf.row("Marginal Tax Rate:", f"{est_marginal_rate*100:.1f}%", "Est. CGT Payable:", f"${cgt_payable:,.0f}")
    pdf.set_font("helvetica", "B", 10); pdf.row("NET PROFIT ON SALE:", f"${net_profit_on_sale:,.0f}")
    pdf.ln(3)

    # --- 6. CHARTS ---
    pdf.add_page()
    pdf.section_header("6. Projected Wealth Milestones")
    pdf.set_font("helvetica", "B", 9); pdf.set_fill_color(240, 240, 240)
    pdf.cell(30, 7, "Year", border=1, align="C", fill=True); pdf.cell(80, 7, "Estimated Value", border=1, align="C", fill=True); pdf.cell(80, 7, "Estimated Equity", border=1, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9)
    for yr in [1, 3, 5, 10]:
        if yr <= holding_period:
            val = purchase_price * (1 + growth_rate)**yr
            eq = val - loan_amount - eq_amount # Subtracting BOTH loans for true equity
            pdf.cell(30, 7, f"Year {yr}", border=1, align="C"); pdf.cell(80, 7, f"${val:,.0f}", border=1, align="C"); pdf.cell(80, 7, f"${eq:,.0f}", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(8)
    pdf.section_header("7. Equity & Value Projections")
    fig, ax = plt.subplots(figsize=(8, 4.5)) 
    ax.plot(df_chart.index, df_chart["Property Value"], label="Market Value", color="#003366", linewidth=2.5)
    
    # Calculate true equity accounting for both loans
    true_equity = df_chart["Property Value"] - loan_amount - eq_amount
    ax.plot(df_chart.index, true_equity, label="Equity Position", color="#2ca02c", linewidth=2.5)
    ax.fill_between(df_chart.index, true_equity, color="#2ca02c", alpha=0.1)
    
    ax.set_title(f"Equity Projection ({growth_rate*100:.1f}% Annual Growth)", fontsize=12, fontweight='bold', pad=15)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f'${x:,.0f}'))
    ax.grid(True, axis='y', linestyle="--", alpha=0.5)
    ax.legend(frameon=False, loc="upper left")
    plt.tight_layout(); img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format="png", bbox_inches="tight", dpi=200) 
    pdf.image(img_buffer, x=15, w=180); plt.close()

    return bytes(pdf.output())

# Generate PDF safely outside of column wrappers
pdf_bytes = generate_pdf(
    salary_1_annual, 
    salary_2_annual, 
    total_monthly_living, 
    total_existing_debt_m,
    gross_income_1,
    gross_income_2,
    net_property_taxable_income,
    pre_tax_cashflow,
    total_tax_variance
)

# Package all raw inputs securely to stop Revisit Math bugs
# Package all raw inputs securely to stop Revisit Math bugs
save_data = {
    "purchase_price": purchase_price,
    "beds": beds, "baths": baths, "cars": cars,
    "s1_input": s1_input, "s1_freq": s1_freq, 
    "s2_input": s2_input, "s2_freq": s2_freq, 
    "ownership_split": ownership_split,
    "growth_rate": growth_rate,
    "holding_period": holding_period,
    "living_expenses_json": st.session_state.form_data["living_expenses_json"],
    "ext_mortgage": ext_mortgage,
    "ext_car_loan": ext_car_loan,
    "ext_cc": ext_cc,
    "ext_other": ext_other,
    "use_eq": use_equity,
    "eq_amount": eq_amount,
    "eq_rate": eq_rate * 100, 
    # ADD THE NEW ONES HERE:
    "stamp_duty": stamp_duty,
    "legal_fees": legal_fees,
    "building_pest": building_pest,
    "loan_setup": loan_setup,
    "buyers_agent": buyers_agent,
    "other_entry": other_entry,
    "monthly_rent": monthly_rent,
    "vacancy_pct": vacancy_pct,
    "mgt_fee_m": mgt_fee_m,
    "strata_m": strata_m,
    "insurance_m": insurance_m,
    "rates_m": rates_m,
    "maint_m": maint_m,
    "water_m": water_m,
    "other_m": other_m,
    "div_43": div_43,
    "div_40": div_40,
    "is_ai_estimated": st.session_state.form_data.get("is_ai_estimated", False) # <-- SAVE TO CSV
}

col_save, col_dl = st.columns(2)

with col_save:
    if st.button("💾 Save Property to History", use_container_width=True):
        save_to_history(property_name, property_url, save_data)
        st.toast("✅ Property successfully saved to history!")
        st.rerun()

with col_dl:
    st.download_button(
        label="⬇️ Download Full Summary PDF",
        data=pdf_bytes,
        file_name=f"{property_name.replace(' ', '_')}_Summary.pdf",
        mime="application/pdf",
        on_click=save_to_history,
        args=(property_name, property_url, save_data),
        use_container_width=True
    )