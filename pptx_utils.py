import asyncio
import json
import logging
import os
import re
from pprint import pprint
from typing import Dict, List

import nest_asyncio
from google import genai
from pptx import Presentation
from pptx.util import Inches, Pt

# Apply nest_asyncio to allow nested event loops (crucial for Streamlit + edge-tts)
nest_asyncio.apply()

# --- HARDCODED API KEY (SECURITY WARNING: DO NOT USE IN PUBLIC REPOSITORIES) ---
# ⚠️ REPLACE THE PLACEHOLDER BELOW WITH YOUR ACTUAL GEMINI API KEY ⚠️
HARDCODED_GEMINI_API_KEY = "AIzaSyA4YsTnbNjl2gKn20EqPa-9nom9yymEwd0"
# ---

logging.basicConfig(level=logging.INFO)

# --- Docling Availability Check ---
try:
    from docling.document_converter import DocumentConverter

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logging.warning("Docling not available. Mock content may be used.")

# --- PROMPTS ---

GEMINI_LECTURE_PROMPT = """
You are a master presentation creator. Transform the following text into a presentation in Markdown.
Output ONLY the Markdown.

Syntax:
1. Slides separated by `---`
2. Title prefixed with `#`
3. `layout: title_content` (or others) on first line.
4. `::: notes` for speaker notes.
5. `::: column` for columns.
6. Images: `![alt](path)` or `![alt](gemini:prompt)`.

Text to transform:
"""

GEMINI_PODCAST_PROMPT = """
You are a podcast producer. Turn the text into a dialogue script between 'Sascha' and 'Marina'.
Output JSON ONLY: [{"speaker": "Sascha", "text": "..."}]

Text:
{text_content}
"""

# --- HELPER FUNCTIONS ---


def generate_image(prompt: str, output_path: str):
    """Generates an image using Gemini."""
    try:
        client = genai.Client(api_key=HARDCODED_GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
        )
        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()
                image.save(output_path)
                return output_path
    except Exception as e:
        logging.error(f"Error generating image: {e}")
        return None


def create_table_from_markdown(text: str) -> List[List[str]]:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return []
    lines = [l for l in lines if not re.match(r"^\s*\|?.*--.*\|?\s*$", l)]
    table_data = []
    for row_str in lines:
        if row_str.startswith("|"):
            row_str = row_str[1:]
        if row_str.endswith("|"):
            row_str = row_str[:-1]
        cells = [cell.strip() for cell in row_str.split("|")]
        table_data.append(cells)
    return table_data


def add_formatted_text_runs(paragraph, text, bold=False, italic=False, underline=False):
    parts = re.split(
        r"(\*\*\*[\s\S]+?\*\*\*|\*\*[\s\S]+?\*\*|\*[\s\S]+?\*|__[\s\S]+?__)", text
    )
    if len(parts) == 1:
        if text:
            run = paragraph.add_run()
            run.text = text
            font = run.font
            font.bold = bold
            font.italic = italic
            font.underline = underline
        return
    for part in parts:
        if not part:
            continue
        if part.startswith("***") and part.endswith("***"):
            add_formatted_text_runs(
                paragraph, part[3:-3], bold=True, italic=True, underline=underline
            )
        elif part.startswith("**") and part.endswith("**"):
            add_formatted_text_runs(
                paragraph, part[2:-2], bold=True, italic=italic, underline=underline
            )
        elif part.startswith("*") and part.endswith("*"):
            add_formatted_text_runs(
                paragraph, part[1:-1], bold=bold, italic=True, underline=underline
            )
        elif part.startswith("__") and part.endswith("__"):
            add_formatted_text_runs(
                paragraph, part[2:-2], bold=bold, italic=italic, underline=True
            )
        else:
            add_formatted_text_runs(
                paragraph, part, bold=bold, italic=italic, underline=underline
            )


def add_bullet_points_from_markdown(text_frame, points: str):
    if not text_frame.text.strip():
        text_frame.text = ""

    def get_level_and_text(line: str) -> tuple[int, str]:
        stripped_line = line.lstrip()
        text = stripped_line
        if text.startswith(("-", "*", "+")) and text[1:2] in (" ", ""):
            text = text[1:].lstrip()
        indent = len(line) - len(line.lstrip())
        return indent // 2, text

    lines = [line for line in points.split("\n") if line.strip()]
    for line in lines:
        level, text = get_level_and_text(line)
        p = text_frame.add_paragraph()
        add_formatted_text_runs(p, text)
        p.level = min(level, 8)


