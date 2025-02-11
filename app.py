import asyncio
import streamlit as st
from crud_pg import ask

st.set_page_config(page_title="Note Manager", layout="centered")
st.title("My Note Dashboard")
st.write("Type instructions below to create, retrieve, or list notes.")
user_input = st.text_area("What do you want to do?", placeholder="e.g., 'Create a note about my Monday meeting.'")
if st.button("Submit"):
    if not user_input.strip():
        st.error("Please enter something.")
    else:
        with st.spinner("Working on it..."):
            try:
                response = asyncio.run(ask(user_input))
                if response.note is not None:
                    st.success(response.message)
                    st.subheader(f"Note Title: {response.note.get('title', '')}")
                    st.write(response.note.get('text', 'No content found.'))
                elif response.titles is not None:
                    st.success(response.message)
                    if response.titles:
                        st.subheader("Current Titles:")
                        for t in response.titles:
                            st.write(f"- {t}")
                    else:
                        st.info("No notes available yet.")
                else:
                    st.info(response.message)
            except Exception as e:
                st.error(f"Error: {e}")