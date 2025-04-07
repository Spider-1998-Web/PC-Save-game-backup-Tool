import os
import shutil
import json
import datetime
import webbrowser

CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'game_backup_config.json')
CONFIG_FILE = os.path.abspath(CONFIG_FILE)

class GameBackupCore:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Config error: {str(e)}")

    def _save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def _get_backup_dir(self, game_name):
        return os.path.join(self.config['root_backup_dir'], game_name)

    def _get_timestamped_name(self):
        return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    def get_backups(self, game_name):
        backups = []
        backup_dir = self._get_backup_dir(game_name)
        if not os.path.exists(backup_dir):
            return backups

        for filename in sorted(os.listdir(backup_dir), reverse=True):
            full_path = os.path.join(backup_dir, filename)
            try:
                dt = datetime.datetime.strptime(filename, "%Y-%m-%d_%H-%M-%S")
                formatted_date = dt.strftime("%b %d, %Y - %H:%M")
            except ValueError:
                formatted_date = "Unknown"
            backups.append({"name": filename, "path": full_path, "formatted_date": formatted_date})

        return backups

    def create_backup(self, game_name):
        if game_name not in self.config['games']:
            return False, "Game not found in config."

        source_path = self.config['games'][game_name]['source_path']
        backup_dir = self._get_backup_dir(game_name)
        timestamp = self._get_timestamped_name()
        backup_path = os.path.join(backup_dir, timestamp)

        if not os.path.exists(source_path):
            return False, f"Source path not found: {source_path}"

        os.makedirs(backup_dir, exist_ok=True)

        try:
            shutil.copytree(source_path, backup_path)
            return True, f"Backup created at {backup_path}"
        except Exception as e:
            return False, str(e)

    def restore_backup(self, game_name, backup_path):
        if game_name not in self.config['games']:
            return False, "Game not found in config."

        dest_path = self.config['games'][game_name]['source_path']

        if not os.path.exists(backup_path):
            return False, "Backup path does not exist."

        try:
            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)
            shutil.copytree(backup_path, dest_path)
            return True, "Backup restored."
        except Exception as e:
            return False, str(e)

    def update_all_backups(self):
        results = {}
        for game_name in self.config['games']:
            success, message = self.create_backup(game_name)
            results[game_name] = {"success": success, "message": message}
        return results

    def restore_all_backups(self):
        results = {}
        for game_name in self.config['games']:
            backups = self.get_backups(game_name)
            if backups:
                latest_backup = backups[0]['path']
                success, message = self.restore_backup(game_name, latest_backup)
                results[game_name] = {"success": success, "message": message}
            else:
                results[game_name] = {"success": False, "message": "No backup found."}
        return results

    def search_save_locations(self, game_name):
        query = f"{game_name} save game location"
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return {"search_url": url}