def parse_markdown_to_slides(content: str) -> List[Dict]:
    slides = []
    slide_contents = re.split(r"\n---\n", content)
    for slide_content in slide_contents:
        if not slide_content.strip():
            continue
        lines = slide_content.strip().split("\n")
        slide_data = {
            "layout": "title_content",
            "title": None,
            "blocks": [],
            "columns": [],
            "notes": "",
        }
        if lines and lines[0].startswith("layout:"):
            slide_data["layout"] = lines[0].split(":", 1)[1].strip()
            lines.pop(0)
        if lines and lines[0].startswith("# "):
            slide_data["title"] = lines[0][2:].strip()
            lines.pop(0)

        line_idx = 0
        in_notes = False
        in_col = False
        while line_idx < len(lines):
            line = lines[line_idx]
            stripped = line.strip()
            if stripped.lower().startswith("::: notes"):
                in_notes = True
                line_idx += 1
                continue
            if stripped.lower().startswith("::: column"):
                in_col = True
                if not slide_data["columns"] and slide_data["blocks"]:
                    slide_data["columns"].append(slide_data["blocks"])
                    slide_data["blocks"] = []
                slide_data["columns"].append([])
                line_idx += 1
                continue
            if stripped == ":::":
                in_notes = False
                in_col = False
                line_idx += 1
                continue
            if in_notes:
                slide_data["notes"] += line + "\n"
                line_idx += 1
                continue

            curr = (
                slide_data["columns"][-1]
                if in_col and slide_data["columns"]
                else slide_data["blocks"]
            )
            if not stripped:
                line_idx += 1
                continue

            if stripped.startswith("```"):
                code = []
                lang = stripped[3:]
                line_idx += 1
                while line_idx < len(lines) and not lines[line_idx].strip().startswith(
                    "```"
                ):
                    code.append(lines[line_idx])
                    line_idx += 1
                curr.append(
                    {"type": "code", "language": lang, "content": "\n".join(code)}
                )
                line_idx += 1
                continue

            if re.match(r"^\s*!\[.*\]\(.*\)\s*$", line):
                curr.append({"type": "image", "content": line.strip()})
                line_idx += 1
                continue

            if line.lstrip().startswith(("-", "*", "+")):
                bullets = []
                start_indent = len(line) - len(line.lstrip())
                while line_idx < len(lines):
                    curr_l = lines[line_idx]
                    curr_s = curr_l.strip()
                    if curr_s.startswith((":::", "```")):
                        break
                    if curr_s and (len(curr_l) - len(curr_l.lstrip()) < start_indent):
                        break
                    bullets.append(curr_l)
                    line_idx += 1
                curr.append({"type": "bullet", "content": "\n".join(bullets)})
                continue

            text_lines = []
            while line_idx < len(lines):
                curr_l = lines[line_idx]
                curr_s = curr_l.strip()
                if (
                    not curr_s
                    or curr_l.lstrip().startswith(("-", "*", "+"))
                    or re.match(r"^\s*!\[.*\]\(.*\)\s*$", curr_l)
                    or curr_s.startswith(("```", ":::"))
                ):
                    break
                text_lines.append(curr_l)
                line_idx += 1
            if text_lines:
                curr.append({"type": "text", "content": "\n".join(text_lines)})
        slides.append(slide_data)
    return slides


def create_presentation_from_markdown(
    content: str, output_path: str = "output.pptx"
) -> str:
    prs = Presentation()
    layout_map = {
        "title_slide": prs.slide_layouts[0],
        "title_content": prs.slide_layouts[1],
        "section_header": prs.slide_layouts[2],
        "two_content": prs.slide_layouts[3],
        "comparison": prs.slide_layouts[3],
        "title_only": prs.slide_layouts[5],
        "blank": prs.slide_layouts[6],
        "picture_and_caption": prs.slide_layouts[8],
    }
    slides_data = parse_markdown_to_slides(content)

    for slide_data in slides_data:
        layout = layout_map.get(slide_data["layout"], layout_map["title_content"])
        slide = prs.slides.add_slide(layout)
        if slide_data["title"] and slide.shapes.title:
            slide.shapes.title.text = slide_data["title"]
        if slide_data["notes"]:
            slide.notes_slide.notes_text_frame.text = slide_data["notes"]

        body = next(
            (
                s
                for s in slide.placeholders
                if s.placeholder_format.idx != 0 and s.has_text_frame
            ),
            None,
        )
        blocks = [b for b in slide_data["blocks"] if b["type"] != "image"]
        if body and blocks:
            tf = body.text_frame
            tf.clear()
            for b in blocks:
                if b["type"] == "text":
                    add_formatted_text_runs(tf.add_paragraph(), b["content"])
                elif b["type"] == "bullet":
                    add_bullet_points_from_markdown(tf, b["content"])
                elif b["type"] == "code":
                    p = tf.add_paragraph()
                    r = p.add_run()
                    r.text = b["content"]
                    r.font.name = "Courier New"
                    r.font.size = Pt(10)

    prs.save(output_path)
    return output_path


# --- CORE FUNCTIONS ---


