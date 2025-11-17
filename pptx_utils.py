from pptx import Presentation
from pptx.util import Inches
from typing import List, Dict
from pprint import pprint
import re
from google import genai
from docling.document_converter import DocumentConverter

GEMINI_LECTURE_PROMPT = '''
You are an expert instructional designer and content synthesizer. Your task is to take the provided lecture text and convert it into a structured JSON object representing a slide presentation.Your output MUST be a single, valid JSON object and nothing else.Carefully analyze the text to identify logical sections, titles, main points, sub-points, comparisons, and data tables. Create a new slide object for each distinct topic or section.Use the following JSON schema:{"slides": [{"title": "string","type": "content_slide" | "comparison_slide" | "table_slide" | "title_slide","content": ["string"],"leftContent": ["string"] (Only for 'comparison_slide'),"rightContent": ["string"] (Only for 'comparison_slide'),"table": {"headers": ["string"],"rows": [["string"]]} (Only for 'table_slide')}]}Here are the rules for each slide type:"title_slide": Use this for the main presentation title. The "title" property should be the presentation title, and the "content" array can contain a subtitle or author."content_slide": This is the default slide.title: The slide's title.content: An array of strings. Each string is a line of text.Crucially, preserve indentation for bullet points in the strings. For example: "- Main Point", "  - Sub-point"."comparison_slide": Use this when the text is comparing two items.title: The title of the comparison.leftContent: An array of strings for the left side of the comparison.rightContent: An array of strings for the right side of the comparison."table_slide": Use this when the text contains structured data that belongs in a table.title: The title for the table.table: An object containing headers (an array of strings) and rows (an array of arrays of strings).Here is the lecture text you need to convert:\n'''
def create_table_from_markdown(text: str) -> List[List[str]]:
    """Convert Markdown table to table data."""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return []
    
    # Filter out separator line
    lines = [l for l in lines if not re.match(r'^\s*\|?.*--.*\|?\s*$', l)]
    
    table_data = []
    for row_str in lines:
        if row_str.startswith('|'): row_str = row_str[1:]
        if row_str.endswith('|'): row_str = row_str[:-1]
        
        cells = [cell.strip() for cell in row_str.split('|')]
        table_data.append(cells)
        
    return table_data

def add_bullet_points_from_markdown(text_frame, points: str):
    """Add bullet points to a text frame from Markdown list."""
    if not text_frame.text.strip():
        text_frame.text = ""

    def get_level_and_text(line: str) -> tuple[int, str]:
        """Determine level and clean text from a Markdown list item."""
        stripped_line = line.lstrip()
        text = stripped_line
        
        if text.startswith(('-', '*', '+')) and text[1:2] in (' ', ''):
            text = text[1:].lstrip()

        indent = len(line) - len(line.lstrip())
        level = indent // 2
        return level, text

    lines = [line for line in points.split('\n') if line.strip()]
    if not lines:
        return

    for line in lines:
        level, text = get_level_and_text(line)
        p = text_frame.add_paragraph()
        p.text = text
        p.level = min(level, 8)

def parse_markdown_to_slides(content: str) -> List[Dict]:
    """Parses markdown-like text into a list of slide definitions."""
    slides = []
    slide_contents = re.split(r'\n---\n', content)

    for slide_content in slide_contents:
        if not slide_content.strip():
            continue

        lines = slide_content.strip().split('\n')
        
        slide_data = {
            'layout': 'title_content',
            'title': None,
            'blocks': []
        }

        if lines and lines[0].startswith('layout:'):
            slide_data['layout'] = lines[0].split(':', 1)[1].strip()
            lines.pop(0)

        if lines and lines[0].startswith('# '):
            slide_data['title'] = lines[0][2:].strip()
            lines.pop(0)

        line_idx = 0
        while line_idx < len(lines):
            line = lines[line_idx]

            if not line.strip():
                line_idx += 1
                continue

            if line.lstrip().startswith(('-', '*', '+')):
                bullet_lines = []
                start_indent = len(line) - len(line.lstrip())
                while line_idx < len(lines) and (not lines[line_idx].strip() or (len(lines[line_idx]) - len(lines[line_idx].lstrip()) >= start_indent)):
                    bullet_lines.append(lines[line_idx])
                    line_idx += 1
                slide_data['blocks'].append({'type': 'bullet', 'content': '\n'.join(bullet_lines)})
                continue

            is_table = False
            if '|' in line:
                if (line_idx + 1 < len(lines)) and re.match(r'^\s*\|?.*--.*\|?\s*$', lines[line_idx+1]):
                    is_table = True
            
            if is_table:
                table_lines = []
                while line_idx < len(lines) and '|' in lines[line_idx]:
                    table_lines.append(lines[line_idx])
                    line_idx += 1
                slide_data['blocks'].append({'type': 'table', 'content': '\n'.join(table_lines)})
                continue

            text_lines = []
            while line_idx < len(lines):
                current_line = lines[line_idx]
                if not current_line.strip() or current_line.lstrip().startswith(('-', '*', '+')):
                    break
                if '|' in current_line and (line_idx + 1 < len(lines)) and re.match(r'^\s*\|?.*--.*\|?\s*$', lines[line_idx+1]):
                    break
                text_lines.append(current_line)
                line_idx += 1
            
            if text_lines:
                slide_data['blocks'].append({'type': 'text', 'content': '\n'.join(text_lines)})
            
        slides.append(slide_data)
    return slides

