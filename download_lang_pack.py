import requests
import os
import sys
import shutil

def find_tessdata_path():
    """
    Attempts to find the default tessdata directory across different OS.
    """
    # Check TESSDATA_PREFIX environment variable
    if 'TESSDATA_PREFIX' in os.environ:
        return os.environ['TESSDATA_PREFIX']

    # Common default paths
    if sys.platform.startswith('win'):
        # Windows default installation path
        default_path = r'C:\Program Files\Tesseract-OCR\tessdata'
        if os.path.exists(default_path):
            return default_path
    else:
        # Linux/macOS common paths
        common_paths = [
            '/usr/share/tessdata',
            '/usr/local/share/tessdata',
            '/usr/share/tesseract-ocr/4.00/tessdata', # Example for specific versions
            '/usr/share/tesseract-ocr/5.00/tessdata'
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
    
    # Fallback to current directory if default not found
    return os.getcwd()

def download_tesseract_language(lang_code, output_dir=None, repository='tessdata'):
    """
    Downloads a Tesseract language .traineddata file from GitHub.

    Args:
        lang_code (str): The language code (e.g., 'fra', 'spa', 'chi_sim').
        output_dir (str, optional): The directory to save the file. If None, 
                                    it attempts to find the default tessdata path.
        repository (str): The GitHub repository ('tessdata', 'tessdata_fast', 
                          or 'tessdata_best').
    """
    if output_dir is None:
        output_dir = find_tessdata_path()
        if not os.path.exists(output_dir):
            print(f"Warning: Default tessdata path not found. Creating {output_dir} directory.")
            os.makedirs(output_dir, exist_ok=True)

    file_name = f"{lang_code}.traineddata"
    # Use raw.githubusercontent.com for direct file access
    url = f"https://raw.githubusercontent.com/tesseract-ocr/{repository}/main/{file_name}"
    destination_path = os.path.join(output_dir, file_name)

    print(f"Attempting to download {file_name} from {url}")
    print(f"Saving to: {destination_path}")

    try:
        response = requests.get(url, stream=True)
        response.raise_for_status() # Raise an exception for bad status codes

        with open(destination_path, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
        print(f"Successfully downloaded {file_name}")

    except requests.exceptions.RequestException as e:
        print(f"Error downloading the file: {e}")
        print("Please check the language code and repository name.")
        print("You may need to manually place the file in the tessdata directory.")
        print(f"Download link: {url}")