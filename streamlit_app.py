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
    generate_podcast_script,    # <--- NEW
    generate_audio_overview,    # <--- NEW
    DOCLING_AVAILABLE,
    HARDCODED_GEMINI_API_KEY
)

# --- Streamlit Session State & Logic ---

def init_session_state():
    """Initialize Streamlit session state variables."""
    if 'markdown_editor' not in st.session_state:
        st.session_state['markdown_editor'] = ""
    if 'raw_extracted_content' not in st.session_state:
        st.session_state['raw_extracted_content'] = ""
    if 'podcast_script' not in st.session_state: # <--- NEW
        st.session_state['podcast_script'] = []
    if 'audio_path' not in st.session_state:     # <--- NEW
        st.session_state['audio_path'] = ""

def import_file_content(uploaded_file, page_range):
    # ... (Keep existing logic exactly as is) ...
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
                st.session_state['markdown_editor'] = "" 
                st.session_state['audio_path'] = "" # Reset audio on new import
                st.success("✅ Raw content extracted successfully.")
            else:
                st.warning("Content extraction resulted in an empty result.")
            
    except Exception as e:
        st.error(f"Failed to extract content: {e}")
    finally:
        if os.path.exists(temp_path): os.unlink(temp_path)

def import_from_url(url, page_range):
    # ... (Keep existing logic exactly as is) ...
    if not url: return
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
                st.session_state['markdown_editor'] = ""
                st.session_state['audio_path'] = "" # Reset audio
                st.success("✅ Raw content extracted successfully.")
            else:
                st.warning("Empty result.")
    except Exception as e:
        st.error(f"Error: {e}")

def generate_slides_content():
    """Orchestrates the LLM generation step for SLIDES."""
    raw_content = st.session_state.get('raw_extracted_content', '')
    if not raw_content or len(raw_content) < 50:
        st.error("Please import content in Step 1 first.")
        return

    with st.spinner("🤖 Generating structured slide content using Gemini..."):
        try:
            structured_markdown = generate_structured_markdown(raw_content)
            st.session_state['markdown_editor'] = structured_markdown
            if "Gemini API Error" in structured_markdown:
                st.error("AI Generation Failed. You may have hit your 3 RPM limit. Please wait 60s.")
            else:
                st.success("🎉 Slides generated.")
        except Exception as e:
            st.error(f"AI Generation Failed: {e}")

def generate_audio_logic():
    """Orchestrates the Audio Overview (1 API Call + EdgeTTS)."""
    raw_content = st.session_state.get('raw_extracted_content', '')
    if not raw_content:
        st.error("No content to process.")
        return

    # Step 1: Generate Script (Consumes 1 Gemini Request)
    with st.spinner("🎧 Generating Deep Dive conversation script (1 API Call)..."):
        script = generate_podcast_script(raw_content)
        st.session_state['podcast_script'] = script
    
    # Step 2: Synthesize Audio (No API Cost)
    with st.spinner("🎙️ Synthesizing voices with EdgeTTS (No API Cost)..."):
        try:
            temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            audio_path = temp_audio.name
            temp_audio.close()
            
            generate_audio_overview(script, audio_path)
            st.session_state['audio_path'] = audio_path
            st.success("Audio Overview Ready!")
        except Exception as e:
            st.error(f"Failed to generate audio: {e}")

def main_app_ui():
    
    st.set_page_config(page_title="Presentation Generator", layout="wide")
    st.title("📄 Gemini-Powered Presentation Generator")
    
    # ... (Step 1 UI - Kept same) ...
    st.header("1. Extract Raw Document Content")
    
    # Local File
    col_file_upload, col_file_range = st.columns([3, 1])
    with col_file_upload:
        uploaded_file = st.file_uploader("Upload Document:", type=['pdf', 'docx', 'txt'], key="file_uploader_main")
    with col_file_range:
        file_range_input = st.text_input("Page Range:", key="file_range_input_main")
    
    if st.button("Import Uploaded File", type="primary"):
        if uploaded_file: import_file_content(uploaded_file, file_range_input)

    # URL
    with st.form(key='url_import_form'):
        col_url, col_range = st.columns([3, 1])
        with col_url: url_input = st.text_input("URL:", key="url_input")
        with col_range: range_input = st.text_input("Page Range:", key="url_range_input")
        if st.form_submit_button("Import from URL", type="primary"):
            if url_input: import_from_url(url_input, range_input)
        
    st.markdown("##") 

    # --- 1.5 Audio Overview (NotebookLM Style) ---
    st.header("🎧 Audio Overview (Deep Dive)")
    st.caption("Generate a podcast-style discussion. Uses **1 API Call** for the script. Audio synthesis is free.")
    
    raw_content_len = len(st.session_state.get('raw_extracted_content', ''))
    
    if raw_content_len > 0:
        col_audio_btn, col_audio_player = st.columns([1, 2])
        
        with col_audio_btn:
            # Separate button to control when API call happens
            if st.button("Generate Audio Overview", icon="🎙️"):
                generate_audio_logic()
                
        with col_audio_player:
            if 'audio_path' in st.session_state and os.path.exists(st.session_state['audio_path']):
                st.audio(st.session_state['audio_path'], format="audio/mp3")
                
                with st.expander("View Podcast Script"):
                    script = st.session_state.get('podcast_script', [])
                    for line in script:
                        speaker = line.get('speaker', 'Unknown')
                        text = line.get('text', '')
                        st.markdown(f"**{speaker}**: {text}")
    else:
        st.info("Import content in Step 1 to enable Audio Overview.")

    st.markdown("---") 

    # --- 2. LLM Generation Step ---
    st.header("2. Generate Structured Slides")
    
    if raw_content_len > 0:
        st.info(f"Raw content of **{raw_content_len}** characters ready.")
        if st.button("🚀 Generate Slides with Gemini", type="secondary"):
             # Warning about the RPM limit
             st.warning("⚠️ You have a 3 RPM limit. If you just generated audio, wait 20 seconds before generating slides.")
             generate_slides_content()
    else:
        st.info("Import content in Step 1 first.")

    st.markdown("---") 

    # --- 3. Editable Markdown ---
    st.header("3. Final Slide Markdown (Editable)")
    st.text_area("Edit Content:", value=st.session_state.get('markdown_editor', ''), height=500, key="markdown_editor")

    # --- 4. Generate PPTX ---
    st.header("4. Generate Presentation")
    if st.button("Generate Final PPTX", type="primary"):
        content = st.session_state['markdown_editor']
        if not content.strip():
            st.error("Editor is empty.")
        else:
            temp_output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
            output_path = temp_output_file.name
            temp_output_file.close()
            try:
                with st.spinner("Creating PowerPoint..."):
                    create_presentation_from_markdown(content, output_path)
                with open(output_path, "rb") as f: pptx_bytes = f.read()
                st.download_button("✅ Download PPTX", data=pptx_bytes, file_name="presentation.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
            finally:
                if os.path.exists(output_path): os.unlink(output_path)

if __name__ == "__main__":
    init_session_state()
    main_app_ui()
