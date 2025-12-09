import os
import tempfile

import google.generativeai as genai
import streamlit as st


def file_search_page():
    st.header("🔍 Gemini File Search")
    st.markdown("Upload a file and ask questions about it using the Gemini API.")

    gemini_api_key = st.text_input(
        "Gemini API Key",
        value=st.session_state.get("gemini_api_key", ""),
        type="password",
    )

    uploaded_file = st.file_uploader("Upload a document", type=["txt", "pdf", "md"])

    if uploaded_file:
        if st.button("Process File"):
            if not gemini_api_key:
                st.error("Please enter your Gemini API key.")
                return

            genai.configure(api_key=gemini_api_key)

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(uploaded_file.name)[1]
            ) as tmp:
                tmp.write(uploaded_file.getvalue())
                file_path = tmp.name

            with st.spinner("Uploading file to Gemini..."):
                try:
                    # Upload the file to the Gemini API
                    uploaded_file_response = genai.upload_file(path=file_path)
                    st.session_state["file_search_file"] = uploaded_file_response
                    st.success(
                        f"File uploaded successfully: {uploaded_file_response.name}"
                    )
                except Exception as e:
                    st.error(f"Failed to upload file: {e}")
                finally:
                    os.unlink(file_path)

    if "file_search_file" in st.session_state:
        question = st.text_area("Ask a question about the file")
        if st.button("Get Answer"):
            if not question:
                st.error("Please enter a question.")
                return

            with st.spinner("Searching for the answer..."):
                try:
                    file = st.session_state["file_search_file"]
                    model = genai.GenerativeModel(
                        model_name="gemini-2.5-flash",
                        system_instruction="You are a helpful assistant.",
                    )
                    response = model.generate_content([file, question])
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"An error occurred: {e}")
