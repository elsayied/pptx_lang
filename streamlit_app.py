# streamlit_app.py
import os
import tempfile

import httpx
import streamlit as st

# Import core backend functions
from pptx_utils import (
    DOCLING_AVAILABLE,
    create_presentation_from_markdown,
    extract_content_from_youtube,
    extract_content_with_docling,
    generate_audio_overview,
    generate_podcast_script,
    generate_structured_markdown,
)
from settings_page import settings_page


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
    if "elevenlabs_api_key" not in st.session_state:
        st.session_state["elevenlabs_api_key"] = ""
    if "gemini_api_key" not in st.session_state:
        st.session_state["gemini_api_key"] = ""
    if "voice_mapping" not in st.session_state:
        st.session_state["voice_mapping"] = {"Sascha": "Rachel", "Marina": "Bella"}


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

            if isinstance(content, dict) and "error" in content:
                st.error(f"Failed to extract content: {content['error']}")
                st.session_state["raw_extracted_content"] = ""
            elif content:
                st.session_state["raw_extracted_content"] = content
                st.session_state["markdown_editor"] = ""
                st.session_state["audio_path"] = ""
                st.success("✅ Content Extracted")
            else:
                st.error(
                    "Failed to extract content. The document might be empty or unreadable."
                )
                st.session_state["raw_extracted_content"] = ""

    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
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
                response.raise_for_status()
                temp_path = os.path.join(tempfile.gettempdir(), "downloaded_file.tmp")
                with open(temp_path, "wb") as f:
                    f.write(response.content)

            content = extract_content_with_docling(temp_path, page_range=page_range)

            if isinstance(content, dict) and "error" in content:
                st.error(f"Failed to extract content: {content['error']}")
                st.session_state["raw_extracted_content"] = ""
            elif content:
                st.session_state["raw_extracted_content"] = content
                st.session_state["markdown_editor"] = ""
                st.session_state["audio_path"] = ""
                st.success("✅ Content Extracted")
            else:
                st.error(
                    "Failed to extract content. The document might be empty or unreadable."
                )
                st.session_state["raw_extracted_content"] = ""

    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
    finally:
        if "temp_path" in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)


# --- Generation Logic ---
def generate_slides_content():
    raw = st.session_state.get("raw_extracted_content", "")
    api_key = st.session_state.get("gemini_api_key")
    if not api_key:
        st.error("Gemini API key is not set. Please set it in the Settings page.")
        return
    if len(raw) < 50:
        st.error("Content too short.")
        return
    with st.spinner("🤖 Generating Slides (Gemini)..."):
        res = generate_structured_markdown(raw, api_key)
        st.session_state["markdown_editor"] = res
        if "API Error" in res:
            st.error("Rate Limit or API Error.")
        else:
            st.success("✅ Slides Generated")


def generate_audio_logic():
    raw = st.session_state.get("raw_extracted_content", "")
    api_key = st.session_state.get("elevenlabs_api_key")
    voice_mapping = st.session_state.get("voice_mapping")

    if not raw:
        st.error("No content.")
        return
    if not api_key:
        st.error("Eleven Labs API key is not set. Please set it in the Settings page.")
        return

    gemini_api_key = st.session_state.get("gemini_api_key")
    if not gemini_api_key:
        st.error("Gemini API key is not set. Please set it in the Settings page.")
        return
    print(f"{gemini_api_key = }")
    with st.spinner("🎧 Generating Script (1 Call)..."):
        script = generate_podcast_script(raw, gemini_api_key)
        st.session_state["podcast_script"] = script
        from pprint import pprint

        pprint(f"{script = }")
    # Check for errors from the script generation
    if script and script[0].get("speaker") == "Error":
        st.error(script[0].get("text"))
        return

    with st.spinner("🎙️ Synthesizing Audio..."):
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        generate_audio_overview(script, temp_audio.name, api_key, voice_mapping)
        st.session_state["audio_path"] = temp_audio.name
        st.success("✅ Audio Ready")


# --- UI ---
def main_app_ui():
    st.set_page_config(layout="wide", page_title="Gemini Presentation")
    st.title("📄 Gemini-Powered Presentation Generator")

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["App", "Settings"])

    if page == "App":
        app_page()
    elif page == "Settings":
        settings_page()


def app_page():
    # 1. Import
    st.header("1. Extract Content")
    col1, col2 = st.columns([3, 1])
    with col1:
        file_up = st.file_uploader("Upload File", type=["pdf", "docx", "txt"])
    with col2:
        page_range_input = st.text_input("Page range (e.g., 1-3, 5)")

    if st.button("Import File") and file_up:
        import_file_content(file_up, page_range_input)

    with st.form("url_form"):
        url = st.text_input("Or Enter URL")
        if st.form_submit_button("Import URL"):
            import_from_url(url, page_range_input)

    with st.form("youtube_form"):
        youtube_url = st.text_input("Or Enter YouTube URL")
        start_time = st.text_input("Start time (e.g., 0:00)")
        end_time = st.text_input("End time (e.g., 1:30)")
        if st.form_submit_button("Import from YouTube"):
            if youtube_url:
                with st.spinner("Fetching YouTube transcript..."):
                    content = extract_content_from_youtube(
                        youtube_url, start_time, end_time
                    )
                    if content:
                        st.session_state["raw_extracted_content"] = content
                        st.session_state["markdown_editor"] = ""
                        st.session_state["audio_path"] = ""
                        st.success("✅ Content Extracted from YouTube")
                    else:
                        st.error("Could not extract content from YouTube.")
            else:
                st.error("Please enter a YouTube URL.")

    # 1.5 Audio
    st.markdown("---")
    st.header("🎧 Audio Overview")
    if len(st.session_state.get("raw_extracted_content", "")) > 0:
        if st.button("Generate Audio Overview", icon="🎙️"):
            generate_audio_logic()
        if st.session_state["audio_path"]:
            st.audio(st.session_state["audio_path"])
            with open(st.session_state["audio_path"], "rb") as f:
                st.download_button("Download audio", f.read(), "audio_overview.mp3")
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
