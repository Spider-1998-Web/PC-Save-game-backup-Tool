import os
import shutil
import webbrowser
from datetime import datetime
import configparser
import sys

# Function to create default config file
def create_default_config():
    config = configparser.ConfigParser()
    
    # Set default values
    config['PATHS'] = {
        'BASE_BACKUP_LOCATION': "C:\\save game",
    }
    
    config['URLS'] = {
        'SAVEGAME_PRO_URL': "https://savegame.pro/"
    }
    
    # Create config directory if it doesn't exist
    config_dir = os.path.dirname(CONFIG_FILE)
    if not os.path.exists(config_dir) and config_dir:
        os.makedirs(config_dir)
    
    # Write config to file
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    
    print(f"Created default configuration file at: {CONFIG_FILE}")
    print("Please edit this file to set your preferred backup location.")
    print("Restart the application after making changes.")
    
    return config

# Set up config file path
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")

# Check if config file exists, create it if not
if not os.path.exists(CONFIG_FILE):
    config = create_default_config()
    print("\nFirst-time setup: Default configuration has been created.")
    print(f"Please edit {CONFIG_FILE} to set your preferred backup location.")
    input("Press Enter to continue...")

# Load configuration
config = configparser.ConfigParser()
config.read(CONFIG_FILE)

# Get configuration values with fallbacks for safety
try:
    BASE_BACKUP_LOCATION = config.get('PATHS', 'BASE_BACKUP_LOCATION')
    SAVEGAME_PRO_URL = config.get('URLS', 'SAVEGAME_PRO_URL')
except (configparser.NoSectionError, configparser.NoOptionError) as e:
    print(f"Error in configuration file: {e}")
    print("Creating new default configuration file...")
    config = create_default_config()
    BASE_BACKUP_LOCATION = config.get('PATHS', 'BASE_BACKUP_LOCATION')
    SAVEGAME_PRO_URL = config.get('URLS', 'SAVEGAME_PRO_URL')

# Verify the backup location exists or can be created
if not os.path.exists(BASE_BACKUP_LOCATION):
    try:
        os.makedirs(BASE_BACKUP_LOCATION)
        print(f"Created backup directory: {BASE_BACKUP_LOCATION}")
    except Exception as e:
        print(f"ERROR: Cannot create backup directory {BASE_BACKUP_LOCATION}: {e}")
        print("Please edit the config.ini file to set a valid backup location.")
        input("Press Enter to exit...")
        sys.exit(1)

# Derived paths
LOGS_ROOT = os.path.join(BASE_BACKUP_LOCATION, "logs")  # Path for logs
SAFETY_BACKUPS_ROOT = os.path.join(LOGS_ROOT, "safety_backups")  # Path for safety backups

def copy_dir_recursively(src, dst):
    """Copy directory contents recursively from src to dst."""
    try:
        if not os.path.exists(src):
            raise FileNotFoundError(f"Source path does not exist: {src}")
            
        if not os.path.exists(dst):
            os.makedirs(dst)
        
        if not os.path.isdir(src):
            raise NotADirectoryError(f"Source is not a directory: {src}")
        
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            
            try:
                if os.path.isdir(s):
                    copy_dir_recursively(s, d)
                else:
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copy2(s, d)
            except Exception as e:
                print(f"Warning: Failed to copy {s}: {e}")
                
    except Exception as e:
        print(f"Error during directory copy: {e}")
        raise

