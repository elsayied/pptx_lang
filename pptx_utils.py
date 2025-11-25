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
