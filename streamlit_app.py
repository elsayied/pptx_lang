# streamlit_app.py
import json
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
    load_api_keys()
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


def load_api_keys():
    if os.path.exists("api_keys.json"):
        with open("api_keys.json", "r") as f:
            try:
                api_keys = json.load(f)
                if "gemini_api_key" in api_keys:
                    st.session_state["gemini_api_key"] = api_keys["gemini_api_key"]
                if "elevenlabs_api_key" in api_keys:
                    st.session_state["elevenlabs_api_key"] = api_keys[
                        "elevenlabs_api_key"
                    ]
            except json.JSONDecodeError:
                pass  # Ignore if the file is not a valid JSON


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
            ocr_enabled = st.session_state.get("ocr_enabled", True) # Get OCR setting
            content = extract_content_with_docling(temp_path, page_range=page_range, enabled_ocr=ocr_enabled)

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

            ocr_enabled = st.session_state.get("ocr_enabled", True) # Get OCR setting
            content = extract_content_with_docling(temp_path, page_range=page_range, enabled_ocr=ocr_enabled)

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
    elevenlabs_api_key = st.session_state.get("elevenlabs_api_key")
    voice_mapping = st.session_state.get("voice_mapping")
    tts_engine = st.session_state.get("tts_engine", "Eleven Labs")
    podcast_prompt = st.session_state.get("podcast_prompt")

    if not raw:
        st.error("No content.")
        return

    gemini_api_key = st.session_state.get("gemini_api_key")
    if not gemini_api_key:
        st.error("Gemini API key is not set. Please set it in the Settings page.")
        return

    with st.spinner("🎧 Generating Script (1 Call)..."):
        script = generate_podcast_script(raw, gemini_api_key, prompt=podcast_prompt)
        st.session_state["podcast_script"] = script

    if script and script[0].get("speaker") == "Error":
        st.error(script[0].get("text"))
        return

    with st.spinner("🎙️ Synthesizing Audio..."):
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        success = False

        if tts_engine == "Eleven Labs":
            if not elevenlabs_api_key:
                st.error(
                    "Eleven Labs API key is not set. Please set it in the Settings page."
                )
                return

            result = generate_audio_overview(
                script, temp_audio.name, elevenlabs_api_key, voice_mapping
            )

            if result is True:
                success = True
            elif result == "credit_error":
                st.warning("Eleven Labs credit issue. Falling back to Kokoro TTS.")
                try:
                    from kokoro_utils import (
                        KOKORO_AVAILABLE,
                        generate_audio_overview_kokoro,
                    )

                    if not KOKORO_AVAILABLE:
                        st.error(
                            "Kokoro TTS is not installed. Cannot fallback for audio generation."
                        )
                        return
                    success = generate_audio_overview_kokoro(script, temp_audio.name)
                except ImportError:
                    st.error(
                        "kokoro_utils.py not found. Cannot fallback for audio generation."
                    )
                    return

        elif tts_engine == "Kokoro":
            try:
                from kokoro_utils import (
                    KOKORO_AVAILABLE,
                    generate_audio_overview_kokoro,
                )

                if not KOKORO_AVAILABLE:
                    st.error(
                        "Kokoro TTS is not installed. Please install it to use this feature."
                    )
                    return
                success = generate_audio_overview_kokoro(script, temp_audio.name)
            except ImportError:
                st.error(
                    "kokoro_utils.py not found. Cannot use Kokoro for audio generation."
                )
                return

        if success:
            st.session_state["audio_path"] = temp_audio.name
            st.success("✅ Audio Ready")
        else:
            st.error("Failed to generate audio.")


# --- UI ---
def main_app_ui():
    st.set_page_config(layout="wide", page_title="Gemini Presentation")
    st.title("📄 Gemini-Powered Presentation Generator")

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Create Presentation", "App Settings"])

    if page == "Create Presentation":
        app_page()
    elif page == "App Settings":
        settings_page()


def app_page():
    # 1. Import
    st.header("1. Get Your Content Ready")
    st.markdown(
        "Upload a document (PDF, Word, or text file) or provide a URL to a webpage or YouTube video. This is the first step to create your presentation!"
    )
    col1, col2 = st.columns([3, 1])
    with col1:
        file_up = st.file_uploader(
            "Upload a document (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"]
        )
    with col2:
        page_range_input = st.text_input(
            "Which pages? (e.g., '1-3' or '5')",
            help="Specify a range like '1-3' for pages 1 to 3, or '5' for just page 5. Leave blank for all pages.",
        )

    if st.button("Load from File") and file_up:
        import_file_content(file_up, page_range_input)

    with st.form("url_form"):
        url = st.text_input("Or, paste a Web Page Link here")
        if st.form_submit_button("Load from Web Link"):
            import_from_url(url, page_range_input)

    with st.form("youtube_form"):
        youtube_url = st.text_input("Or, paste a YouTube Video Link here")
        start_time = st.text_input(
            "Start time (e.g., 0:00)",
            help="Optional: Start extracting content from this point in the video.",
        )
        end_time = st.text_input(
            "End time (e.g., 1:30)",
            help="Optional: Stop extracting content at this point in the video.",
        )
        if st.form_submit_button("Load from YouTube Video"):
            if youtube_url:
                with st.spinner("Grabbing the video transcript..."):
                    content = extract_content_from_youtube(
                        youtube_url, start_time, end_time
                    )
                    if content:
                        st.session_state["raw_extracted_content"] = content
                        st.session_state["markdown_editor"] = ""
                        st.session_state["audio_path"] = ""
                        st.success("✅ Content pulled from YouTube!")
                    else:
                        st.error(
                            "Couldn't get content from YouTube. Please check the link."
                        )
            else:
                st.error("Please enter a YouTube video link.")

    # 2. Audio
    st.markdown("---")
    st.header("2. Create Audio Summary (Optional)")
    st.markdown(
        "Want an audio overview of your content? Our AI can generate a podcast-style summary!"
    )
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
        st.info(
            "Ready to hear a summary? First, get your content using the options above (Step 1)."
        )

    # 3. Slides
    st.markdown("---")
    st.header("3. Generate Your Presentation Slides")
    st.markdown(
        "Click below to magically turn your extracted content into a structured presentation outline!"
    )
    if st.button("🚀 Generate Slides"):
        st.warning(
            "Just generated audio? Please wait a moment (around 20 seconds) before generating slides to avoid overloading the system."
        )
        generate_slides_content()

    # 4. Editor
    st.header("4. Review and Edit Your Slides")
    st.markdown(
        "Here's your presentation outline. Feel free to make any changes or corrections directly in this editor!"
    )
    st.text_area(
        "Slide Content (Markdown)",
        value=st.session_state.get("markdown_editor", ""),
        height=400,
        key="markdown_editor",
    )

    # 5. Download
    st.header("5. Get Your Presentation File!")
    st.markdown(
        "All done! Click the button below to download your generated presentation as a PowerPoint (.pptx) file."
    )
    if st.button("Generate PPTX"):
        out = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx").name
        create_presentation_from_markdown(st.session_state["markdown_editor"], out)
        with open(out, "rb") as f:
            st.download_button("Download", f.read(), "presentation.pptx")


if __name__ == "__main__":
    init_session_state()
    main_app_ui()
