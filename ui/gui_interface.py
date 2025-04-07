import os
import threading
import webbrowser
import customtkinter as ctk
from tkinter import messagebox, filedialog
from core.backup_manager import GameBackupCore

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("dark-blue")
 
class BackupGUI(ctk.CTk):
    def __init__(self, core):
        super().__init__()
        self.title("Game Backup Manager")
        self.geometry("900x650")
        self.core = core
        self.selected_game = None
        self.create_widgets()
        self.refresh_game_list()

    def create_widgets(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self)
        sidebar.grid(row=0, column=0, sticky="ns", padx=10, pady=10)
        
        ctk.CTkLabel(sidebar, 
                    text="Game Backup Manager",
                    font=("Arial", 18, "bold")).pack(pady=20)

        # Action Buttons
        buttons = [
            ("📁 Create Backup", self.create_backup),
            ("🔄 Update Backup", self.update_backup),
            ("⏮️ Restore Backup", self.restore_backup),
            ("⚡ Update All", self.update_all_backups),
            ("🎮 Restore All", self.restore_all_backups),
            ("📂 Change Root", self.change_root_dir),
            ("🔍 Search Saves", self.search_save_location)
        ]
        
        for text, cmd in buttons:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                command=cmd,
                anchor="w",
                font=("Arial", 14),
                compound="left"
            )
            btn.pack(fill="x", padx=5, pady=4)

        # Main area
        main = ctk.CTkFrame(self)
        main.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Game List
        self.game_list_frame = ctk.CTkScrollableFrame(
            main,
            label_text="Configured Games"
        )
        self.game_list_frame.grid(row=1, column=0, sticky="nsew")

        # Backup List
        self.backup_list_frame = ctk.CTkScrollableFrame(
            main,
            label_text="Available Backups"
        )
        self.backup_list_frame.grid(row=1, column=1, sticky="nsew")

    def refresh_game_list(self):
        for widget in self.game_list_frame.winfo_children():
            widget.destroy()

        games = list(self.core.config['games'].keys())
        if not games:
            ctk.CTkLabel(self.game_list_frame, text="No games configured").pack(pady=10)
            self.clear_backup_list()
            return

        for game in games:
            btn = ctk.CTkButton(
                self.game_list_frame,
                text=game,
                command=lambda g=game: self.on_game_select(g),
                fg_color=("#2AA876" if game == self.selected_game else "#3B8ED0")
            )
            btn.pack(fill="x", pady=2, padx=5)

        if games and not self.selected_game:
            self.on_game_select(games[0])

    def on_game_select(self, game_name):
        self.selected_game = game_name
        self.clear_backup_list()
        
        backups = self.core.get_backups(game_name)
        if not backups:
            error_msg = "No backups found"
            if not os.path.exists(self.core.config['games'][game_name]['source_path']):
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
            ctk.CTkLabel(
                self.backup_list_frame,
                text=text,
                font=("Arial", 11)
            ).pack(anchor="w", pady=3)

    def clear_backup_list(self):
        for widget in self.backup_list_frame.winfo_children():
            widget.destroy()


    def update_root_display(self):
        """Update root directory display"""
        current_root = self.core.config['root_backup_dir']
        self.root_dir_entry.configure(state="normal")
        self.root_dir_entry.delete(0, "end")
        self.root_dir_entry.insert(0, current_root)
        self.root_dir_entry.configure(state="readonly")

    def refresh_game_list(self):
        """Refresh game list display"""
        # Clear existing games
        for widget in self.game_list_frame.winfo_children():
            widget.destroy()

        games = list(self.core.config['games'].keys())
        if not games:
            ctk.CTkLabel(self.game_list_frame, text="No games configured").pack(pady=10)
            self.clear_backup_list()
            return

        # Create new game buttons
        for game in games:
            btn = ctk.CTkButton(
                self.game_list_frame,
                text=game,
                command=lambda g=game: self.on_game_select(g),
                fg_color=("#2AA876" if game == self.selected_game else "#3B8ED0")
            )
            btn.pack(fill="x", pady=2, padx=5)

        # Select first game if none selected
        if not self.selected_game and games:
            self.on_game_select(games[0])

    def on_game_select(self, game_name):
        """Handle game selection"""
        self.selected_game = game_name
        self.clear_backup_list()
        
        if not game_name:
            return

        # Update backup list
        backups = self.core.get_backups(game_name)
        if not backups:
            ctk.CTkLabel(self.backup_list_frame, text="No backups found").pack(pady=10)
            return

        for idx, backup in enumerate(backups, 1):
            size_mb = os.path.getsize(backup['path']) / (1024 * 1024)
            text = f"{idx}. {backup['formatted_date']}\n{size_mb:.2f} MB"
            ctk.CTkLabel(
                self.backup_list_frame,
                text=text,
                font=("Arial", 11)
            ).pack(anchor="w", pady=3)

    # ===== Core Functionality Methods =====
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