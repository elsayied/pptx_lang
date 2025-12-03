import streamlit as st
from elevenlabs.client import ElevenLabs
import json


def settings_page():
    st.header("Settings")

    st.subheader("API Keys")

    # JSON file uploader
    uploaded_file = st.file_uploader("Upload API Keys from JSON file", type="json")
    if uploaded_file is not None:
        try:
            api_keys = json.load(uploaded_file)
            if "gemini_api_key" in api_keys:
                st.session_state["gemini_api_key"] = api_keys["gemini_api_key"]
            if "elevenlabs_api_key" in api_keys:
                st.session_state["elevenlabs_api_key"] = api_keys["elevenlabs_api_key"]
            st.success("API Keys loaded from file.")
        except json.JSONDecodeError:
            st.error("Invalid JSON file. Please upload a valid JSON file.")
        except Exception as e:
            st.error(f"An error occurred while reading the file: {e}")

    gemini_api_key = st.text_input(
        "Gemini API Key",
        type="password",
        value=st.session_state.get("gemini_api_key", ""),
    )
    if gemini_api_key:
        st.session_state["gemini_api_key"] = gemini_api_key

    st.subheader("TTS Settings")
    tts_engine = st.selectbox(
        "TTS Engine",
        ["Eleven Labs", "Kokoro"],
        index=["Eleven Labs", "Kokoro"].index(
            st.session_state.get("tts_engine", "Eleven Labs")
        ),
    )
    st.session_state["tts_engine"] = tts_engine

    if tts_engine == "Eleven Labs":
        elevenlabs_api_key = st.text_input(
            "Eleven Labs API Key",
            type="password",
            value=st.session_state.get("elevenlabs_api_key", ""),
        )

        if elevenlabs_api_key:
            st.session_state["elevenlabs_api_key"] = elevenlabs_api_key

            try:
                client = ElevenLabs(api_key=elevenlabs_api_key)
                available_voices = client.voices.get_all().voices

                voice_options = [
                    (voice.name, voice.voice_id) for voice in available_voices
                ]
                voice_names = [name for name, _ in voice_options]

                st.subheader("Voice Settings")

                current_mapping = st.session_state.get("voice_mapping", {})
                sascha_current_id = current_mapping.get("Sascha")
                marina_current_id = current_mapping.get("Marina")

                try:
                    sascha_voice_default_ix = [
                        vid for _, vid in voice_options
                    ].index(sascha_current_id)
                except (ValueError, TypeError):
                    sascha_voice_default_ix = 0

                try:
                    marina_voice_default_ix = [
                        vid for _, vid in voice_options
                    ].index(marina_current_id)
                except (ValueError, TypeError):
                    marina_voice_default_ix = 0

                sascha_voice_name = st.selectbox(
                    "Voice for Sascha", voice_names, index=sascha_voice_default_ix
                )
                marina_voice_name = st.selectbox(
                    "Voice for Marina", voice_names, index=marina_voice_default_ix
                )

                if st.button("Save Voice Settings"):
                    sascha_voice_id = next(
                        vid
                        for name, vid in voice_options
                        if name == sascha_voice_name
                    )
                    marina_voice_id = next(
                        vid
                        for name, vid in voice_options
                        if name == marina_voice_name
                    )

                    st.session_state["voice_mapping"] = {
                        "Sascha": sascha_voice_id,
                        "Marina": marina_voice_id,
                    }
                    st.success("Voice settings saved!")

            except Exception as e:
                st.error(
                    f"Failed to fetch voices from Eleven Labs. Check your API key. Error: {e}"
                )
        else:
            st.warning(
                "Please enter your Eleven Labs API key to configure voice settings."
            )

    if "voice_mapping" not in st.session_state:
        st.session_state["voice_mapping"] = {}
    
    st.subheader("Content Extraction Settings")
    ocr_enabled = st.checkbox(
        "Enable OCR for document processing",
        value=st.session_state.get("ocr_enabled", True), # Default to True
        help="If enabled, Optical Character Recognition (OCR) will be used to extract text from images within documents. Turn off for faster processing of text-based PDFs."
    )
    st.session_state["ocr_enabled"] = ocr_enabled
    
    st.subheader("Prompt Settings")
    DEFAULT_PODCAST_PROMPT = '''
You are a podcast producer. Turn the text into a dialogue script between 'Sascha' and 'Marina'.
Output JSON ONLY: [{"speaker": "Sascha", "text": "..."}]

Text:
{text_content}
'''
    podcast_prompt = st.text_area(
        "Audio Overview Prompt",
        value=st.session_state.get("podcast_prompt", DEFAULT_PODCAST_PROMPT),
        height=250,
        help="""
        This is the prompt used to generate the audio overview script. 
        You can customize it, but make sure to keep the {text_content} placeholder.
        The output must be a JSON list of objects, each with a "speaker" and "text" key.
        """
    )
    st.session_state["podcast_prompt"] = podcast_prompt