def create_presentation_from_markdown(content: str, output_path: str = 'output.pptx') -> str:
    """
    Create a PowerPoint presentation from Markdown-structured text.
    """
    prs = Presentation()
    
    layout_map = {
        'title_slide': prs.slide_layouts[0],
        'title_content': prs.slide_layouts[1],
        'section_header': prs.slide_layouts[2],
        'two_content': prs.slide_layouts[3],
        'comparison': prs.slide_layouts[4],
        'title_only': prs.slide_layouts[5],
        'blank': prs.slide_layouts[6],
    }

    slides_data = parse_markdown_to_slides(content)

    for slide_data in slides_data:
        layout_name = slide_data['layout']
        slide_layout = layout_map.get(layout_name, layout_map['title_content'])
        
        current_slide = prs.slides.add_slide(slide_layout)

        if slide_data['title']:
            if current_slide.shapes.title:
                current_slide.shapes.title.text = slide_data['title']

        if layout_name in ['comparison', 'two_content']:
            content_placeholders = [p for p in current_slide.placeholders if p.placeholder_format.idx > 0 and p.has_text_frame]
            if len(content_placeholders) >= 2:
                left_ph, right_ph = content_placeholders[0], content_placeholders[1]
                
                text_block_content = ""
                for block in slide_data['blocks']:
                    if block['type'] == 'text':
                        text_block_content = block['content']
                        break
                
                left_text, right_text = text_block_content.split('|||', 1) if '|||' in text_block_content else (text_block_content, "")
                left_ph.text_frame.text = left_text.strip()
                right_ph.text_frame.text = right_text.strip()
        else:
            body_shape = next((shape for shape in current_slide.placeholders if shape.placeholder_format.idx != 0 and shape.has_text_frame), None)
            
            if body_shape:
                tf = body_shape.text_frame
                tf.clear()

                for block in slide_data['blocks']:
                    if block['type'] == 'text':
                        p = tf.add_paragraph()
                        p.text = block['content']
                    elif block['type'] == 'bullet':
                        add_bullet_points_from_markdown(tf, block['content'])
                    elif block['type'] == 'table':
                        table_data = create_table_from_markdown(block['content'])
                        if not table_data: continue
                        
                        rows, cols = len(table_data), len(table_data[0])
                        table_width = Inches(8.0)
                        table_height = Inches(0.4 * (rows + 1))
                        left = (prs.slide_width - table_width) / 2
                        top = Inches(2.5)
                        
                        table_shape = current_slide.shapes.add_table(rows, cols, left, top, table_width, table_height)
                        table = table_shape.table

                        for r_idx, row_data in enumerate(table_data):
                            for c_idx, cell_text in enumerate(row_data):
                                if c_idx < cols:
                                    table.cell(r_idx, c_idx).text = cell_text
    
    prs.save(output_path)
    return output_path

def extract_content_to_markdown(file_path: str):
    from markitdown import MarkItDown
    suffix = file_path.split('.')[-1]
    
    
    #client = genai.Client(api_key='AIzaSyA4YsTnbNjl2gKn20EqPa-9nom9yymEwd0')
    
    # Initialize MarkItDown
    md = MarkItDown()

    # Convert a file (e.g., a PDF)
    result = md.convert(file_path)
    # closing the socket
    #client.close()
    pprint(result.markdown)
    return result.markdown
def generate_gemini_response(text: str, model: str = 'gemini-2.5-pro'):
    client = genai.Client(api_key='AIzaSyA4YsTnbNjl2gKn20EqPa-9nom9yymEwd0')
    response = client.models.generate_content(model=model, 
                                              contents=GEMINI_LECTURE_PROMPT + text,)
    
    pprint(response)
    return response.text
# to delete
def extract_content_with_docling(file_path: str, page_range: str = None) :
    """
    Extracts content from various file types using the docling library.

    Args:
        file_path (str): The path to the file to extract content from.
        page_range (str): Optional page range (e.g., "1-5", "2,4").

    Returns:
        Dict: A dictionary containing the extracted content.
    """
    suffix = file_path.split('.')[-1]
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
            do_ocr=True, do_table_structure=True, ocr_options=ocr_options
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
            for part in page_range.split(','):
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    pages.extend(range(start - 1, end)) # 0-indexed
                else:
                    pages.append(int(part) - 1) # 0-indexed
            
            # Filter pages
            filtered_content = []
            for i, page in enumerate(doc.pages):
                if i in pages:
                    filtered_content.append(page.export_to_markdown())
            return "\n".join(filtered_content)
        else:
            return doc.export_to_markdown()
    
    except Exception as e:
        print(f"Error extracting content with docling from {file_path}: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    example_content = """
# My Presentation
- Main Point 1
  - Subpoint 1.1
  - Subpoint 1.2
- Main Point 2

---

layout: comparison
# Comparison Example
Left side content.
stuff1
|||
Right side content.
stuff2
stuff3 
---

# stuff you need to really know
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |

---

# Second Slide
This is regular text content.

- Another Point
  - Sub Point
    - Sub Sub Point
"""
    
    output_path = create_presentation_from_markdown(example_content, "my_markdown_presentation.pptx")
    print(f"Created presentation: {output_path}")

    print("\n--- Docling Extraction Example ---")
    # Create a dummy file for docling to extract from
    dummy_text_file = "dummy_docling_test.txt"
    with open(dummy_text_file, "w") as f:
        f.write("This is a test document for docling extraction.\n")
        f.write("It has multiple lines of text.\n")
        f.write("And some more content.")

    extracted_data = extract_content_with_docling('L2 Development of Aortic arches.pdf')
    print(f"Extracted content from {dummy_text_file}: {extracted_data}")

    # Clean up the dummy file
    import os
    os.remove(dummy_text_file)