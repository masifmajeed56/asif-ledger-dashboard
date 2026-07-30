import streamlit as st

# 1. State Initializer (Default Left Button Selected)
if 'selected_btn' not in st.session_state:
    st.session_state['selected_btn'] = 'left'  # Options: 'left' or 'right'

# 2. Dynamic Selection CSS
st.markdown("""
<style>
    /* Selected Active Button (Blue + Office Blue Hover) */
    div.btn-selected > div[data-testid="stButton"] > button,
    div.btn-selected button {
        background-color: #003366 !important;
        color: #ffffff !important;
        border: 1px solid #002244 !important;
        font-weight: bold !important;
        transition: all 0.3s ease-in-out !important;
    }
    div.btn-selected button:hover {
        background-color: #002244 !important; /* Office Blue Hover */
        color: #ffffff !important;
        cursor: pointer !important;
        box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.25) !important;
    }

    /* Unselected Inactive Button (White + Light Blue Hover) */
    div.btn-unselected > div[data-testid="stButton"] > button,
    div.btn-unselected button {
        background-color: #ffffff !important;
        color: #003366 !important;
        border: 1px solid #003366 !important;
        font-weight: bold !important;
        transition: all 0.3s ease-in-out !important;
    }
    div.btn-unselected button:hover {
        background-color: #e6f0fa !important;
        color: #002244 !important;
        border-color: #002244 !important;
        cursor: pointer !important;
    }
</style>
""", unsafe_allow_html=True)

# 3. Dynamic Button UI Component
col1, col2 = st.columns(2)

# Check active classes dynamically
left_class = "btn-selected" if st.session_state['selected_btn'] == 'left' else "btn-unselected"
right_class = "btn-selected" if st.session_state['selected_btn'] == 'right' else "btn-unselected"

with col1:
    st.markdown(f'<div class="{left_class}">', unsafe_allow_html=True)
    if st.button("⬅️ Left Option", key="dynamic_left_btn", use_container_width=True):
        st.session_state['selected_btn'] = 'left'
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown(f'<div class="{right_class}">', unsafe_allow_html=True)
    if st.button("Right Option ➡️", key="dynamic_right_btn", use_container_width=True):
        st.session_state['selected_btn'] = 'right'
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)