def create_backup(game_title, source_path):
    """Creates a new backup of the game save files."""
    source_path = source_path.strip('"')  # Remove extra quotes around the path

    # Define the backup location for the specific game
    backup_path = os.path.join(BASE_BACKUP_LOCATION, game_title)

    if not os.path.exists(backup_path):
        try:
            os.makedirs(backup_path)
        except Exception as e:
            print(f"Error creating backup directory: {e}")
            return False

    # Verify the source path exists
    if not os.path.exists(source_path):
        print(f"Error: Source path '{source_path}' does not exist.")
        return False

    try:
        # Use the helper function to copy files recursively
        copy_dir_recursively(source_path, backup_path)

        # Create a README file with backup details
        readme_path = os.path.join(backup_path, "README.txt")
        with open(readme_path, "w") as f:
            f.write(f"Game Title: {game_title}\n")
            f.write(f"Original Save Path: {source_path}\n")
            f.write(f"Backup Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        print(f"Backup created successfully for {game_title} ✅")

        # Log the backup event in the centralized log file
        log_backup_event("create", game_title, source_path)
        return True
        
    except Exception as e:
        print(f"Error creating backup: {e}")
        return False

def update_backup(game_title, auto_confirm=False):
    """Updates an existing backup of the game save files."""
    backup_path = os.path.join(BASE_BACKUP_LOCATION, game_title)

    # Check if the backup folder exists
    if not os.path.exists(backup_path):
        print(f"Error: No backup found for {game_title}. Please create a backup first.")
        return False

    # Get the source path from the README file
    readme_path = os.path.join(backup_path, "README.txt")
    source_path = None
    
    if os.path.exists(readme_path):
        with open(readme_path, "r") as f:
            for line in f:
                if "Original Save Path:" in line:
                    source_path = line.strip().replace("Original Save Path: ", "")
                    break
    
    if not source_path:
        print(f"Error: Could not determine the source path for {game_title}.")
        return False
    
    # Confirm the source path with the user if not in auto mode
    if not auto_confirm:
        print(f"Will update backup using source path: {source_path}")
        confirm = input("Is this correct? (y/n): ")
        
        if confirm.lower() != 'y':
            source_path = input("Enter the new source path: ")
            source_path = source_path.strip('"')
    
    # Check if the source path exists
    if not os.path.exists(source_path):
        print(f"Error: Source path {source_path} does not exist.")
        return False

    try:
        # First, create a backup of the current backup (for safety) inside the logs/safety_backups folder
        if not os.path.exists(SAFETY_BACKUPS_ROOT):
            os.makedirs(SAFETY_BACKUPS_ROOT)
            
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        safety_backup_name = f"{game_title}_backup_{timestamp}"
        backup_backup_path = os.path.join(SAFETY_BACKUPS_ROOT, safety_backup_name)
        
        # Use the more robust recursive copy or shutil.copytree with error handling
        try:
            shutil.copytree(backup_path, backup_backup_path)
            print(f"Safety backup created at: {backup_backup_path}")
        except Exception as e:
            print(f"Warning: Could not create safety backup: {e}")
            # Continue anyway as this is just a precaution
        
        # Now update by syncing directories
        sync_directories(source_path, backup_path)

        # Update the README file with the new backup details
        with open(readme_path, "w") as f:
            f.write(f"Game Title: {game_title}\n")
            f.write(f"Original Save Path: {source_path}\n")
            f.write(f"Backup Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        print(f"Backup updated successfully for {game_title} ✅")

        # Log the update event
        log_backup_event("update", game_title, source_path)
        return True
        
    except Exception as e:
        print(f"Error updating backup: {e}")
        return False

def update_all_backups():
    """Updates all available backups."""
    print("\nUpdating all backups...")
    
    if not os.path.exists(BASE_BACKUP_LOCATION):
        print("No backups found.")
        return
        
    backups = [d for d in os.listdir(BASE_BACKUP_LOCATION) 
               if os.path.isdir(os.path.join(BASE_BACKUP_LOCATION, d)) 
               and d != "logs" 
               and not d.endswith("_backup_")]
    
    if not backups:
        print("No backups found.")
        return
    
    success_count = 0
    failed_count = 0
    
    print(f"Found {len(backups)} backups to update")
    confirm = input("Do you want to proceed with updating all backups? (y/n): ")
    
    if confirm.lower() != 'y':
        print("Update all operation cancelled.")
        return
    
    for game_title in backups:
        print(f"\nProcessing: {game_title}")
        success = update_backup(game_title, auto_confirm=True)
        if success:
            success_count += 1
        else:
            failed_count += 1
    
    print("\n===== Update All Summary =====")
    print(f"Total backups: {len(backups)}")
    print(f"Successfully updated: {success_count}")
    print(f"Failed updates: {failed_count}")
    
    # Log the update all event
    log_backup_event("update_all", "ALL_GAMES", "multiple")

def sync_directories(source, target):
    """Synchronize target directory with source directory."""
    try:
        if not os.path.exists(source):
            raise FileNotFoundError(f"Source path does not exist: {source}")
            
        if not os.path.exists(target):
            os.makedirs(target)
            
        # Create sets of all files in source and target
        source_items = set()
        for dp, dn, filenames in os.walk(source):
            for f in filenames:
                source_items.add(os.path.relpath(os.path.join(dp, f), source))
        
        target_items = set()
        for dp, dn, filenames in os.walk(target):
            for f in filenames:
                target_items.add(os.path.relpath(os.path.join(dp, f), target))
        
        # Skip our metadata files
        metadata_files = {"README.txt"}
        target_items = {item for item in target_items if item not in metadata_files}
        
        # Copy new and modified files from source to target
        for item in source_items:
            source_item = os.path.join(source, item)
            target_item = os.path.join(target, item)
            
            try:
                # Ensure the directory exists
                os.makedirs(os.path.dirname(target_item), exist_ok=True)
                
                # Copy new or modified files
                if item not in target_items or os.path.getmtime(source_item) > os.path.getmtime(target_item):
                    shutil.copy2(source_item, target_item)
            except Exception as e:
                print(f"Warning: Failed to copy {source_item}: {e}")
        
        # Remove files from target that don't exist in source
        for item in target_items:
            if item not in source_items and item not in metadata_files:
                try:
                    target_item = os.path.join(target, item)
                    os.remove(target_item)
                except Exception as e:
                    print(f"Warning: Failed to remove {target_item}: {e}")
        
        # Clean up empty directories
        for root, dirs, files in os.walk(target, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(dir_path):  # Check if directory is empty
                        os.rmdir(dir_path)
                except Exception as e:
                    print(f"Warning: Failed to remove empty directory {dir_path}: {e}")
                    
    except Exception as e:
        print(f"Error during directory synchronization: {e}")
        raise

def restore_backup(game_title, auto_confirm=False):
    """Restores a backup of the game save files."""
    backup_path = os.path.join(BASE_BACKUP_LOCATION, game_title)

    if not os.path.exists(backup_path):
        print(f"Error: No backup found for {game_title}.")
        return False

    # Get the source path from the README file
    readme_path = os.path.join(backup_path, "README.txt")
    source_path = None
    
    if os.path.exists(readme_path):
        with open(readme_path, "r") as f:
            for line in f:
                if "Original Save Path:" in line:
                    source_path = line.strip().replace("Original Save Path: ", "")
                    break
    
    if not source_path:
        print(f"Error: Could not determine the source path for {game_title}.")
        return False
    
    # Confirm with the user before proceeding if not in auto mode
    if not auto_confirm:
        print(f"This will restore files to: {source_path}")
        confirm = input("Are you sure you want to proceed? (y/n): ")
        
        if confirm.lower() != 'y':
            print("Restore operation cancelled.")
            return False
    
    try:
        # Create a backup of the current save before restoring (in safety_backups folder)
        if not os.path.exists(SAFETY_BACKUPS_ROOT):
            os.makedirs(SAFETY_BACKUPS_ROOT)
            
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        if os.path.exists(source_path):
            # Extract just the folder name from the source path for the backup name
            source_folder_name = os.path.basename(source_path.rstrip('\\'))
            if not source_folder_name:  # In case the path ends with a separator
                source_folder_name = os.path.basename(os.path.dirname(source_path))
                
            safety_backup_name = f"{source_folder_name}_before_restore_{timestamp}"
            backup_before_restore = os.path.join(SAFETY_BACKUPS_ROOT, safety_backup_name)
            
            try:
                shutil.copytree(source_path, backup_before_restore)
                print(f"Created safety backup at: {backup_before_restore}")
            except Exception as e:
                print(f"Warning: Could not create safety backup: {e}")
                
                # Confirm if the user wants to continue without a safety backup
                if not auto_confirm:
                    continue_without_safety = input("Continue without safety backup? (y/n): ")
                    if continue_without_safety.lower() != 'y':
                        print("Restore operation cancelled.")
                        return False
        
        # Now restore the backup folder to the original location
        # Make sure target directory exists
        try:
            os.makedirs(source_path, exist_ok=True)
        except Exception as e:
            print(f"Error creating target directory: {e}")
            return False
        
        # Copy all files except our metadata files
        for item in os.listdir(backup_path):
            if item == "README.txt":
                continue
                
            backup_item = os.path.join(backup_path, item)
            target_item = os.path.join(source_path, item)
            
            try:
                if os.path.isdir(backup_item):
                    # If directory exists, remove it first to ensure clean copy
                    if os.path.exists(target_item):
                        shutil.rmtree(target_item)
                    shutil.copytree(backup_item, target_item)
                elif os.path.isfile(backup_item):
                    # Make sure the directory exists for the target file
                    os.makedirs(os.path.dirname(target_item), exist_ok=True)
                    shutil.copy2(backup_item, target_item)
            except Exception as e:
                print(f"Warning: Failed to restore {backup_item}: {e}")

        print(f"Backup restored successfully for {game_title} ✅")
        
        # Log the restore event
        log_backup_event("restore", game_title, source_path)
        return True
        
    except Exception as e:
        print(f"Error restoring backup: {e}")
        return False

def restore_all_backups():
    """Restores all available backups."""
    print("\nRestoring all backups...")
    
    if not os.path.exists(BASE_BACKUP_LOCATION):
        print("No backups found.")
        return
        
    backups = [d for d in os.listdir(BASE_BACKUP_LOCATION) 
               if os.path.isdir(os.path.join(BASE_BACKUP_LOCATION, d)) 
               and d != "logs" 
               and not d.endswith("_backup_")]
    
    if not backups:
        print("No backups found.")
        return
    
    success_count = 0
    failed_count = 0
    
    print(f"Found {len(backups)} backups to restore")
    print("⚠️ WARNING: This will restore ALL game saves to their original locations! ⚠️")
    confirm = input("Are you absolutely sure you want to proceed with restoring all backups? (y/n): ")
    
    if confirm.lower() != 'y':
        print("Restore all operation cancelled.")
        return
    
    # Double-confirm since this is a potentially destructive operation
    confirm = input("Type 'RESTORE ALL' to confirm: ")
    if confirm != "RESTORE ALL":
        print("Restore all operation cancelled.")
        return
    
    for game_title in backups:
        print(f"\nProcessing: {game_title}")
        success = restore_backup(game_title, auto_confirm=True)
        if success:
            success_count += 1
        else:
            failed_count += 1
    
    print("\n===== Restore All Summary =====")
    print(f"Total backups: {len(backups)}")
    print(f"Successfully restored: {success_count}")
    print(f"Failed restores: {failed_count}")
    
    # Log the restore all event
    log_backup_event("restore_all", "ALL_GAMES", "multiple")

def log_backup_event(action_type, game_title, source_path):
    """Log backup events to a centralized log file."""
    try:
        if not os.path.exists(LOGS_ROOT):
            os.makedirs(LOGS_ROOT)
            
        # Use a single log file for all games, but categorize by action type
        log_file = os.path.join(LOGS_ROOT, "backup_log.txt")
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(log_file, "a") as log:
            log.write(f"[{timestamp}] {action_type.upper()}: {game_title} | Path: {source_path}\n")
    except Exception as e:
        print(f"Warning: Failed to log backup event: {e}")

def list_backups():
    """List all available backups."""
    print("\nAvailable Backups:")
    print("-----------------")
    
    if not os.path.exists(BASE_BACKUP_LOCATION):
        print("No backups found.")
        return
        
    try:
        backups = [d for d in os.listdir(BASE_BACKUP_LOCATION) 
                   if os.path.isdir(os.path.join(BASE_BACKUP_LOCATION, d)) 
                   and d != "logs" 
                   and not d.endswith("_backup_")]
        
        if not backups:
            print("No backups found.")
            return
            
        for i, backup in enumerate(backups, 1):
            backup_path = os.path.join(BASE_BACKUP_LOCATION, backup)
            readme_path = os.path.join(backup_path, "README.txt")
            
            backup_date = "Unknown"
            source_path = "Unknown"
            
            if os.path.exists(readme_path):
                try:
                    with open(readme_path, "r") as f:
                        lines = f.readlines()
                        for line in lines:
                            if "Backup Date:" in line:
                                backup_date = line.strip().replace("Backup Date: ", "")
                            if "Original Save Path:" in line:
                                source_path = line.strip().replace("Original Save Path: ", "")
                except Exception as e:
                    print(f"Warning: Could not read README file for {backup}: {e}")
            
            print(f"{i}. {backup}")
            print(f"   Date: {backup_date}")
            print(f"   Path: {source_path}")
            print()
    except Exception as e:
        print(f"Error listing backups: {e}")

def view_logs():
    """View the backup logs."""
    if not os.path.exists(LOGS_ROOT):
        print("No logs found.")
        return
        
    log_file = os.path.join(LOGS_ROOT, "backup_log.txt")
    
    if not os.path.exists(log_file):
        print("No logs found.")
        return
        
    print("\nBackup Logs:")
    print("------------")
    
    try:
        with open(log_file, "r") as f:
            logs = f.readlines()
            
        # Display the most recent logs first (limited to last 20)
        for log in logs[-20:][::-1]:
            print(log.strip())
            
        print(f"\nShowing last {min(20, len(logs))} log entries. Total entries: {len(logs)}")
    except Exception as e:
        print(f"Error viewing logs: {e}")

def list_safety_backups():
    """List all safety backups."""
    print("\nSafety Backups:")
    print("--------------")
    
    if not os.path.exists(SAFETY_BACKUPS_ROOT):
        print("No safety backups found.")
        return
        
    try:
        backups = [d for d in os.listdir(SAFETY_BACKUPS_ROOT) 
                   if os.path.isdir(os.path.join(SAFETY_BACKUPS_ROOT, d))]
        
        if not backups:
            print("No safety backups found.")
            return
            
        for i, backup in enumerate(backups, 1):
            backup_path = os.path.join(SAFETY_BACKUPS_ROOT, backup)
            try:
                creation_time = datetime.fromtimestamp(os.path.getctime(backup_path)).strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"{i}. {backup}")
                print(f"   Created: {creation_time}")
                print()
            except Exception as e:
                print(f"{i}. {backup}")
                print(f"   Created: Unknown (Error: {e})")
                print()
    except Exception as e:
        print(f"Error listing safety backups: {e}")

def open_savegame_pro():
    """Open the savegame.pro website in the default browser."""
    print("\nOpening savegame.pro in your default browser...")
    try:
        webbrowser.open(SAVEGAME_PRO_URL)
        print("Website opened successfully ✅")
    except Exception as e:
        print(f"Error opening website: {e}")
        print(f"Please visit {SAVEGAME_PRO_URL} manually")

def search_game_saves():
    """Search for a game on savegame.pro."""
    game_name = input("\nEnter game name to search on savegame.pro: ")
    if game_name.strip():
        search_url = f"{SAVEGAME_PRO_URL}?s={game_name.replace(' ', '+')}"
        try:
            print(f"Searching for '{game_name}' on savegame.pro...")
            webbrowser.open(search_url)
            print("Search results opened successfully ✅")
        except Exception as e:
            print(f"Error opening search: {e}")
            print(f"Please visit {search_url} manually")
    else:
        print("Search cancelled. No game name provided.")

def check_create_dir(path):
    """Check if a directory exists and create it if it doesn't."""
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            return True
        except Exception as e:
            print(f"Error creating directory {path}: {e}")
            return False
    return True

def delete_backup(game_title=None):
    """Permanently delete a backup and all related safety backups for a game."""
    if not game_title:
        # List available backups first
        list_backups()
        game_title = input("Enter the game title to delete: ")
    
    if not game_title:
        print("No game title provided. Operation cancelled.")
        return False
        
    backup_path = os.path.join(BASE_BACKUP_LOCATION, game_title)
    
    # Check if the backup folder exists
    if not os.path.exists(backup_path):
        print(f"Error: No backup found for {game_title}.")
        return False
    
    # Confirm with the user
    confirm = input(f"Are you sure you want to PERMANENTLY delete the backup for '{game_title}' and all related safety backups? (y/n): ")
    if confirm.lower() != 'y':
        print("Delete operation cancelled.")
        return False
    
    # Double-confirm for safety since this is permanent
    confirm = input("This action CANNOT be undone. Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("Delete operation cancelled.")
        return False
    
    try:
        # 1. First delete the main backup
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)
            print(f"Deleted main backup for {game_title} ✅")
        
        # 2. Find and delete all related safety backups
        deleted_safety_count = 0
        if os.path.exists(SAFETY_BACKUPS_ROOT):
            for backup in os.listdir(SAFETY_BACKUPS_ROOT):
                backup_path = os.path.join(SAFETY_BACKUPS_ROOT, backup)
                # Check if the backup name starts with the game title
                if os.path.isdir(backup_path) and backup.startswith(game_title + "_"):
                    try:
                        shutil.rmtree(backup_path)
                        deleted_safety_count += 1
                    except Exception as e:
                        print(f"Warning: Could not delete safety backup {backup}: {e}")
        
        if deleted_safety_count > 0:
            print(f"Deleted {deleted_safety_count} related safety backup(s) ✅")
        
        # 3. Check for any backups in the deleted_backups directory
        deleted_backups_dir = os.path.join(SAFETY_BACKUPS_ROOT, "deleted_backups")
        if os.path.exists(deleted_backups_dir):
            deleted_backup_count = 0
            for backup in os.listdir(deleted_backups_dir):
                backup_path = os.path.join(deleted_backups_dir, backup)
                if os.path.isdir(backup_path) and backup.startswith(game_title + "_"):
                    try:
                        shutil.rmtree(backup_path)
                        deleted_backup_count += 1
                    except Exception as e:
                        print(f"Warning: Could not delete from deleted_backups: {backup}: {e}")
            
            if deleted_backup_count > 0:
                print(f"Deleted {deleted_backup_count} backup(s) from deleted_backups folder ✅")
        
        print(f"All backups for {game_title} have been permanently deleted ✅")
        
        # Log the deletion event
        log_backup_event("permanent_delete", game_title, "All related backups deleted")
        return True
        
    except Exception as e:
        print(f"Error deleting backup: {e}")
        return False

def main():
    """Main function for user interaction."""
    print("================================================")
    print(" Save Game  Backup Management System")
    print("================================================")
    
    # Check base directories
    base_dirs_ok = True
    for dir_path in [BASE_BACKUP_LOCATION, LOGS_ROOT, SAFETY_BACKUPS_ROOT]:
        if not check_create_dir(dir_path):
            base_dirs_ok = False
            
    if not base_dirs_ok:
        print("Warning: Some base directories could not be created. Some features may not work properly.")
    
    while True:
        print("\nOptions:")
        print("1. Create Backup")
        print("2. Update Backup")
        print("3. Restore Backup")
        print("4. Update All Backups")
        print("5. Restore All Backups")
        print("6. List Backups")
        print("7. List Safety Backups")
        print("8. View Logs")
        print("9. Open SaveGame.pro Website")
        print("D. Delete Backup")
        print("S. Search Game on SaveGame.pro")
        print("Q. Exit")

        try:
            choice = input("\nEnter your choice: ").strip().lower()

            if choice == "1":
                game_title = input("Enter the game title: ")
                # Offer to search for save location on savegame.pro
                search_save = input("Do you want to look up the save location on savegame.pro? (y/n): ")
                if search_save.lower() == 'y':
                    search_url = f"{SAVEGAME_PRO_URL}?s={game_title.replace(' ', '+')}"
                    try:
                        print(f"Searching for '{game_title}' on savegame.pro...")
                        webbrowser.open(search_url)
                        print("Please check your browser for the save location")
                    except Exception as e:
                        print(f"Error opening search: {e}")
                        print(f"Please visit {search_url} manually")
                
                source_path = input("Enter the source folder path: ")
                create_backup(game_title, source_path)

            elif choice == "2":
                list_backups()
                game_title = input("Enter the game title to update: ")
                update_backup(game_title)

            elif choice == "3":
                list_backups()
                game_title = input("Enter the game title to restore: ")
                restore_backup(game_title)
                
            elif choice == "4":
                update_all_backups()

            elif choice == "5":
                restore_all_backups()

            elif choice == "6":
                list_backups()

            elif choice == "7":
                list_safety_backups()
                
            elif choice == "8":
                view_logs()
                
            elif choice == "9":
                open_savegame_pro()
                
            elif choice == "d":
                delete_backup()
                
            elif choice == "s":
                search_game_saves()

            elif choice == "q":
                print("Thank you for using the Backup Management System. Goodbye!")
                break
            else:
                print("Invalid choice, please try again.")
                
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print("Please try again.")

if __name__ == "__main__":
    try:
        # Create base directories if they don't exist
        for dir_path in [BASE_BACKUP_LOCATION, LOGS_ROOT, SAFETY_BACKUPS_ROOT]:
            check_create_dir(dir_path)
        
        # Display a tip about savegame.pro at startup
        print("\nTIP: Use options 9 or 10 to quickly access savegame.pro for finding game save locations\n")
        
        main()
    except Exception as e:
        print(f"Fatal error: {e}")
        print("The program will now exit.")
        input("Press Enter to continue...")