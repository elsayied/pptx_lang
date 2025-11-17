# streamlit_app.py
import streamlit as st
import tempfile
import os
import httpx
# Import core backend functions
from pptx_utils import (
    create_presentation_from_markdown, 
    extract_content_with_docling, 
    generate_structured_markdown,
    DOCLING_AVAILABLE,
    HARDCODED_GEMINI_API_KEY
)

# --- Streamlit Session State & Logic ---

def init_session_state():
    """Initialize Streamlit session state variables."""
    if 'markdown_content' not in st.session_state:
        st.session_state['markdown_content'] = ""
    if 'raw_extracted_content' not in st.session_state:
        st.session_state['raw_extracted_content'] = ""

def import_file_content(uploaded_file, page_range):
    """Processes an uploaded file by saving to temp and extracting content to RAW state."""
    if uploaded_file is None:
        st.error("Please upload a file first.")
        return

    suffix = os.path.splitext(uploaded_file.name)[1] or '.tmp'
    temp_path = os.path.join(tempfile.gettempdir(), next(tempfile._get_candidate_names()) + suffix)

    try:
        with st.spinner(f"Importing and extracting content from **{uploaded_file.name}**..."):
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            
            content = extract_content_with_docling(temp_path, page_range=page_range or None)
            
            if content:
                st.session_state['raw_extracted_content'] = content
                st.session_state['markdown_content'] = "" 
                st.success("✅ Raw content extracted successfully. Ready for AI generation (Step 2).")
            else:
                st.warning("Content extraction resulted in an empty result.")
            
    except Exception as e:
        st.error(f"Failed to extract content: {e}")
        st.exception(e)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def import_from_url(url, page_range):
    """Downloads content from URL, saves to temp, and extracts to RAW state."""
    if not url:
        st.error("Please enter a URL.")
        return

    temp_path = None
    try:
        with st.spinner(f"Downloading and extracting content from **{url}**..."):
            with httpx.Client(follow_redirects=True, timeout=15.0) as client:
                response = client.get(url)
                response.raise_for_status()

                suffix = os.path.splitext(url.split('?')[0])[1] or '.tmp'
                temp_path = os.path.join(tempfile.gettempdir(), next(tempfile._get_candidate_names()) + suffix)
                with open(temp_path, "wb") as temp_file:
                    temp_file.write(response.content)

            content = extract_content_with_docling(temp_path, page_range=page_range or None)
            
            if content:
                st.session_state['raw_extracted_content'] = content
                st.session_state['markdown_content'] = "" 
                st.success("✅ Raw content extracted successfully. Ready for AI generation (Step 2).")
            else:
                st.warning("Content extraction resulted in an empty result.")

    except httpx.RequestError as e:
        st.error(f"Could not fetch content from URL: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred during extraction: {e}")
        st.exception(e)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def generate_slides_content():
    """Orchestrates the LLM generation step."""
    raw_content = st.session_state.get('raw_extracted_content', '')
    if not raw_content or len(raw_content) < 50:
        st.error("Please import content in Step 1 first (minimum 50 characters).")
        return

    with st.spinner("🤖 Generating structured slide content using Gemini..."):
        try:
            structured_markdown = generate_structured_markdown(raw_content)
            
            st.session_state['markdown_content'] = structured_markdown
            
            if "Gemini API Error" in structured_markdown or "General Error" in structured_markdown:
                st.error("AI Generation Failed. Check the content in Step 3 for details.")
            elif "MOCK" in structured_markdown:
                st.warning("⚠️ Using Mock Content. Please insert your key into the `HARDCODED_GEMINI_API_KEY` variable in `pptx_utils.py` for real generation.")
            else:
                st.success("🎉 Structured Markdown generated and loaded into the editor (Step 3).")
                
        except Exception as e:
            st.error(f"AI Generation Failed: {e}")
            st.exception(e)


