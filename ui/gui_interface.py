import os
import threading
import webbrowser
import customtkinter as ctk
from tkinter import messagebox, filedialog
from core.backup_manager import GameBackupCore
import tkinter as tk
from tkinter import ttk 
import json
import urllib.parse
from ui.theme import COLORS, FONTS, STYLES, configure_theme

class BackupGUI(ctk.CTk):
    def __init__(self, core):
        super().__init__()
        configure_theme()
        self.title("Game Backup Manager")
        self.geometry("900x650")
        self.core = core
        self.selected_game = None
        self.selected_backup_path = None
        self.configure(fg_color=COLORS["background"])
        self.create_widgets()
        self.update_root_display()
        self.refresh_game_list()
        try:
            self.iconbitmap("./assets/icon.ico")
        except:
            pass

    def create_widgets(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, **STYLES["frame"])
        sidebar.grid(row=0, column=0, sticky="ns", padx=10, pady=10)

        root_frame = ctk.CTkFrame(sidebar, **STYLES["frame"])
        root_frame.pack(pady=10, padx=5, fill="x")
        ctk.CTkLabel(root_frame, text="Backup Location:", 
                    font=FONTS["label"], text_color=COLORS["text"]).pack(anchor="w")
        self.root_dir_entry = ctk.CTkEntry(root_frame, **STYLES["entry"])
        self.root_dir_entry.pack(fill="x", pady=5)

        buttons = [
            ("\U0001F4C1 Create Backup", self.create_backup),
            ("\U0001F501 Update Backup", self.update_backup),
            ("\u23EE\uFE0F Restore Backup", self.restore_backup),
            ("\U0001F5D1\uFE0F Delete Backup", self.delete_backup),
            ("\u26A1 Update All", self.update_all_backups),
            ("\U0001F3AE Restore All", self.restore_all_backups),
            ("\U0001F4C2 Change Root", self.change_root_dir),
            ("\U0001F50D Search Saves", self.search_save_location)
        ]

        for text, cmd in buttons:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                command=cmd,
                **STYLES["button"],
                font=FONTS["button"]
            )
            btn.pack(fill="x", padx=5, pady=4)

        main = ctk.CTkFrame(self, **STYLES["frame"])
        main.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self.game_list_frame = ctk.CTkScrollableFrame(
            main,
            label_text="Configured Games",
            **STYLES["frame"],
            label_font=FONTS["body"]
        )
        self.game_list_frame.grid(row=1, column=0, sticky="nsew")

        self.backup_list_frame = ctk.CTkScrollableFrame(
            main,
            label_text="Available Backups",
            **STYLES["frame"],
            label_font=FONTS["body"]
        )
        self.backup_list_frame.grid(row=1, column=1, sticky="nsew")

    def refresh_game_list(self):
        for widget in self.game_list_frame.winfo_children():
            widget.destroy()

        games = list(self.core.config['games'].keys())
        if not games:
            ctk.CTkLabel(
                self.game_list_frame, 
                text="No games configured",
                text_color=COLORS["text"],
                font=FONTS["body"]
            ).pack(pady=10)
            self.clear_backup_list()
            return

        for game in games:
            is_selected = (game == self.selected_game)
            btn = ctk.CTkButton(
                self.game_list_frame,
                text=f"✔ {game}" if is_selected else game,
                command=lambda g=game: self.on_game_select(g),
                fg_color=COLORS["accent"] if is_selected else COLORS["surface"],
                hover_color=COLORS["secondary"],
                text_color="#000000" if is_selected else COLORS["text"],
                border_width=2 if is_selected else 0,
                border_color=COLORS["accent"],
                corner_radius=6
            )
            btn.pack(fill="x", pady=2, padx=5)

    def on_game_select(self, game_name):
        self.selected_game = game_name
        self.selected_backup_path = None
        self.refresh_game_list()
        self.clear_backup_list()

        backups = self.core.get_backups(game_name)
        if not backups:
            error_msg = "No backups found"
            if game_name and not os.path.exists(self.core.config['games'][game_name]['source_path']):
                error_msg = f"Source path missing!\n{self.core.config['games'][game_name]['source_path']}"
            ctk.CTkLabel(
                self.backup_list_frame,
                text=error_msg,
                text_color="#FF5555" if "missing" in error_msg else None
            ).pack(pady=10)
            return

        for idx, backup in enumerate(backups, 1):
            size_mb = os.path.getsize(backup['path']) / (1024 * 1024)
            text = f"{idx}. {backup['formatted_date']}\n{size_mb:.2f} MB"
            btn = ctk.CTkButton(
                self.backup_list_frame,
                text=text,
                font=("Arial", 11),
                anchor="w",
                fg_color=COLORS["accent"] if backup['path'] == self.selected_backup_path else COLORS["surface"],
                hover_color=COLORS["secondary"],
                text_color=COLORS["text"],
                command=lambda b=backup: self.on_backup_select(b['path'])
            )
            btn.pack(fill="x", pady=3, padx=5)

    def on_backup_select(self, backup_path):
        if self.selected_backup_path == backup_path:
            self.selected_backup_path = None
        else:
            self.selected_backup_path = backup_path
        self.on_game_select(self.selected_game)

    def clear_backup_list(self):
        for widget in self.backup_list_frame.winfo_children():
            widget.destroy()

    def update_root_display(self):
        current_root = self.core.config['root_backup_dir']
        self.root_dir_entry.configure(state="normal")
        self.root_dir_entry.delete(0, "end")
        self.root_dir_entry.insert(0, current_root)
        self.root_dir_entry.configure(state="readonly")

    def create_backup(self):
        name = ctk.CTkInputDialog(text="Enter game name:", title="Create Backup").get_input()
        if not name:
            return
        if name in self.core.config['games']:
            messagebox.showerror("Error", "Game already exists!")
            return

        source = filedialog.askdirectory(title="Select Save Folder")
        if not source:
            return

        self.core.config['games'][name] = {
            'source_path': source,
            'backup_dir': os.path.join(self.core.config['root_backup_dir'], name)
        }
        self.core._save_config()
        self.selected_game = name  # Auto-select new game after adding

        def _create():
            success, msg = self.core.create_backup(name)
            self.after(0, lambda: messagebox.showinfo(
                "Result", 
                "✅ Backup created!" if success else f"❌ Error: {msg}"
            ))
            self.refresh_game_list()

        threading.Thread(target=_create, daemon=True).start()

    def update_backup(self):
        if not self.selected_game:
            messagebox.showerror("Error", "No game selected!")
            return
        
        def _update():
            success, msg = self.core.create_backup(self.selected_game)
            self.after(0, lambda: messagebox.showinfo(
                "Result", 
                "✅ Backup updated!" if success else f"❌ Error: {msg}"
            ))
            self.on_game_select(self.selected_game)
        
        threading.Thread(target=_update, daemon=True).start()

    def restore_backup(self):
        if not self.selected_game:
            messagebox.showerror("Error", "No game selected!")
            return
        
        backups = self.core.get_backups(self.selected_game)
        if not backups:
            messagebox.showinfo("Info", "No backups available")
            return
        
        options = "\n".join([f"{i+1}. {b['formatted_date']}" for i, b in enumerate(backups)])
        choice = ctk.CTkInputDialog(
            text=f"Select backup to restore:\n{options}",
            title="Restore Backup"
        ).get_input()
        
        if not choice or not choice.isdigit():
            return
        
        index = int(choice) - 1
        if 0 <= index < len(backups):
            def _restore():
                success, msg = self.core.restore_backup(
                    self.selected_game, 
                    backups[index]['path']
                )
                self.after(0, lambda: messagebox.showinfo(
                    "Result",
                    "✅ Restore successful!" if success else f"❌ Error: {msg}"
                ))
            
            threading.Thread(target=_restore, daemon=True).start()

    def delete_backup(self):
        if not self.selected_game:
            messagebox.showerror("Error", "No game selected!")
            return
        
        backups = self.core.get_backups(self.selected_game)
        if not backups:
            messagebox.showinfo("Info", "No backups available to delete")
            return
            
        options = "\n".join([f"{i+1}. {b['formatted_date']}" for i, b in enumerate(backups)])
        choice = ctk.CTkInputDialog(
            text=f"Select backup to delete:\n{options}",
            title="Delete Backup"
        ).get_input()
        
        if not choice or not choice.isdigit():
            return
            
        index = int(choice) - 1
        if 0 <= index < len(backups):
            if messagebox.askyesno("Confirm", "Permanently delete this backup?"):
                current_self = self
                def _delete():
                    success, msg = current_self.core.delete_backup(
                        current_self.selected_game, 
                        backups[index]['path']
                    )
                    current_self.after(0, lambda: messagebox.showinfo(
                        "Result",
                        "✅ Backup deleted!" if success else f"❌ {msg}"
                    ))
                    current_self.on_game_select(current_self.selected_game)
                
                threading.Thread(target=_delete, daemon=True).start()       

    def update_all_backups(self):
        if messagebox.askyesno("Confirm", "Backup ALL games?"):
            def _update_all():
                results = self.core.update_all_backups()
                report = "\n".join(
                    f"{k}: {'✅' if v['success'] else '❌'} {v['message']}" 
                    for k, v in results.items()
                )
                self.after(0, lambda: messagebox.showinfo("Update All", report))
                self.refresh_game_list()
            
            threading.Thread(target=_update_all, daemon=True).start()

    def restore_all_backups(self):
        if messagebox.askyesno("Warning", "Restore ALL games to latest backups?"):
            def _restore_all():
                results = self.core.restore_all_backups()
                report = "\n".join(
                    f"{k}: {'✅' if v['success'] else '❌'} {v['message']}" 
                    for k, v in results.items()
                )
                self.after(0, lambda: messagebox.showinfo("Restore All", report))
            
            threading.Thread(target=_restore_all, daemon=True).start()
            

    def change_root_dir(self):
        new_root = filedialog.askdirectory()
        if new_root:
            self.core.config['root_backup_dir'] = os.path.normpath(new_root)
            self.core._save_config()
            self.update_root_display()
            messagebox.showinfo("Success", f"Root directory updated to:\n{new_root}")
            self.refresh_game_list()

    def search_save_location(self):
        name = ctk.CTkInputDialog(text="Enter game name:", title="Search Saves").get_input()
        if name:
            url = self.core.search_save_locations(name)['search_url']
            webbrowser.open(url)

            

    def run(self):
        self.mainloop()