import sys
import traceback

import customtkinter as ctk


def show_crash_popup(exception):
    """
    Displays a crash report window with the traceback.
    Can be called from the main thread global exception hook.
    """
    try:
        # Create a Toplevel window
        # We assume the main app is running, but if it's super early crash,
        # we might need to create a root.
        # However, for this integration, we assume a root exists or we can create a Toplevel linked to it
        # via the currently active app if possible.

        # If we can't find a root, we might make a new CTk.
        # But safest is usually to use the existing root if available.
        # This function acts as a standalone popup logic.

        root = None
        # Try to find existing root
        try:
            # tkinter default root
            import tkinter
            root = tkinter._default_root
        except:
            pass

        if root and root.winfo_exists():
            window = ctk.CTkToplevel(root)
        else:
            # Fallback if no root matches or exists
            window = ctk.CTk()

        window.title("Whoops! Sunatra Crashed")
        window.geometry("600x500")
        window.attributes("-topmost", True)

        # Red Theme for urgency
        window.configure(fg_color="#18181b")

        # Header
        header = ctk.CTkLabel(window, text="Whoops! Sunatra Crashed",
                              font=("Inter", 20, "bold"), text_color="#ef4444")
        header.pack(pady=(20, 10))

        body = ctk.CTkLabel(window, text="We encountered an error. A report has been automatically sent to the developer.\n"
                                         "Please restart the application.",
                            font=("Inter", 14), text_color="#a1a1aa")
        body.pack(pady=(0, 20))

        # Traceback Textbox
        tb_text = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

        textbox = ctk.CTkTextbox(window, width=540, height=300, font=("Consolas", 12))
        textbox.pack(pady=10)
        textbox.insert("1.0", tb_text)
        textbox.configure(state="disabled") # Readonly

        # Buttons
        btn_frame = ctk.CTkFrame(window, fg_color="transparent")
        btn_frame.pack(pady=20)

        def restart_app():
            import os
            import sys
            # Simple restart: re-execute the script
            # Note: This might not work perfectly in all frozen environments/PyInstaller
            # but is a good best-effort.
            try:
                python = sys.executable
                os.execl(python, python, *sys.argv)
            except Exception as e:
                print(f"Failed to restart: {e}")
                window.destroy()
                sys.exit(1)

        ctk.CTkButton(btn_frame, text="Restart App", fg_color="#ef4444", hover_color="#dc2626",
                      command=restart_app).pack(side="left", padx=10)

        ctk.CTkButton(btn_frame, text="Close", fg_color="#3f3f46", hover_color="#52525b",
                      command=lambda: sys.exit(1)).pack(side="left", padx=10)

        if not root or not root.winfo_exists():
            window.mainloop()

    except Exception as e:
        # Fallback to console if GUI fails
        print("CRITICAL ERROR IN CRASH REPORTER:")
        print(e)
        traceback.print_exc()
