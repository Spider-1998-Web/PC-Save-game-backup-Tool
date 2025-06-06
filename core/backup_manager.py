import os
import shutil
import json
import urllib.parse
from datetime import datetime

CONFIG_FILE = "game_backup_config.json"
SAVEGAME_PRO_URL = "https://savegame.pro/"
DEFAULT_ROOT = os.path.abspath("C:\\GameBackups")

class GameBackupCore:
    def __init__(self):
        self.config = self._load_config()
        self._ensure_paths()

    def _load_config(self):
        """Load or create configuration file"""
        config_path = os.path.abspath(CONFIG_FILE)
        
        if not os.path.exists(config_path):
            default_config = {
                "root_backup_dir": DEFAULT_ROOT,
                "games": {},
                "version": "4.1"
            }
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            config['root_backup_dir'] = os.path.normpath(config['root_backup_dir'])
            
            cleaned_games = {}
            for game_name, game_config in config['games'].items():
                clean_name = game_name.strip().lower()  # Case-insensitive game name
                game_config['source_path'] = os.path.normpath(game_config['source_path'].strip())
                game_config['backup_dir'] = os.path.normpath(
                    os.path.join(config['root_backup_dir'], clean_name)
                )
                cleaned_games[clean_name] = game_config
            
            config['games'] = cleaned_games
            return config
            
        except Exception as e:
            raise RuntimeError(f"Configuration error: {str(e)}")

    def _save_config(self):
        """Save current configuration to file"""
        config_path = os.path.abspath(CONFIG_FILE)
        try:
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            raise RuntimeError(f"Failed to save config: {str(e)}")

    def _ensure_paths(self):
        """Create all required directories"""
        try:
            os.makedirs(self.config['root_backup_dir'], exist_ok=True)
            for game_config in self.config['games'].values():
                os.makedirs(game_config['backup_dir'], exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"Path creation failed: {str(e)}")

    # ========== GAME MANAGEMENT METHODS ==========

    def add_game(self, game_name, source_path):
        """Add new game to configuration with validation"""
        cleaned_name = game_name.strip().lower()  # Case-insensitive game name

        if cleaned_name in self.config['games']:
            raise ValueError(f"'{cleaned_name}' already exists. Use a unique name.")

        source_path = source_path.strip()
        if not os.path.exists(source_path):
            raise ValueError(f"Source path does not exist: {source_path}")

        self.config['games'][cleaned_name] = {
            'source_path': os.path.normpath(source_path),
            'backup_dir': os.path.normpath(
                os.path.join(self.config['root_backup_dir'], cleaned_name)
            )
        }
        
        self._save_config()
        self._ensure_paths()
        
        return True, f"Successfully added: {cleaned_name}"

    def remove_game(self, game_name):
        """Remove game from configuration"""
        cleaned_name = game_name.strip().lower()  # Case-insensitive game name
        
        try:
            del self.config['games'][cleaned_name]
            self._save_config()
            return True, f"Removed game: {cleaned_name}"
        except KeyError:
            return False, f"Game not found: {cleaned_name}"

    def get_root_directory(self):
        """Get current root backup directory"""
        return self.config['root_backup_dir']

    def list_games(self):
        """Get list of all registered game names"""
        return [name for name in self.config['games'].keys()]

    # ========== BACKUP/RESTORE METHODS ==========

    
    def create_backup(self, game_name):
        """Create backup with validation"""
        try:
            game_name = game_name.strip().lower()  # Case-insensitive game name
            cfg = self.config['games'][game_name]
            
            if not os.path.exists(cfg['source_path']):
                return False, f"Source path not found: {cfg['source_path']}"
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(cfg['backup_dir'], f"backup_{timestamp}")
            
            if os.path.isdir(cfg['source_path']):
                shutil.copytree(cfg['source_path'], backup_dir, dirs_exist_ok=True)
            else:
                os.makedirs(backup_dir, exist_ok=True)
                shutil.copy2(cfg['source_path'], backup_dir)
            
            # Ensure the backup folder itself has the correct timestamp
            current_time = datetime.now().timestamp()
            os.utime(backup_dir, (current_time, current_time))
            
            return True, f"Backup created: {os.path.basename(backup_dir)}"
            
        except KeyError:
            return False, f"Game not found: {game_name}"
        except Exception as e:
            return False, f"Backup failed: {str(e)}"

    def restore_backup(self, game_name, backup_path):
        """Restore backup with validation"""
        try:
            game_name = game_name.strip().lower()  # Case-insensitive game name
            cfg = self.config['games'][game_name]
            backup_path = os.path.normpath(backup_path)
            
            if not os.path.exists(backup_path):
                return False, "Backup file/directory not found"
                
            source = cfg['source_path']
            if os.path.isdir(source):
                shutil.rmtree(source, ignore_errors=True)
            elif os.path.exists(source):
                os.remove(source)
                
            if os.path.isdir(backup_path):
                shutil.copytree(backup_path, source, dirs_exist_ok=True)
            else:
                os.makedirs(os.path.dirname(source), exist_ok=True)
                shutil.copy2(backup_path, source)
                
            return True, "Restore completed successfully"
            
        except KeyError:
            return False, f"Game not found: {game_name}"
        except Exception as e:
            return False, f"Restore failed: {str(e)}"

    def get_backups(self, game_name):
        """Get sorted list of backups"""
        try:
            game_name = game_name.strip().lower()  # Case-insensitive game name
            backup_dir = self.config['games'][game_name]['backup_dir']
            
            if not os.path.exists(backup_dir):
                return []

            backups = []
            for entry in os.listdir(backup_dir):
                if entry.startswith("backup_"):
                    backup_path = os.path.join(backup_dir, entry)
                    if os.path.exists(backup_path):
                        mtime = os.path.getmtime(backup_path)
                        backups.append({
                            'path': backup_path,
                            'name': entry,
                            'timestamp': mtime,
                            'formatted_date': datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                        })
            
            return sorted(backups, key=lambda x: x['timestamp'], reverse=True)
        except Exception:
            return []

    def update_all_backups(self):
        """Update all game backups"""
        results = {}
        for game_name in self.config['games']:
            success, message = self.create_backup(game_name)
            results[game_name] = {'success': success, 'message': message}
        return results

    def restore_all_backups(self):
        """Restore all games to latest backup"""
        results = {}
        for game_name in self.config['games']:
            backups = self.get_backups(game_name)
            if not backups:
                results[game_name] = {'success': False, 'message': "No backups available"}
                continue
                
            success, message = self.restore_backup(game_name, backups[0]['path'])
            results[game_name] = {'success': success, 'message': message}
        return results
    
    def delete_backup(self, game_name, backup_path):
        """Delete a specific backup"""
        try:
            game_name = game_name.strip().lower()  # Case-insensitive game name
            backup_path = os.path.normpath(backup_path)
            if not os.path.exists(backup_path):
                return False, "Backup not found"
            if os.path.isdir(backup_path):
                shutil.rmtree(backup_path)
            else:
                os.remove(backup_path)
            return True, "Backup deleted successfully"
        except Exception as e:
            return False, f"Deletion failed: {str(e)}"
        

    def export_config(self, export_path):
        """Export configuration to specified path"""
        try:
            shutil.copy(CONFIG_FILE, export_path)
            return True, f"Config exported to {export_path}"
        except Exception as e:
            return False, f"Export failed: {str(e)}"

    def import_config(self, import_path):
        """Import configuration from file with validation"""
        try:
            with open(import_path, 'r') as f:
                new_config = json.load(f)
            
            # Basic validation
            required_keys = ['root_backup_dir', 'games', 'version']
            if not all(key in new_config for key in required_keys):
                raise ValueError("Invalid configuration format")
                
            # Preserve current root directory structure
            new_config['root_backup_dir'] = os.path.normpath(new_config['root_backup_dir'])
            
            # Overwrite current config
            self.config = new_config
            self._save_config()
            self._ensure_paths()
            return True, "Config imported successfully"
            
        except Exception as e:
            return False, f"Import failed: {str(e)}"

    def search_save_locations(self, game_name):
        """Generate search URL for save locations"""
        return {
            'search_url': f"{SAVEGAME_PRO_URL}?s={urllib.parse.quote_plus(game_name)}",
            'game': game_name.strip().lower()  # Case-insensitive game name
        }