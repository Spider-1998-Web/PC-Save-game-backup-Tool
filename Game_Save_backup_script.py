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

def main(gui_mode=False):
    """Main function for user interaction."""
    if gui_mode:
        # If GUI mode is selected, start the GUI
        start_gui()
        return
        
    # Original command-line interface
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
        print("G. Switch to GUI Mode")
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
                
            elif choice == "g":
                print("Switching to GUI mode...")
                start_gui()
                break

            elif choice == "q":
                print("Thank you for using the Backup Management System. Goodbye!")
                break
            else:
                print("Invalid choice, please try again.")
                
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print("Please try again.")

# GUI Implementation
def start_gui():
    """Start the GUI interface for the backup tool."""
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
    from tkinter import simpledialog
    import threading
    import queue
    import functools
    
    # Thread-safe function executor
    def run_in_thread(func, success_msg=None):
        # Create a queue for console output
        console_queue = queue.Queue()
        # Create a flag to signal when the operation is done
        done_flag = threading.Event()
        # Result storage
        result_container = {"success": False, "error": None}
        
        # Text redirector for capturing console output
        class ThreadSafeConsoleRedirector:
            def __init__(self, queue_obj):
                self.queue = queue_obj
                
            def write(self, string):
                self.queue.put(string)
                
            def flush(self):
                pass
        
        # Function to run in a thread
        def thread_target():
            # Redirect stdout
            orig_stdout = sys.stdout
            sys.stdout = ThreadSafeConsoleRedirector(console_queue)
            
            try:
                # Call the target function
                result = func()
                result_container["success"] = result if result is not None else True
            except Exception as e:
                result_container["error"] = str(e)
                print(f"Error: {e}")
            finally:
                # Restore stdout
                sys.stdout = orig_stdout
                # Signal that we're done
                done_flag.set()
        
        # Start the thread
        thread = threading.Thread(target=thread_target)
        thread.daemon = True
        thread.start()
        
        # Function to update console and check if the thread is done
        def check_thread():
            # Process all messages in the queue
            while not console_queue.empty():
                try:
                    message = console_queue.get_nowait()
                    console.configure(state="normal")
                    console.insert(tk.END, message)
                    console.see(tk.END)
                    console.configure(state="disabled")
                    console_queue.task_done()
                except queue.Empty:
                    break
            
            # Check if the thread is done
            if done_flag.is_set():
                if result_container["error"]:
                    messagebox.showerror("Error", f"Operation failed: {result_container['error']}")
                elif success_msg and result_container["success"]:
                    messagebox.showinfo("Success", success_msg)
                return  # Stop checking
            
            # Schedule the next check
            root.after(100, check_thread)
        
        # Start checking
        root.after(100, check_thread)
    
    # Create the main window
    root = tk.Tk()
    root.title("Save Game Backup Tool")
    root.geometry("800x600")
    root.minsize(600, 500)
    
    # Configure style
    style = ttk.Style()
    style.configure("TButton", padding=6, relief="flat", background="#ccc")
    style.configure("TFrame", background="#f0f0f0")
    style.configure("TLabel", background="#f0f0f0", font=("Arial", 10))
    style.configure("Header.TLabel", font=("Arial", 14, "bold"))
    
    # Create main frame
    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Header
    header_frame = ttk.Frame(main_frame)
    header_frame.pack(fill=tk.X, pady=(0, 10))
    
    header_label = ttk.Label(header_frame, text="Save Game Backup Tool", style="Header.TLabel")
    header_label.pack(side=tk.LEFT)
    
    config_path_label = ttk.Label(header_frame, text=f"Config: {CONFIG_FILE}")
    config_path_label.pack(side=tk.RIGHT)
    
    # Backup location info
    backup_info_frame = ttk.Frame(main_frame)
    backup_info_frame.pack(fill=tk.X, pady=(0, 10))
    
    backup_path_label = ttk.Label(backup_info_frame, text=f"Backup Location: {BASE_BACKUP_LOCATION}")
    backup_path_label.pack(side=tk.LEFT)
    
    def edit_config():
        try:
            if os.path.exists(CONFIG_FILE):
                # Use the appropriate system command to open the config file
                import platform
                if platform.system() == 'Windows':
                    os.startfile(CONFIG_FILE)
                elif platform.system() == 'Darwin':  # macOS
                    os.system(f'open "{CONFIG_FILE}"')
                else:  # Linux
                    os.system(f'xdg-open "{CONFIG_FILE}"')
            else:
                messagebox.showerror("Error", "Config file not found!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open config file: {e}")
    
    edit_config_btn = ttk.Button(backup_info_frame, text="Edit Config", command=edit_config)
    edit_config_btn.pack(side=tk.RIGHT)
    
    # Split the interface into two parts
    paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
    paned_window.pack(fill=tk.BOTH, expand=True)
    
    # Left panel - Buttons
    left_frame = ttk.Frame(paned_window)
    paned_window.add(left_frame, weight=1)
    
    # Right panel - Console output
    right_frame = ttk.Frame(paned_window)
    paned_window.add(right_frame, weight=2)
    
    # Console output area with title
    ttk.Label(right_frame, text="Console Output:").pack(anchor=tk.W, padx=10, pady=(10, 0))
    
    console_frame = ttk.Frame(right_frame, borderwidth=1, relief=tk.SUNKEN)
    console_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    console = scrolledtext.ScrolledText(console_frame, wrap=tk.WORD, font=("Courier", 9))
    console.pack(fill=tk.BOTH, expand=True)
    console.configure(state="disabled")
    
    # Function to populate backup list and return selected title
    def select_backup_dialog(title="Select Backup", allow_cancel=True):
        result = {"selected": None}
        
        dialog = tk.Toplevel(root)
        dialog.title(title)
        dialog.geometry("500x400")
        dialog.transient(root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Available Backups:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        
        # Create listbox with scrollbar
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        backup_list = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("Courier", 10))
        backup_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=backup_list.yview)
        
        # Get backups
        backups = []
        if not os.path.exists(BASE_BACKUP_LOCATION):
            backup_list.insert(tk.END, "No backups found")
        else:
            backups = [d for d in os.listdir(BASE_BACKUP_LOCATION) 
                       if os.path.isdir(os.path.join(BASE_BACKUP_LOCATION, d)) 
                       and d != "logs" 
                       and not d.endswith("_backup_")]
            
            if not backups:
                backup_list.insert(tk.END, "No backups found")
            else:
                for i, backup in enumerate(backups, 1):
                    backup_path = os.path.join(BASE_BACKUP_LOCATION, backup)
                    readme_path = os.path.join(backup_path, "README.txt")
                    
                    backup_date = "Unknown"
                    
                    if os.path.exists(readme_path):
                        try:
                            with open(readme_path, "r") as f:
                                lines = f.readlines()
                                for line in lines:
                                    if "Backup Date:" in line:
                                        backup_date = line.strip().replace("Backup Date: ", "")
                                        break
                        except Exception:
                            pass
                    
                    backup_list.insert(tk.END, f"{backup} - {backup_date}")
                    backup_list.itemconfig(i-1, {'bg': '#f0f0f0' if i % 2 == 0 else '#ffffff'})
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        def on_select():
            selection = backup_list.curselection()
            if selection and backups:
                index = selection[0]
                if index < len(backups):
                    result["selected"] = backups[index]
            dialog.destroy()
        
        select_btn = ttk.Button(button_frame, text="Select", command=on_select)
        select_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        if allow_cancel:
            cancel_btn = ttk.Button(button_frame, text="Cancel", command=dialog.destroy)
            cancel_btn.pack(side=tk.RIGHT)
        
        # Wait for dialog to close
        dialog.wait_window()
        return result["selected"]
    
    # Create buttons with consistent sizing
    button_frame = ttk.Frame(left_frame)
    button_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    button_width = 20
    
    # Create backup button and related functions
    def on_create_backup():
        dialog = tk.Toplevel(root)
        dialog.title("Create Backup")
        dialog.geometry("500x300")
        dialog.transient(root)
        dialog.grab_set()
        
        # Game title
        ttk.Label(dialog, text="Game Title:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        title_entry = ttk.Entry(dialog, width=50)
        title_entry.pack(fill=tk.X, padx=10, pady=(0, 10))
        title_entry.focus_set()
        
        # Source path
        ttk.Label(dialog, text="Source Folder:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        path_frame = ttk.Frame(dialog)
        path_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        path_entry = ttk.Entry(path_frame, width=50)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def browse_folder():
            folder = filedialog.askdirectory(title="Select Save Game Folder")
            if folder:
                path_entry.delete(0, tk.END)
                path_entry.insert(0, folder)
        
        browse_btn = ttk.Button(path_frame, text="Browse...", command=browse_folder)
        browse_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # SaveGame.pro search option
        def search_on_savegame_pro():
            game_title = title_entry.get().strip()
            if game_title:
                search_url = f"{SAVEGAME_PRO_URL}?s={game_title.replace(' ', '+')}"
                try:
                    webbrowser.open(search_url)
                    messagebox.showinfo("Search", f"Searching for '{game_title}' on SaveGame.pro")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to open browser: {e}")
            else:
                messagebox.showwarning("Warning", "Please enter a game title first")
        
        search_btn = ttk.Button(dialog, text="Search on SaveGame.pro", command=search_on_savegame_pro)
        search_btn.pack(anchor=tk.W, padx=10, pady=(0, 10))
        
        # Create button
        def do_create_backup():
            game_title = title_entry.get().strip()
            source_path = path_entry.get().strip()
            
            if not game_title:
                messagebox.showwarning("Warning", "Please enter a game title")
                return
                
            if not source_path:
                messagebox.showwarning("Warning", "Please select a source folder")
                return
            
            dialog.destroy()
            
            # Use the thread-safe runner
            run_in_thread(
                lambda: create_backup(game_title, source_path),
                f"Backup created successfully for {game_title}"
            )
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(10, 10))
        
        create_btn = ttk.Button(button_frame, text="Create Backup", command=do_create_backup)
        create_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT)
    
    # Update backup function
    def on_update_backup():
        game_title = select_backup_dialog("Select Backup to Update")
        if game_title:
            run_in_thread(
                lambda: update_backup(game_title, auto_confirm=True),
                f"Backup updated successfully for {game_title}"
            )
    
    # Restore backup function
    def on_restore_backup():
        game_title = select_backup_dialog("Select Backup to Restore")
        if game_title:
            confirm = messagebox.askyesno("Confirm Restore", 
                                         f"Are you sure you want to restore the backup for {game_title}?\n\n"
                                         "This will overwrite the current save files.")
            if confirm:
                run_in_thread(
                    lambda: restore_backup(game_title, auto_confirm=True),
                    f"Backup restored successfully for {game_title}"
                )
    
    # Delete backup function
    def on_delete_backup():
        game_title = select_backup_dialog("Select Backup to Delete")
        if game_title:
            confirm = messagebox.askyesno("Confirm Delete", 
                                         f"Are you sure you want to DELETE the backup for {game_title}?\n\n"
                                         "This action cannot be undone!")
            if confirm:
                confirm2 = simpledialog.askstring("Final Confirmation", 
                                                "Type DELETE to confirm:")
                
                if confirm2 == "DELETE":
                    run_in_thread(
                        lambda: delete_backup(game_title),
                        f"Backup deleted successfully for {game_title}"
                    )
                else:
                    messagebox.showinfo("Cancelled", "Delete operation cancelled.")
    
    # Function for update all backups with modified behavior for GUI
    def gui_update_all_backups():
        """Updates all available backups (GUI version without confirmation prompt)."""
        if not os.path.exists(BASE_BACKUP_LOCATION):
            print("No backups found.")
            return False
            
        backups = [d for d in os.listdir(BASE_BACKUP_LOCATION) 
                  if os.path.isdir(os.path.join(BASE_BACKUP_LOCATION, d)) 
                  and d != "logs" 
                  and not d.endswith("_backup_")]
        
        if not backups:
            print("No backups found.")
            return False
        
        success_count = 0
        failed_count = 0
        
        print(f"Found {len(backups)} backups to update")
        print("Starting update operation...")
        
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
        
        return success_count > 0
    
    # Function for restore all backups with modified behavior for GUI
    def gui_restore_all_backups():
        """Restores all available backups (GUI version without confirmation prompt)."""
        if not os.path.exists(BASE_BACKUP_LOCATION):
            print("No backups found.")
            return False
            
        backups = [d for d in os.listdir(BASE_BACKUP_LOCATION) 
                  if os.path.isdir(os.path.join(BASE_BACKUP_LOCATION, d)) 
                  and d != "logs" 
                  and not d.endswith("_backup_")]
        
        if not backups:
            print("No backups found.")
            return False
        
        success_count = 0
        failed_count = 0
        
        print(f"Found {len(backups)} backups to restore")
        print("Starting restore operation...")
        
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
        
        return success_count > 0
    
    # Function for update all backups
    def on_update_all():
        confirm = messagebox.askyesno("Confirm Update All", 
                                     "Are you sure you want to update ALL backups?\n\n"
                                     "This will update all game save backups with their current versions.")
        if confirm:
            run_in_thread(gui_update_all_backups, "All backups have been updated successfully")
    
    # Function for restore all backups
    def on_restore_all():
        confirm = messagebox.askyesno("Confirm Restore All", 
                                    "⚠️ WARNING: This will restore ALL game saves to their original locations! ⚠️\n\n"
                                    "Are you absolutely sure you want to proceed?")
        if confirm:
            confirm2 = simpledialog.askstring("Final Confirmation", 
                                          "Type 'RESTORE ALL' to confirm:")
            
            if confirm2 == "RESTORE ALL":
                run_in_thread(gui_restore_all_backups, "All backups have been restored successfully")
    
    # Create all the buttons
    create_backup_btn = ttk.Button(button_frame, text="Create Backup", width=button_width, command=on_create_backup)
    create_backup_btn.pack(fill=tk.X, pady=(0, 5))
    
    update_backup_btn = ttk.Button(button_frame, text="Update Backup", width=button_width, command=on_update_backup)
    update_backup_btn.pack(fill=tk.X, pady=(0, 5))
    
    restore_backup_btn = ttk.Button(button_frame, text="Restore Backup", width=button_width, command=on_restore_backup)
    restore_backup_btn.pack(fill=tk.X, pady=(0, 5))
    
    update_all_btn = ttk.Button(button_frame, text="Update All Backups", width=button_width, command=on_update_all)
    update_all_btn.pack(fill=tk.X, pady=(0, 5))
    
    restore_all_btn = ttk.Button(button_frame, text="Restore All Backups", width=button_width, command=on_restore_all)
    restore_all_btn.pack(fill=tk.X, pady=(0, 5))
    
    list_backups_btn = ttk.Button(button_frame, text="List Backups", width=button_width, 
                                command=lambda: select_backup_dialog("Backup List", allow_cancel=True))
    list_backups_btn.pack(fill=tk.X, pady=(0, 5))
    
    # Function to view logs
    def on_view_logs():
        log_file = os.path.join(LOGS_ROOT, "backup_log.txt")
        if not os.path.exists(log_file):
            messagebox.showinfo("Logs", "No logs found.")
            return
            
        dialog = tk.Toplevel(root)
        dialog.title("Backup Logs")
        dialog.geometry("700x500")
        dialog.transient(root)
        
        log_text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=("Courier", 10))
        log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Read logs
        try:
            with open(log_file, "r") as f:
                logs = f.readlines()
                
            # Display the most recent logs first
            for log in logs[-100:][::-1]:
                log_text.insert(tk.END, log)
                
            log_text.insert(tk.END, f"\nShowing last {min(100, len(logs))} log entries. Total entries: {len(logs)}")
            log_text.configure(state="disabled")  # Make read-only
                
        except Exception as e:
            log_text.insert(tk.END, f"Error viewing logs: {e}")
    
    view_logs_btn = ttk.Button(button_frame, text="View Logs", width=button_width, command=on_view_logs)
    view_logs_btn.pack(fill=tk.X, pady=(0, 5))
    
    # Function to open SaveGame.pro
    def on_open_savegame_pro():
        try:
            webbrowser.open(SAVEGAME_PRO_URL)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open website: {e}")
    
    open_savegame_btn = ttk.Button(button_frame, text="Open SaveGame.pro", width=button_width, command=on_open_savegame_pro)
    open_savegame_btn.pack(fill=tk.X, pady=(0, 5))
    
    # Function to search on SaveGame.pro
    def on_search_game():
        game_name = simpledialog.askstring("Search Game", "Enter game name to search:")
        if game_name and game_name.strip():
            search_url = f"{SAVEGAME_PRO_URL}?s={game_name.replace(' ', '+')}"
            try:
                webbrowser.open(search_url)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open search: {e}")
    
    search_game_btn = ttk.Button(button_frame, text="Search Game", width=button_width, command=on_search_game)
    search_game_btn.pack(fill=tk.X, pady=(0, 5))
    
    delete_backup_btn = ttk.Button(button_frame, text="Delete Backup", width=button_width, command=on_delete_backup)
    delete_backup_btn.pack(fill=tk.X, pady=(0, 5))
    
    # Switch to CLI mode button
    def switch_to_cli():
        root.destroy()
        main(gui_mode=False)
    
    cli_mode_btn = ttk.Button(button_frame, text="Switch to CLI Mode", width=button_width, command=switch_to_cli)
    cli_mode_btn.pack(fill=tk.X, pady=(20, 5))
    
    # Status bar
    status_bar = ttk.Label(main_frame, text=f"Backup Location: {BASE_BACKUP_LOCATION}", relief=tk.SUNKEN, anchor=tk.W)
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Set minimum size for each panel
    paned_window.paneconfig(left_frame, minsize=200)
    paned_window.paneconfig(right_frame, minsize=300)
    
    # Welcome message in console
    console.configure(state="normal")
    console.insert(tk.END, "Welcome to Save Game Backup Tool!\n")
    console.insert(tk.END, "==============================\n\n")
    console.insert(tk.END, f"Base Backup Location: {BASE_BACKUP_LOCATION}\n")
    console.insert(tk.END, f"Config File: {CONFIG_FILE}\n\n")
    console.insert(tk.END, "Select an operation from the buttons on the left.\n")
    console.insert(tk.END, "Console output will appear here.\n")
    console.configure(state="disabled")
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    try:
        # Create base directories if they don't exist
        for dir_path in [BASE_BACKUP_LOCATION, LOGS_ROOT, SAFETY_BACKUPS_ROOT]:
            check_create_dir(dir_path)
        
        # Check for command line arguments
        import sys
        gui_mode = "--gui" in sys.argv
        
        if gui_mode:
            # Skip the tip in GUI mode
            main(gui_mode=True)
        else:
            # Display a tip about savegame.pro at startup in CLI mode
            print("\nTIP: Use options 9 or 10 to quickly access savegame.pro for finding game save locations\n")
            main(gui_mode=False)
            
    except Exception as e:
        print(f"Fatal error: {e}")
        print("The program will now exit.")
        input("Press Enter to continue...")