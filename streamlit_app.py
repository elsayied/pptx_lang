# streamlit_app.py
import streamlit as st
import tempfile
import os
import httpx
# Import all backend logic from the separate utility file
from pptx_utils import create_presentation_from_markdown, extract_content_with_docling, DOCLING_AVAILABLE

# --- Streamlit Session State & Logic ---

def init_session_state():
    """Initialize Streamlit session state variables."""
    if 'markdown_content' not in st.session_state:
        st.session_state['markdown_content'] = ""

def import_file_content(uploaded_file, page_range):
    """Processes an uploaded file by saving to temp and extracting content."""
    if uploaded_file is None:
        st.error("Please upload a file first.")
        return

    suffix = os.path.splitext(uploaded_file.name)[1] or '.tmp'
    temp_path = os.path.join(tempfile.gettempdir(), next(tempfile._get_candidate_names()) + suffix)

    try:
        with st.spinner(f"Importing and extracting content from **{uploaded_file.name}**..."):
            # Write the UploadedFile content to the temporary file
            uploaded_file.seek(0) # Rewind buffer
            file_bytes = uploaded_file.read()
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            
            content = extract_content_with_docling(temp_path, page_range=page_range or None)
            
            if content:
                st.session_state['markdown_content'] = content
                st.success("Content extracted and loaded into editor.")
            else:
                st.warning("Content extraction resulted in an empty result.")
            
    except Exception as e:
        st.error(f"Failed to extract content: {e}")
        st.exception(e)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def import_from_url(url, page_range):
    """Downloads content from URL, saves to temp, and extracts."""
    if not url:
        st.error("Please enter a URL.")
        return

    temp_path = None
    try:
        with st.spinner(f"Downloading and extracting content from **{url}**..."):
            # 1. Download
            with httpx.Client(follow_redirects=True, timeout=15.0) as client:
                response = client.get(url)
                response.raise_for_status()

                # 2. Save to temporary file
                suffix = os.path.splitext(url.split('?')[0])[1] or '.tmp'
                temp_path = os.path.join(tempfile.gettempdir(), next(tempfile._get_candidate_names()) + suffix)
                with open(temp_path, "wb") as temp_file:
                    temp_file.write(response.content)

            # 3. Extract content
            content = extract_content_with_docling(temp_path, page_range=page_range or None)
            
            # 4. Update state
            if content:
                st.session_state['markdown_content'] = content
                st.success("Content downloaded, extracted, and loaded into editor.")
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


def main_app_ui():
    """Main Streamlit UI based on gui2.py single-document flow."""
    
    st.set_page_config(page_title="Presentation Generator", layout="wide")
    st.title("📄 Markdown to PowerPoint Generator")
    st.caption("Import document content via file upload or URL, edit the resulting Markdown, and generate a PPTX presentation.")
    
    if not DOCLING_AVAILABLE:
        st.warning(
            "⚠️ **`docling` or Tesseract is missing.** "
            "Content extraction from files/URLs is currently **mocked** to allow testing the PPTX generation flow. "
            "Install required packages for full functionality."
        )
    
    # --- 1. Import Content (Using st.form for grouping) ---
    st.header("1. Import Document Content")
    
    with st.form(key='import_form'):
        
        col_url, col_range = st.columns([3, 1])
        with col_url:
            url_input = st.text_input("URL:", key="url_input", help="Enter the direct link to a document (PDF, DOCX, etc.).")
        with col_range:
            range_input = st.text_input("Page Range:", key="range_input", help="e.g., 1-5, 2,4 (1-indexed)")

        st.markdown("---")
        
        uploaded_file = st.file_uploader(
            "Upload Document (If used, URL input is ignored for this action):", 
            type=['pdf', 'docx', 'doc', 'txt', 'epub', 'html'], 
            key="file_uploader_main"
        )
        
        st.markdown("---")

        col_buttons = st.columns(2)
        
        # Streamlit forms require submit buttons to trigger the action
        submit_url = col_buttons[0].form_submit_button("Import from URL", type="primary")
        submit_file = col_buttons[1].form_submit_button("Import Uploaded File", type="secondary")

        if submit_file:
            if uploaded_file:
                # We need to re-read the uploaded file as form submission consumes the buffer
                import_file_content(uploaded_file, range_input)
            else:
                st.error("Please upload a file before clicking 'Import Uploaded File'.")
        
        if submit_url:
            if url_input:
                import_from_url(url_input, range_input)
            else:
                st.error("Please enter a URL before clicking 'Import from URL'.")
        
    st.markdown("##") 

    # --- 2. Presentation Content (Editable Markdown) ---
    st.header("2. Presentation Content (Editable Markdown)")
    st.caption("Edit the content below. Use Markdown list syntax for bullets and '---' to separate slides.")
    
    markdown_content = st.text_area(
        "Edit Content:", 
        st.session_state.get('markdown_content', ''), 
        height=500,
        key="markdown_editor"
    )
    st.session_state['markdown_content'] = markdown_content

    # --- 3. Generate Presentation ---
    st.header("3. Generate Presentation")
    
    if st.button("Generate Presentation (.pptx)", type="primary", key="generate_btn_final"):
        content = st.session_state['markdown_content']
        if not content.strip():
            st.error("The content editor is empty. Please import or type content.")
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
                type="success"
            )
            st.balloons()
            st.success("Presentation created successfully! Click the download button above.")
            
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
