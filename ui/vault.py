import customtkinter as ctk
import json
import os
import uuid
from tkinter import messagebox
from core.utils import safe_messagebox

class PromptManager:
    """Manages storage of prompts in JSON file."""
    def __init__(self, filename="prompts.json"):
        import appdirs
        data_dir = appdirs.user_data_dir("SunoSync", "SunoSync")
        self.filepath = os.path.join(data_dir, filename)
        
        # Ensure dir exists
        os.makedirs(data_dir, exist_ok=True)
        
        self.prompts = {}
        self.load()
    
    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.prompts = json.load(f)
            except:
                self.prompts = {}
    
    def save(self):
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.prompts, f, indent=4)
        except Exception as e:
            print(f"Error saving prompts: {e}")

    def add_prompt(self, title, text, tags=""):
        uid = str(uuid.uuid4())
        self.prompts[uid] = {
            "title": title,
            "text": text,
            "tags": [t.strip() for t in tags.split(",")] if isinstance(tags, str) else tags,
            "created_at": time.time()
        }
        self.save()
        return uid

    def delete_prompt(self, uid):
        if uid in self.prompts:
            del self.prompts[uid]
            self.save()
            return True
        return False
        
    def get_all(self):
        # Sort by title
        return dict(sorted(self.prompts.items(), key=lambda item: item[1]['title'].lower()))

import time

