import streamlit as st
import json
import os

st.set_page_config(page_title="Flight Deals",layout="wide")

st.title("✈️ Flight Deals Dashboard")

file="deals_log.json"

# If no file yet
if not os.path.exists(file):
    st.warning("No deals logged yet.")
    st.stop()

# Load data
data=json.load(open(file))

dates=sorted(data.keys(),reverse=True)

# Date selector
selected=st.selectbox("📅 Select date",dates)

st.subheader(f"Deals for {selected}")

deals=data[selected]

# Display deals
if not deals:
    st.info("No deals found that day.")
else:
    for deal in deals:
        st.markdown(f"""
        <div style='padding:15px;border:1px solid #ddd;border-radius:10px;margin-bottom:10px'>
        <pre>{deal}</pre>
        </div>
        """,unsafe_allow_html=True)