def main_app_ui():
    
    st.set_page_config(page_title="Presentation Generator", layout="wide")
    st.title("📄 Gemini-Powered Presentation Generator")
    
    if not DOCLING_AVAILABLE:
        st.warning(
            "⚠️ **Content Extraction is Mocked.** The `docling` library or its Tesseract dependency "
            "was not fully available. Extraction results will use mock data."
        )
    
    # --- 1. Extract Raw Document Content ---
    st.header("1. Extract Raw Document Content")
    
    # --- A. Local File Import (Outside Form) ---
    st.subheader("Import from Local File")
    
    col_file_upload, col_file_range = st.columns([3, 1])
    
    with col_file_upload:
        uploaded_file = st.file_uploader(
            "Upload Document (e.g., PDF, DOCX):", 
            type=['pdf', 'docx', 'doc', 'txt'], 
            key="file_uploader_main"
        )
    with col_file_range:
        file_range_input = st.text_input("Page Range:", key="file_range_input_main", help="e.g., 1-5")
    
    # Button to trigger the file import logic
    if st.button("Import Uploaded File", type="primary", key="file_import_button_final"):
        if uploaded_file:
            import_file_content(uploaded_file, file_range_input)
        else:
            st.error("Please upload a file before clicking 'Import Uploaded File'.")

    st.markdown("---")
    
    # --- B. URL Import (Inside Form) ---
    st.subheader("Import from URL")

    with st.form(key='url_import_form'):
        col_url, col_range = st.columns([3, 1])
        with col_url:
            url_input = st.text_input("URL:", key="url_input", help="Enter link to a document.")
        with col_range:
            range_input = st.text_input("Page Range:", key="url_range_input", help="e.g., 1-5")

        submit_url = st.form_submit_button("Import from URL", type="primary")

        if submit_url:
            if url_input:
                import_from_url(url_input, range_input)
            else:
                st.error("Please enter a URL before clicking 'Import from URL'.")
        
    st.markdown("##") 

    # --- 2. LLM Generation Step ---
    st.header("2. Generate Structured Slides from Raw Content")
    
    raw_content_len = len(st.session_state.get('raw_extracted_content', ''))
    
    if HARDCODED_GEMINI_API_KEY != "YOUR_HARDCODED_GEMINI_API_KEY_HERE":
        st.success("🔑 Gemini API Key found in `pptx_utils.py`. Real AI generation is active.")
    else:
        st.warning("⚠️ **API Key MISSING or is the placeholder.** Generation will use mock content.")
    
    if raw_content_len > 0:
        st.info(f"Raw content of **{raw_content_len}** characters is ready for processing.")
        if st.button("🚀 Generate Structured Slides with Gemini", type="secondary", key="generate_ai_content_btn"):
            generate_slides_content()
    else:
        st.info("Import content in Step 1 to enable AI generation.")

    st.markdown("---") 

    # --- 3. Presentation Content (Editable Markdown) ---
    st.header("3. Final Slide Markdown (Editable)")
    st.caption("Review and edit the structured Markdown before final PPTX creation. Use `#` for slide title and `---` to separate slides.")
    
    markdown_content = st.text_area(
        "Edit Content:", 
        st.session_state.get('markdown_content', ''), 
        height=500,
        key="markdown_editor"
    )
    st.session_state['markdown_content'] = markdown_content

    # --- 4. Generate Presentation ---
    st.header("4. Generate Presentation")
    
    if st.button("Generate Final PPTX", type="primary", key="generate_btn_final"):
        content = st.session_state['markdown_content']
        if not content.strip():
            st.error("The slide content editor (Step 3) is empty.")
            return
        
        temp_output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
        output_path = temp_output_file.name
        temp_output_file.close()
        
        try:
            with st.spinner("Creating PowerPoint..."):
                create_presentation_from_markdown(content, output_path)
            
            with open(output_path, "rb") as f:
                pptx_bytes = f.read()

            st.download_button(
                label="✅ Download Presentation",
                data=pptx_bytes,
                file_name="generated_presentation.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                key="download_button_final",
                type="secondary"
            )
            st.balloons()
            st.success("Presentation created successfully!")
            
        except Exception as e:
            st.error(f"Failed to generate presentation: {e}")
            st.exception(e)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

# --- Run App ---
if __name__ == "__main__":
    init_session_state()
    main_app_ui()
