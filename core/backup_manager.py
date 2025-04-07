import os
import shutil
import json
import urllib.parse
from datetime import datetime

CONFIG_FILE = "game_backup_config.json"
DEFAULT_ROOT = r"C:\save game"
SAVEGAME_PRO_URL = "https://savegame.pro/"

class GameBackupCore:
    def __init__(self):
        self.config = self._load_config()
        self._ensure_root_structure()

    def _load_config(self):
        config_path = os.path.abspath(CONFIG_FILE)
        default_config = {
            'root_backup_dir': DEFAULT_ROOT,
            'games': {},
            'version': '4.1'
        }

        try:
            if not os.path.exists(config_path):
                return self._create_new_config(config_path, default_config)

            with open(config_path, 'r') as f:
                if os.stat(config_path).st_size == 0:
                    raise json.JSONDecodeError("Empty config file", "", 0)
                return self._validate_config(json.load(f), default_config)

        except Exception as e:
            print(f"Config error: {str(e)} - Reinitializing")
            return self._reinitialize_config(config_path, default_config)

    def _create_new_config(self, path, config):
        with open(path, 'w') as f:
            json.dump(config, f, indent=4)
        return config.copy()

    def _validate_config(self, config, default):
        config['root_backup_dir'] = config.get('root_backup_dir', default['root_backup_dir'])
        config['games'] = config.get('games', default['games'])
        return config

    def _reinitialize_config(self, path, default):
        try:
            shutil.copy(path, f"{path}.bak")
        except Exception as e:
            print(f"Config backup failed: {str(e)}")
        return self._create_new_config(path, default)

    def _save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def _ensure_root_structure(self):
        os.makedirs(self.config['root_backup_dir'], exist_ok=True)

    def create_backup(self, game_name):
        try:
            cfg = self.config['games'][game_name]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(cfg['backup_dir'], f"backup_{timestamp}")

            if not os.path.exists(cfg['source_path']):
                return False, "Source path not found"

            os.makedirs(backup_dir, exist_ok=True)
            
            if os.path.isdir(cfg['source_path']):
                shutil.copytree(cfg['source_path'], backup_dir, dirs_exist_ok=True)
            else:
                shutil.copy2(cfg['source_path'], backup_dir)
            
            return True, f"Backup created: {os.path.basename(backup_dir)}"
        except Exception as e:
            return False, str(e)

    def restore_backup(self, game_name, backup_path):
        try:
            cfg = self.config['games'][game_name]
            source = os.path.normpath(cfg['source_path'])
            backup = os.path.normpath(backup_path)

            if not os.path.exists(backup):
                return False, "Backup doesn't exist"

            # Clear source
            if os.path.isdir(source):
                shutil.rmtree(source, ignore_errors=True)
            elif os.path.exists(source):
                os.remove(source)

            # Restore
            if os.path.isdir(backup):
                shutil.copytree(backup, source, dirs_exist_ok=True)
            else:
                os.makedirs(os.path.dirname(source), exist_ok=True)
                shutil.copy2(backup, source)

            return True, "Restore successful"
        except Exception as e:
            return False, f"Restore failed: {str(e)}"

    def get_backups(self, game_name):
        try:
            backup_dir = self.config['games'][game_name]['backup_dir']
            if not os.path.exists(backup_dir):
                return []

            backups = []
            for entry in os.listdir(backup_dir):
                if entry.startswith("backup_"):
                    path = os.path.join(backup_dir, entry)
                    mtime = os.path.getmtime(path)
                    backups.append({
                        'path': path,
                        'name': entry,
                        'timestamp': mtime,
                        'formatted_date': datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            return sorted(backups, key=lambda x: x['timestamp'], reverse=True)
        except Exception:
            return []

    def update_all_backups(self):
        results = {}
        for game in self.config['games']:
            success, msg = self.create_backup(game)
            results[game] = {'success': success, 'message': msg}
        return results

    def restore_all_backups(self):
        results = {}
        for game in self.config['games']:
            backups = self.get_backups(game)
            if not backups:
                results[game] = {'success': False, 'message': 'No backups'}
                continue
            success, msg = self.restore_backup(game, backups[0]['path'])
            results[game] = {'success': success, 'message': msg}
        return results

    def search_save_locations(self, game_name):
        return {
            'search_url': f"{SAVEGAME_PRO_URL}?s={urllib.parse.quote_plus(game_name)}",
            'game': game_name
        }