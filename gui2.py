import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
import httpx
import tempfile
import os

# We assume pptx_utils.py is in the same directory
# It should contain:
# - create_presentation_from_markdown(content, output_path)
# - extract_content_with_docling(file_path)
# A mock file is provided separately to allow this app to run for UI testing.
try:
    from pptx_utils import create_presentation_from_markdown, extract_content_with_docling
except ImportError:
    messagebox.showerror("Missing Module", "Could not find pptx_utils.py. A mock file should be used for testing.")
    # Define mock functions if the import fails, so the app can at least start
    def create_presentation_from_markdown(content, output_path):
        print(f"Mock Create: Presentation at {output_path} with content:\n{content[:50]}...")
    
    def extract_content_with_docling(file_path):
        print(f"Mock Extract: Extracting from {file_path}")
        return f"Mock content from {os.path.basename(file_path)}"

class PresentationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Presentation Generator")

        # Main frame
        main_frame = ttk.Frame(root, padding=(10, 10))
        main_frame.pack(fill=BOTH, expand=True)

        # --- Options Frame (URL and Range) ---
        # Placed this frame first as in the original layout logic
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill=X, pady=5)

        # URL Entry
        self.url_label = ttk.Label(options_frame, text="URL:")
        self.url_label.pack(side=LEFT, padx=(0, 5))
        self.url_entry = ttk.Entry(options_frame)
        # Use fill=X and expand=True to make it fill the space
        self.url_entry.pack(side=LEFT, fill=X, expand=True, padx=5)

        # Range Entry
        self.range_label = ttk.Label(options_frame, text="Page Range (e.g., 1-5):")
        self.range_label.pack(side=LEFT, padx=(10, 5))
        self.range_entry = ttk.Entry(options_frame, width=10)
        self.range_entry.pack(side=LEFT, padx=5)

        # --- Button Frame ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X, pady=5)

        # Buttons
        self.import_file_button = ttk.Button(button_frame, text="Import File", 
                                             command=self.import_file, bootstyle="info")
        self.import_file_button.pack(side=LEFT, padx=5)

        self.import_url_button = ttk.Button(button_frame, text="Import from URL", 
                                            command=self.import_from_url, bootstyle="info")
        self.import_url_button.pack(side=LEFT, padx=5)

        self.generate_button = ttk.Button(button_frame, text="Generate Presentation", 
                                          command=self.generate_presentation, bootstyle="success")
        self.generate_button.pack(side=RIGHT, padx=5)

        # --- Text Area ---
        # The text area should be last to fill the remaining space
        self.text_area = ttk.Text(main_frame, wrap=WORD, height=20)
        self.text_area.pack(fill=BOTH, expand=True, pady=(5,0))


    def import_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            # For now, I'm assuming the range is not used for local files.
            # This could be implemented if the extraction function supports it.
            try:
                content = extract_content_with_docling(file_path)
                if content:
                    self.text_area.delete(1.0, END)
                    self.text_area.insert(END, content)
                else:
                    messagebox.showerror("Error", "Could not extract content from the file (empty content).")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to extract content: {e}")

    def import_from_url(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return

        try:
            # Use httpx.Client for clearer timeout handling
            with httpx.Client(follow_redirects=True, timeout=10.0) as client:
                response = client.get(url)
                response.raise_for_status()
                
                # Create a temporary file to save the content
                suffix = os.path.splitext(url)[1] or '.tmp' # Ensure suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                    temp_file.write(response.content)
                    temp_file_path = temp_file.name

            # Now extract content from the downloaded file
            # The range from range_entry could be used here
            page_range = self.range_entry.get() or None # Pass range if it exists
            
            # Pass range to the extraction function (assuming it accepts it)
            # You might need to adjust this call if your function signature is different
            content = extract_content_with_docling(temp_file_path, page_range=page_range)
            
            # Clean up the temporary file
            os.unlink(temp_file_path)

            if content:
                self.text_area.delete(1.0, END)
                self.text_area.insert(END, content)
            else:
                messagebox.showerror("Error", "Could not extract content from the URL (empty content).")

        except httpx.RequestError as e:
            messagebox.showerror("Error", f"Could not fetch content from URL: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")


    def generate_presentation(self):
        content = self.text_area.get(1.0, END)
        if not content.strip():
            messagebox.showerror("Error", "The text area is empty.")
            return
        
        # Ask for a directory first
        output_dir = filedialog.askdirectory()
        if not output_dir:
            return # User cancelled
            
        # Hardcode a filename or ask the user
        output_filename = "presentation.pptx"
        output_path = os.path.join(output_dir, output_filename)
        
        # Original code used askdirectory, but create_presentation_from_markdown
        # likely needs a full file path.
        # If you want to ask for the save *filename*:
        # output_path = filedialog.asksaveasfilename(
        #     defaultextension=".pptx",
        #     filetypes=[("PowerPoint", "*.pptx"), ("All Files", "*.*")]
        # )
        
        if output_path:
            try:
                create_presentation_from_markdown(content, output_path)
                messagebox.showinfo("Success", f"Presentation saved to {output_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate presentation: {e}")

if __name__ == "__main__":
    # Use ttk.Window for the main window, pick a theme
    root = ttk.Window(themename="flatly") 
    app = PresentationApp(root)
    root.mainloop()