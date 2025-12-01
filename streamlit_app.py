# streamlit_app.py
import os
import tempfile

import httpx
import streamlit as st

# Import core backend functions
from pptx_utils import (
    DOCLING_AVAILABLE,
    HARDCODED_GEMINI_API_KEY,
    create_presentation_from_markdown,
    extract_content_with_docling,
    generate_audio_overview,
    generate_podcast_script,
    generate_structured_markdown,
)


# --- Session State ---
def init_session_state():
    if "markdown_editor" not in st.session_state:
        st.session_state["markdown_editor"] = ""
    if "raw_extracted_content" not in st.session_state:
        st.session_state["raw_extracted_content"] = ""
    if "podcast_script" not in st.session_state:
        st.session_state["podcast_script"] = []
    if "audio_path" not in st.session_state:
        st.session_state["audio_path"] = ""


# --- Content Import ---
def import_file_content(uploaded_file, page_range):
    if not uploaded_file:
        return
    suffix = os.path.splitext(uploaded_file.name)[1] or ".tmp"
    temp_path = os.path.join(
        tempfile.gettempdir(), next(tempfile._get_candidate_names()) + suffix
    )
    try:
        with st.spinner(f"Extracting {uploaded_file.name}..."):
            uploaded_file.seek(0)
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.read())
            content = extract_content_with_docling(temp_path, page_range=page_range)
            if content:
                st.session_state["raw_extracted_content"] = content
                st.session_state["markdown_editor"] = ""
                st.session_state["audio_path"] = ""
                st.success("✅ Content Extracted")
    except Exception as e:
        st.error(f"Error: {e}")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def import_from_url(url, page_range):
    if not url:
        return
    try:
        with st.spinner(f"Fetching {url}..."):
            with httpx.Client(follow_redirects=True) as client:
                response = client.get(url)
                temp_path = os.path.join(tempfile.gettempdir(), "downloaded_file.tmp")
                with open(temp_path, "wb") as f:
                    f.write(response.content)
            content = extract_content_with_docling(temp_path, page_range=page_range)
            if content:
                st.session_state["raw_extracted_content"] = content
                st.session_state["markdown_editor"] = ""
                st.session_state["audio_path"] = ""
                st.success("✅ Content Extracted")
    except Exception as e:
        st.error(f"Error: {e}")


# --- Generation Logic ---
def generate_slides_content():
    raw = st.session_state.get("raw_extracted_content", "")
    if len(raw) < 50:
        st.error("Content too short.")
        return
    with st.spinner("🤖 Generating Slides (Gemini)..."):
        res = generate_structured_markdown(raw)
        st.session_state["markdown_editor"] = res
        if "API Error" in res:
            st.error("Rate Limit or API Error.")
        else:
            st.success("✅ Slides Generated")


def generate_audio_logic():
    raw = st.session_state.get("raw_extracted_content", "")
    if not raw:
        st.error("No content.")
        return

    with st.spinner("🎧 Generating Script (1 Call)..."):
        script = generate_podcast_script(raw)
        st.session_state["podcast_script"] = script

    with st.spinner("🎙️ Synthesizing Audio (Free)..."):
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        generate_audio_overview(script, temp_audio.name)
        st.session_state["audio_path"] = temp_audio.name
        st.success("✅ Audio Ready")


# --- UI ---
def main_app_ui():
    st.set_page_config(layout="wide", page_title="Gemini Presentation")
    st.title("📄 Gemini-Powered Presentation Generator")

    # 1. Import
    st.header("1. Extract Content")
    col1, col2 = st.columns([3, 1])
    with col1:
        file_up = st.file_uploader("Upload File", type=["pdf", "docx", "txt"])
    if st.button("Import File") and file_up:
        import_file_content(file_up, None)

    with st.form("url_form"):
        url = st.text_input("Or Enter URL")
        if st.form_submit_button("Import URL"):
            import_from_url(url, None)

    # 1.5 Audio
    st.markdown("---")
    st.header("🎧 Audio Overview")
    if len(st.session_state.get("raw_extracted_content", "")) > 0:
        if st.button("Generate Audio Overview", icon="🎙️"):
            generate_audio_logic()
        if st.session_state["audio_path"]:
            st.audio(st.session_state["audio_path"])
            with st.expander("View Script"):
                for l in st.session_state["podcast_script"]:
                    st.write(f"**{l.get('speaker')}**: {l.get('text')}")
    else:
        st.info("Import content first.")

    # 2. Slides
    st.markdown("---")
    st.header("2. Generate Slides")
    if st.button("🚀 Generate Slides"):
        st.warning("⚠️ Wait 20s if you just generated audio (3 RPM Limit).")
        generate_slides_content()

    # 3. Editor
    st.header("3. Edit Markdown")
    st.text_area(
        "Content",
        value=st.session_state.get("markdown_editor", ""),
        height=400,
        key="markdown_editor",
    )

    # 4. Download
    st.header("4. Download PPTX")
    if st.button("Generate PPTX"):
        out = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx").name
        create_presentation_from_markdown(st.session_state["markdown_editor"], out)
        with open(out, "rb") as f:
            st.download_button("Download", f.read(), "presentation.pptx")


if __name__ == "__main__":
    init_session_state()
    main_app_ui()