def generate_structured_markdown(text: str) -> str:
    """Generates slides markdown using Gemini."""
    client = genai.Client(api_key=HARDCODED_GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=GEMINI_LECTURE_PROMPT + text,
        )
        return response.text
    except Exception as e:
        return f"Gemini API Error: {e}"


def generate_podcast_script(raw_text: str) -> List[Dict]:
    """Generates script (1 API Call) with robust cleanup."""
    client = genai.Client(api_key=HARDCODED_GEMINI_API_KEY)
    truncated_text = raw_text[:30000]
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=GEMINI_PODCAST_PROMPT.format(text_content=truncated_text),
            config={"response_mime_type": "application/json"},
        )

        # --- FIX: Clean Response Text ---
        text_resp = response.text.strip()
        # Remove markdown code blocks if present
        if text_resp.startswith("```"):
            text_resp = re.sub(
                r"^```(json)?|```$", "", text_resp, flags=re.MULTILINE
            ).strip()

        script = json.loads(text_resp)

        # Ensure it's a list
        if isinstance(script, dict):
            script = [script]

        return script
    except Exception as e:
        logging.error(f"Script Error: {e}")
        # Return a safe fallback that works with audio generation
        return [
            {"speaker": "Sascha", "text": "I am having trouble reading this document."},
            {"speaker": "Marina", "text": "Let's try processing it again."},
        ]


async def _synthesize_audio_chunk(text, voice, output_filename):
    import edge_tts

    # --- FIX: Clean text to avoid TTS errors ---
    # Remove asterisks, hashtags, or excessive newlines which might confuse the TTS
    clean_text = re.sub(r"[*#_`]", "", text).strip()

    # If text is empty or meaningless, skip it
    if not clean_text or not any(c.isalnum() for c in clean_text):
        logging.warning(f"Skipping empty/invalid text chunk: '{text}'")
        return

    communicate = edge_tts.Communicate(clean_text, voice)
    await communicate.save(output_filename)


def generate_audio_overview(script: List[Dict], output_path: str):
    import shutil

    temp_dir = "temp_audio_chunks"
    os.makedirs(temp_dir, exist_ok=True)
    chunk_files = []

    try:
        loop = asyncio.get_event_loop()
        for i, line in enumerate(script):
            text = line.get("text", "")
            if not text:
                continue

            # Robust voice selection
            speaker_name = line.get("speaker", "Sascha")
            voice = (
                "en-US-GuyNeural" if speaker_name == "Sascha" else "en-US-JennyNeural"
            )

            fname = os.path.join(temp_dir, f"chunk_{i:03d}.mp3")

            try:
                loop.run_until_complete(_synthesize_audio_chunk(text, voice, fname))
                if os.path.exists(fname):
                    chunk_files.append(fname)
            except Exception as e:
                logging.error(f"Error generating chunk {i}: {e}")
                continue

        if chunk_files:
            with open(output_path, "wb") as outfile:
                for f in chunk_files:
                    with open(f, "rb") as infile:
                        shutil.copyfileobj(infile, outfile)
        else:
            logging.error("No audio chunks generated.")

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def extract_content_with_docling(
    file_path: str, enabled_ocr=True, page_range: str = None
):
    """
    Extracts content from various file types using the docling library.

    Args:
        file_path (str): The path to the file to extract content from.
        page_range (str): Optional page range (e.g., "1-5", "2,4").

    Returns:
        Dict: A dictionary containing the extracted content.
    """
    suffix = file_path.split(".")[-1]
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
            TesseractCliOcrOptions,
            TesseractOcrOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        # Set lang=["auto"] with a tesseract OCR engine: TesseractOcrOptions, TesseractCliOcrOptions
        # ocr_options = TesseractOcrOptions(lang=["auto"])

        ocr_options = TesseractCliOcrOptions(lang=["eng"])

        pipeline_options = PdfPipelineOptions(
            do_ocr=enabled_ocr, do_table_structure=True, ocr_options=ocr_options
        )

        doc_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )

        doc = doc_converter.convert(file_path).document

        # Apply page range if provided
        if page_range:
            pages = []
            for part in page_range.split(","):
                if "-" in part:
                    start, end = map(int, part.split("-"))
                    pages.extend(range(start - 1, end))  # 0-indexed
                else:
                    pages.append(int(part) - 1)  # 0-indexed

            # Filter pages
            filtered_content = []
            for i, page in enumerate(doc.pages):
                if i in pages:
                    filtered_content.append(page.export_to_markdown())
            return "\n".join(filtered_content)
        else:
            pprint(doc.export_to_markdown())
            return doc.export_to_markdown()

    except Exception as e:
        print(f"Error extracting content with docling from {file_path}: {e}")
        return {"error": str(e)}


def sleep_min(seconds=60):
    import time

    logging.info(f"sleeping for {seconds}")
    time.sleep(seconds)
