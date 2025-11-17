import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
import tempfile
import os
import httpx

from pptx_utils import create_presentation_from_markdown, extract_content_with_docling

class PresentationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Presentation Generator")
        self.resources = []

        # Main frame
        main_frame = ttk.Frame(root, padding=(10, 10))
        main_frame.pack(fill=BOTH, expand=True)

        # --- Left Pane (Resource Management) ---
        left_pane = ttk.Frame(main_frame)
        left_pane.pack(side=LEFT, fill=Y, padx=(0, 10))

        # Resource List
        list_frame = ttk.Labelframe(left_pane, text="Resources")
        list_frame.pack(fill=Y, expand=True)

        self.tree = ttk.Treeview(list_frame, columns=("type", "source", "range"), show="headings")
        self.tree.heading("type", text="Type")
        self.tree.heading("source", text="Source")
        self.tree.heading("range", text="Range/Chapter")
        self.tree.column("type", width=50, anchor=CENTER)
        self.tree.column("source", width=200)
        self.tree.column("range", width=100)
        self.tree.pack(fill=Y, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_resource_select)

        # Resource Management Buttons
        btn_list_frame = ttk.Frame(left_pane)
        btn_list_frame.pack(fill=X, pady=5)
        self.move_up_btn = ttk.Button(btn_list_frame, text="Up", command=self.move_resource_up, state=DISABLED)
        self.move_up_btn.pack(side=LEFT, expand=True, fill=X, padx=2)
        self.move_down_btn = ttk.Button(btn_list_frame, text="Down", command=self.move_resource_down, state=DISABLED)
        self.move_down_btn.pack(side=LEFT, expand=True, fill=X, padx=2)
        self.remove_btn = ttk.Button(btn_list_frame, text="Remove", command=self.remove_resource, bootstyle="danger", state=DISABLED)
        self.remove_btn.pack(side=LEFT, expand=True, fill=X, padx=2)

        # --- Right Pane (Editing and Preview) ---
        right_pane = ttk.Frame(main_frame)
        right_pane.pack(side=LEFT, fill=BOTH, expand=True)

        # Add Resource Frame
        add_frame = ttk.Labelframe(right_pane, text="Add Resource")
        add_frame.pack(fill=X, pady=(0, 10))

        self.url_label = ttk.Label(add_frame, text="URL:")
        self.url_label.grid(row=0, column=0, padx=5, pady=5, sticky=W)
        self.url_entry = ttk.Entry(add_frame)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5, sticky=EW)
        self.add_url_btn = ttk.Button(add_frame, text="Add URL", command=self.add_url, bootstyle="info")
        self.add_url_btn.grid(row=0, column=2, padx=5, pady=5)

        self.add_file_btn = ttk.Button(add_frame, text="Add File", command=self.add_file, bootstyle="info")
        self.add_file_btn.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky=EW)
        add_frame.columnconfigure(1, weight=1)

        # Edit Resource Frame
        edit_frame = ttk.Labelframe(right_pane, text="Edit Selected Resource")
        edit_frame.pack(fill=X, pady=10)
        
        self.range_label = ttk.Label(edit_frame, text="Range/Chapter:")
        self.range_label.grid(row=0, column=0, padx=5, pady=5, sticky=W)
        self.range_entry = ttk.Entry(edit_frame)
        self.range_entry.grid(row=0, column=1, padx=5, pady=5, sticky=EW)
        self.update_range_btn = ttk.Button(edit_frame, text="Update", command=self.update_resource_range, state=DISABLED)
        self.update_range_btn.grid(row=0, column=2, padx=5, pady=5)
        edit_frame.columnconfigure(1, weight=1)

        # Content Preview
        preview_frame = ttk.Labelframe(right_pane, text="Presentation Content (Editable Markdown)")
        preview_frame.pack(fill=BOTH, expand=True)
        self.text_area = ttk.Text(preview_frame, wrap=WORD)
        self.text_area.pack(fill=BOTH, expand=True, padx=5, pady=5)
        # self.text_area.config(state=DISABLED) # Make it editable by default

        # Button to load content from resources
        self.load_content_btn = ttk.Button(preview_frame, text="Load Content from Resources", command=self.load_content_from_resources, bootstyle="secondary")
        self.load_content_btn.pack(fill=X, pady=(0, 5))

        # Generate Button
        self.generate_button = ttk.Button(right_pane, text="Generate Presentation", command=self.generate_presentation, bootstyle="success")
        self.generate_button.pack(fill=X, pady=(10, 0))

    def add_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            resource = {"type": "File", "source": file_path, "range": ""}
            self.resources.append(resource)
            self.refresh_resource_list()

    def add_url(self):
        url = self.url_entry.get()
        if url:
            resource = {"type": "URL", "source": url, "range": ""}
            self.resources.append(resource)
            self.refresh_resource_list()
            self.url_entry.delete(0, END)
        else:
            messagebox.showwarning("Input Error", "Please enter a URL.")

    def remove_resource(self):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        selected_index = self.tree.index(selected_item[0])
        del self.resources[selected_index]
        self.refresh_resource_list()

    def move_resource_up(self):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        selected_index = self.tree.index(selected_item[0])
        if selected_index > 0:
            self.resources.insert(selected_index - 1, self.resources.pop(selected_index))
            self.refresh_resource_list(select_index=selected_index - 1)

    def move_resource_down(self):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        selected_index = self.tree.index(selected_item[0])
        if selected_index < len(self.resources) - 1:
            self.resources.insert(selected_index + 1, self.resources.pop(selected_index))
            self.refresh_resource_list(select_index=selected_index + 1)

    def update_resource_range(self):
        selected_item = self.tree.selection()
        if not selected_item:
            return
            
        selected_index = self.tree.index(selected_item[0])
        self.resources[selected_index]["range"] = self.range_entry.get()
        self.refresh_resource_list(select_index=selected_index)

    def refresh_resource_list(self, select_index=None):
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        for i, res in enumerate(self.resources):
            self.tree.insert("", END, iid=i, values=(res["type"], os.path.basename(res["source"]), res["range"]))
        
        if select_index is not None and select_index < len(self.resources):
            self.tree.selection_set(str(select_index))
        
        # self.update_content_preview() # Removed automatic update

    def on_resource_select(self, event):
        selected = bool(self.tree.selection())
        self.remove_btn.config(state=NORMAL if selected else DISABLED)
        self.move_up_btn.config(state=NORMAL if selected else DISABLED)
        self.move_down_btn.config(state=NORMAL if selected else DISABLED)
        self.update_range_btn.config(state=NORMAL if selected else DISABLED)

        if selected:
            selected_index = self.tree.index(self.tree.selection()[0])
            resource = self.resources[selected_index]
            self.range_entry.delete(0, END)
            self.range_entry.insert(0, resource["range"])
        else:
            self.range_entry.delete(0, END)

    def load_content_from_resources(self):
        self.text_area.config(state=NORMAL)
        self.text_area.delete(1.0, END)
        
        full_content = []
        for res in self.resources:
            try:
                if res["type"] == "File":
                    content = extract_content_with_docling(res["source"], page_range=res["range"] or None)
                elif res["type"] == "URL":
                    with httpx.Client(follow_redirects=True, timeout=10.0) as client:
                        response = client.get(res["source"])
                        response.raise_for_status()
                        suffix = os.path.splitext(res["source"])[1] or '.tmp'
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                            temp_file.write(response.content)
                            temp_file_path = temp_file.name
                    
                    content = extract_content_with_docling(temp_file_path, page_range=res["range"] or None)
                    os.unlink(temp_file_path)
                
                if content:
                    full_content.append(f"--- Resource: {os.path.basename(res['source'])} ---\n{content}\n")

            except Exception as e:
                full_content.append(f"--- ERROR processing {os.path.basename(res['source'])}: {e} ---\n")
        
        self.text_area.insert(END, "\n".join(full_content))
        self.text_area.config(state=NORMAL) # Keep it editable

    def generate_presentation(self):
        # self.update_content_preview() # No longer needed, content is directly editable
        content = self.text_area.get(1.0, END)
        if not content.strip():
            messagebox.showerror("Error", "There is no content to generate a presentation from.")
            return
        
        output_path = filedialog.asksaveasfilename(
            defaultextension=".pptx",
            filetypes=[("PowerPoint", "*.pptx"), ("All Files", "*.*")]
        )
        
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