class VaultTab(ctk.CTkFrame):
    """Prompt Vault Tab for storing ideas."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.manager = PromptManager()
        self.selected_uid = None
        
        # Layout: Left Sidebar (List) | Right Content (Details)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # --- Left Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color="#252526")
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)
        
        # Search
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.refresh_list)
        self.search = ctk.CTkEntry(self.sidebar, placeholder_text="Search prompts...",
                                   textvariable=self.search_var,
                                   font=("Segoe UI", 12), fg_color="#2d2d30",
                                   border_color="#3a3a3d", text_color="#FFFFFF",
                                   placeholder_text_color="#9aa0a6")
        self.search.pack(fill="x", padx=10, pady=10)
        
        # Add Button
        ctk.CTkButton(self.sidebar, text="+ New Prompt", command=self.new_prompt,
                      fg_color="#5c8bc4", hover_color="#3f6a9e",
                      font=("Segoe UI", 13, "bold"), corner_radius=8).pack(fill="x", padx=10, pady=(0, 10))
        
        # List Area
        self.scroll_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.scroll_list.pack(fill="both", expand=True, padx=5, pady=5)
        
        # --- Right Content ---
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        # Title Input
        ctk.CTkLabel(self.content, text="Title", anchor="w",
                     font=("Segoe UI", 12, "bold"), text_color="#9aa0a6").pack(anchor="w")
        self.title_entry = ctk.CTkEntry(self.content, placeholder_text="My Awesome Prompt",
                                        font=("Segoe UI", 12), fg_color="#2d2d30",
                                        border_color="#3a3a3d", text_color="#FFFFFF")
        self.title_entry.pack(fill="x", pady=(5, 15))
        
        # Tags Input
        ctk.CTkLabel(self.content, text="Tags (comma separated)", anchor="w",
                     font=("Segoe UI", 12, "bold"), text_color="#9aa0a6").pack(anchor="w")
        self.tags_entry = ctk.CTkEntry(self.content, placeholder_text="Dark, Techno, Fast",
                                       font=("Segoe UI", 12), fg_color="#2d2d30",
                                       border_color="#3a3a3d", text_color="#FFFFFF")
        self.tags_entry.pack(fill="x", pady=(5, 15))
        
        # Prompt Text
        ctk.CTkLabel(self.content, text="Prompt", anchor="w",
                     font=("Segoe UI", 12, "bold"), text_color="#9aa0a6").pack(anchor="w")
        self.prompt_text = ctk.CTkTextbox(self.content, font=("Segoe UI", 12),
                                          fg_color="#2d2d30", text_color="#FFFFFF",
                                          border_color="#3a3a3d")
        self.prompt_text.pack(fill="both", expand=True, pady=(5, 15))
        
        # Action Buttons
        self.btn_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.btn_frame.pack(fill="x")
        
        self.save_btn = ctk.CTkButton(self.btn_frame, text="Save", command=self.save_prompt,
                                      width=100, fg_color="#5c8bc4", hover_color="#3f6a9e",
                                      font=("Segoe UI", 13), corner_radius=8)
        self.save_btn.pack(side="right", padx=5)
        
        self.copy_btn = ctk.CTkButton(self.btn_frame, text="Copy to Clipboard",
                                      command=self.copy_to_clipboard,
                                      fg_color="#66bb6a", hover_color="#43a047",
                                      font=("Segoe UI", 13), corner_radius=8)
        self.copy_btn.pack(side="right", padx=5)
        
        self.del_btn = ctk.CTkButton(self.btn_frame, text="Delete",
                                     command=self.delete_current,
                                     fg_color="#f44336", hover_color="#d32f2f",
                                     width=100, font=("Segoe UI", 13), corner_radius=8)
        self.del_btn.pack(side="left", padx=5)
        
        self.status_lbl = ctk.CTkLabel(self.btn_frame, text="",
                                       text_color="#66bb6a", font=("Segoe UI", 12))
        self.status_lbl.pack(side="right", padx=10)
        
        self.prompt_buttons = {} # uid -> properties
        self.refresh_list()
        self.new_prompt() # Clear fields

    def refresh(self):
        """Reload data from disk and refresh list."""
        self.manager.load()
        self.refresh_list()

    def refresh_list(self, *args):
        # clear
        for w in self.scroll_list.winfo_children():
            w.destroy()
            
        search = self.search_var.get().lower()
        all_prompts = self.manager.get_all()
        
        for uid, data in all_prompts.items():
            title = data.get('title', 'Untitled')
            # Filter
            if search and search not in title.lower():
                continue
                
            btn = ctk.CTkButton(self.scroll_list, text=title, anchor="w", 
                                fg_color="transparent", text_color="#9aa0a6",
                                hover_color="#2d2d30", font=("Segoe UI", 12),
                                command=lambda u=uid: self.load_prompt(u))
            btn.pack(fill="x", pady=2)
            self.prompt_buttons[uid] = btn

    def load_prompt(self, uid):
        if uid not in self.manager.prompts: return
        
        data = self.manager.prompts[uid]
        self.selected_uid = uid
        
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, data.get('title', ''))
        
        tags = data.get('tags', [])
        self.tags_entry.delete(0, "end")
        self.tags_entry.insert(0, ", ".join(tags) if isinstance(tags, list) else str(tags))
        
        self.prompt_text.delete("1.0", "end")
        
        raw_text = data.get('text', '')
        if raw_text:
             # Fix escaped newlines that might be in the data
             clean_text = raw_text.replace('\\n', '\n')
             self.prompt_text.insert("1.0", clean_text)
        
        # reliable highlight
        for u, btn in self.prompt_buttons.items():
            btn.configure(fg_color="#2d2d30" if u == uid else "transparent",
                          text_color="#FFFFFF" if u == uid else "#9aa0a6")

    def new_prompt(self):
        self.selected_uid = None
        self.title_entry.delete(0, "end")
        self.tags_entry.delete(0, "end")
        self.prompt_text.delete("1.0", "end")
        
    def save_prompt(self):
        title = self.title_entry.get().strip()
        text = self.prompt_text.get("1.0", "end-1c").strip()
        tags = self.tags_entry.get().strip()
        
        if not title:
            safe_messagebox(messagebox.showerror, "Error", "Title cannot be empty")
            return
            
        if self.selected_uid:
            # Update existing
            self.manager.prompts[self.selected_uid]['title'] = title
            self.manager.prompts[self.selected_uid]['text'] = text
            self.manager.prompts[self.selected_uid]['tags'] = tags.split(",") if tags else []
            self.manager.save()
        else:
            # Create new
            self.selected_uid = self.manager.add_prompt(title, text, tags)
            
        self.refresh_list()
        self.show_status("Saved!")
        self.load_prompt(self.selected_uid) # maintain selection

    def delete_current(self):
        if not self.selected_uid: return
        
        if safe_messagebox(messagebox.askyesno, "Confirm", "Delete this prompt?"):
            self.manager.delete_prompt(self.selected_uid)
            self.new_prompt()
            self.refresh_list()
            
    def copy_to_clipboard(self):
        text = self.prompt_text.get("1.0", "end-1c")
        if text:
            import pyperclip
            pyperclip.copy(text)
            self.show_status("Copied!")
            
    def show_status(self, msg):
        self.status_lbl.configure(text=msg)
        self.after(2000, lambda: self.status_lbl.configure(text=""))
