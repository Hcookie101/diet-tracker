import streamlit as st
import pandas as pd
import datetime
import os
import requests
import plotly.express as px

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="MacroTracker Pro", page_icon="🥗", layout="centered")

st.markdown("""
    <style>
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }
    [data-testid="stMetric"] {
        background-color: rgba(28, 131, 225, 0.05);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid rgba(28, 131, 225, 0.1);
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA HANDLING ---
DB_FILE = "nutrition_data.csv"

if 'calorie_goal' not in st.session_state:
    st.session_state.calorie_goal = 2000

COMMON_FOODS = {
    "Egg (Large)": {"c": 70, "p": 6, "cb": 0, "f": 5},
    "Chicken Breast (100g)": {"c": 165, "p": 31, "cb": 0, "f": 3.6},
    "White Rice (1 cup cooked)": {"c": 205, "p": 4.3, "cb": 45, "f": 0.4},
    "Greek Yogurt (100g)": {"c": 59, "p": 10, "cb": 3.6, "f": 0.4},
    "Apple (Medium)": {"c": 95, "p": 0.5, "cb": 25, "f": 0.3},
    "Banana (Medium)": {"c": 105, "p": 1.3, "cb": 27, "f": 0.4},
    "Oatmeal (1 cup cooked)": {"c": 150, "p": 6, "cb": 27, "f": 3},
    "Avocado (Half)": {"c": 160, "p": 2, "cb": 8.5, "f": 15},
}

def load_data():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        return df
    return pd.DataFrame(columns=["Date", "Name", "Calories", "Protein", "Carbs", "Fat"])

def save_data(df):
    df.to_csv(DB_FILE, index=False)

if 'food_df' not in st.session_state:
    st.session_state.food_df = load_data()
if 'import_data' not in st.session_state:
    st.session_state.import_data = None

# --- 3. UI TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Today", "➕ Add Food", "⚙️ History & Settings"])

# --- TAB 1: TODAY'S DIARY ---
with tab1:
    today = datetime.date.today()
    day_df = st.session_state.food_df[st.session_state.food_df['Date'] == today]
    total_cals = int(day_df['Calories'].sum())
    
    st.header(f"Today's Progress ({today.strftime('%b %d')})")
    
    progress_perc = min(total_cals / st.session_state.calorie_goal, 1.0)
    st.progress(progress_perc)
    st.write(f"**{total_cals}** / **{st.session_state.calorie_goal}** kcal")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cals", f"{total_cals}")
    c2.metric("Prot", f"{int(day_df['Protein'].sum())}g")
    c3.metric("Carb", f"{int(day_df['Carbs'].sum())}g")
    c4.metric("Fat", f"{int(day_df['Fat'].sum())}g")

    st.divider()

    if day_df.empty:
        st.info("Nothing logged for today yet.")
    else:
        for idx, row in day_df.iterrows():
            with st.expander(f"🍴 {row['Name']} — {row['Calories']} kcal"):
                col_i, col_d = st.columns([4, 1])
                col_i.write(f"P: {row['Protein']}g | C: {row['Carbs']}g | F: {row['Fat']}g")
                if col_d.button("Delete", key=f"del_{idx}"):
                    st.session_state.food_df = st.session_state.food_df.drop(idx)
                    save_data(st.session_state.food_df)
                    st.rerun()

# --- TAB 2: ADD FOOD ---
with tab2:
    st.header("Log Food")
    st_sub1, st_sub2 = st.tabs(["⚡ Quick Add", "🔍 Database Search"])
    
    with st_sub1:
        sel = st.selectbox("Staples:", ["Select..."] + list(COMMON_FOODS.keys()))
        if sel != "Select...":
            d = COMMON_FOODS[sel]
            q_col, _ = st.columns([1, 2])
            qty = q_col.number_input("Quantity", 1.0, step=0.5, key="q_qty")
            if st.button(f"Import {qty}x {sel}", width='stretch'):
                st.session_state.import_data = {
                    "name": f"{sel} (x{qty})", 
                    "cals": round(d['c'] * qty, 1), "prot": round(d['p'] * qty, 1),
                    "carb": round(d['cb'] * qty, 1), "fat": round(d['f'] * qty, 1)
                }

    with st_sub2:
        query = st.text_input("Search Brand or Product")
        if query:
            with st.spinner("⚡ Fast-searching database..."):
                # Use the 'fields' parameter to only download what we need (Names and Macros)
                # This makes the search 3x-4x faster
                fields = "product_name,brands,nutriments,id,serving_size"
                url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&json=1&page_size=5&fields={fields}"
                
                try:
                    # Increased timeout to 15 seconds as a safety net
                    response = requests.get(url, timeout=15)
                    
                    if response.status_code == 200:
                        items = response.json().get('products', [])
                        
                        if not items:
                            st.warning("No results. Try a more specific name (e.g. 'Quaker Oats').")
                        
                        for i in items:
                            n = i.get('product_name', 'Unknown Product')
                            brand = i.get('brands', 'Generic')
                            
                            with st.expander(f"{n} ({brand})"):
                                nut = i.get('nutriments', {})
                                # Use Kcal if available, otherwise 0
                                c_base = nut.get('energy-kcal_100g', 0)
                                
                                st.write(f"Per 100g: {c_base} kcal")
                                mul = st.number_input("Portion x", 1.0, step=0.1, key=f"api_{i.get('id', n)}")
                                
                                if st.button("Import", key=f"btn_{i.get('id', n)}"):
                                    st.session_state.import_data = {
                                        "name": f"{n} ({brand})", 
                                        "cals": round(float(c_base) * mul, 1),
                                        "prot": round(float(nut.get('proteins_100g', 0)) * mul, 1),
                                        "carb": round(float(nut.get('carbohydrates_100g', 0)) * mul, 1),
                                        "fat": round(float(nut.get('fat_100g', 0)) * mul, 1)
                                    }
                                    st.success("Data imported! Scroll down to save.")
                                    st.rerun()
                    else:
                        st.error("The database server is busy. Please try again in a moment.")
                
                except requests.exceptions.Timeout:
                    st.error("The search timed out. This usually happens on slow Wi-Fi or if the food database is down. Try using 'Quick Add' for now.")
                except Exception as e:
                    st.error(f"Connection Error: {e}")
    st.divider()
    st.subheader("Review & Save")
    imp = st.session_state.import_data or {"name": "", "cals": 0.0, "prot": 0.0, "carb": 0.0, "fat": 0.0}
    
    with st.form("final_log_form", clear_on_submit=True):
        # NEW: Date Picker Added Here
        log_date = st.date_input("Eating Date", datetime.date.today())
        
        f_name = st.text_input("Name", value=imp['name'])
        f_cals = st.number_input("Calories", value=float(imp['cals']))
        c_a, c_b, c_c = st.columns(3)
        f_p = c_a.number_input("Protein", value=float(imp['prot']))
        f_c = c_b.number_input("Carbs", value=float(imp['carb']))
        f_f = c_c.number_input("Fat", value=float(imp['fat']))
        
        if st.form_submit_button("✅ Save to tracker", width='stretch'):
            if f_name:
                new_row = {"Date": log_date, "Name": f_name, "Calories": f_cals, 
                           "Protein": f_p, "Carbs": f_c, "Fat": f_f}
                st.session_state.food_df = pd.concat([st.session_state.food_df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.food_df)
                st.session_state.import_data = None
                st.success(f"Logged for {log_date}!")
                st.rerun()

# --- TAB 3: HISTORY & SETTINGS ---
with tab3:
    col_hist, col_set = st.columns([2, 1])
    
    with col_set:
        st.subheader("⚙️ Settings")
        st.session_state.calorie_goal = st.number_input("Daily Goal", value=st.session_state.calorie_goal, step=50)
        if st.button("Clear All Data"):
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            st.session_state.food_df = pd.DataFrame(columns=["Date", "Name", "Calories", "Protein", "Carbs", "Fat"])
            st.rerun()

    with col_hist:
        st.subheader("📈 History")
        if not st.session_state.food_df.empty:
            df_p = st.session_state.food_df.copy()
            df_p['Date'] = pd.to_datetime(df_p['Date']).dt.date
            df_g = df_p.groupby('Date')[['Protein', 'Carbs', 'Fat']].sum().reset_index()
            
            # Linear Trend Chart
            fig = px.area(df_g.melt(id_vars='Date'), x="Date", y="value", color="variable", 
                          title="Daily Macros", labels={'value':'Grams', 'variable':'Macro'})
            fig.update_xaxes(type='date', tickformat="%b %d")
            st.plotly_chart(fig, width='stretch')
            
            st.write("**Full Log**")
            st.dataframe(st.session_state.food_df.sort_values('Date', ascending=False), width='stretch')