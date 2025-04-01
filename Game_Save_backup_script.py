import os
import shutil
import webbrowser
from datetime import datetime
import configparser
import sys
import subprocess
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import queue
import functools
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import pickle
import io

# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_google_drive_service():
    """Get or create Google Drive service with authentication."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_path, folder_name=None):
    """Upload a file or folder to Google Drive."""
    try:
        service = get_google_drive_service()
        print(f"Connected to Google Drive API")
        
        # Create folder if specified
        folder_id = None
        if folder_name:
            print(f"Creating folder: {folder_name}")
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            folder_id = folder.get('id')
            print(f"Created folder with ID: {folder_id}")
        
        if os.path.isdir(file_path):
            # Handle directory upload
            print(f"Uploading directory: {file_path}")
            for root, dirs, files in os.walk(file_path):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    rel_path = os.path.relpath(dir_path, file_path)
                    drive_path = os.path.join(folder_name, rel_path).replace('\\', '/')
                    
                    print(f"Creating subfolder: {dir_name}")
                    folder_metadata = {
                        'name': dir_name,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [folder_id] if folder_id else []
                    }
                    subfolder = service.files().create(body=folder_metadata, fields='id').execute()
                
                for file_name in files:
                    file_full_path = os.path.join(root, file_name)
                    print(f"Uploading file: {file_name}")
                    file_metadata = {
                        'name': file_name,
                        'parents': [folder_id] if folder_id else []
                    }
                    
                    media = MediaFileUpload(file_full_path, resumable=True)
                    file = service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
                    print(f"Uploaded file with ID: {file.get('id')}")
        else:
            # Handle single file upload
            file_name = os.path.basename(file_path)
            print(f"Uploading file: {file_name}")
            file_metadata = {
                'name': file_name,
                'parents': [folder_id] if folder_id else []
            }
            
            media = MediaFileUpload(file_path, resumable=True)
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            print(f"Uploaded file with ID: {file.get('id')}")
        
        print("Upload to Google Drive completed successfully")
        return True
    except Exception as e:
        print(f"Error uploading to Google Drive: {e}")
        return False

def download_from_drive(file_id, destination_path):
    """Download a file or folder from Google Drive."""
    try:
        service = get_google_drive_service()
        print(f"Connected to Google Drive API")
        
        # Get file metadata
        file = service.files().get(fileId=file_id, fields='name, mimeType').execute()
        print(f"Downloading: {file['name']} (Type: {file['mimeType']})")
        
        if file['mimeType'] == 'application/vnd.google-apps.folder':
            # Handle folder download
            print(f"Creating destination folder: {destination_path}")
            os.makedirs(destination_path, exist_ok=True)
            
            # List all files in the folder
            print(f"Listing files in folder: {file_id}")
            results = service.files().list(
                q=f"'{file_id}' in parents",
                fields="files(id, name, mimeType)"
            ).execute()
            
            items = results.get('files', [])
            print(f"Found {len(items)} items in the folder")
            
            for item in items:
                item_path = os.path.join(destination_path, item['name'])
                print(f"Processing item: {item['name']} ({item['mimeType']})")
                
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    print(f"Recursively downloading subfolder: {item['name']}")
                    download_from_drive(item['id'], item_path)
                else:
                    print(f"Downloading file: {item['name']}")
                    try:
                        request = service.files().get_media(fileId=item['id'])
                        file_content = io.BytesIO()
                        downloader = MediaIoBaseDownload(file_content, request)
                        
                        done = False
                        while not done:
                            status, done = downloader.next_chunk()
                            print(f"Download progress: {int(status.progress() * 100)}%")
                        
                        # Ensure the directory exists
                        os.makedirs(os.path.dirname(item_path), exist_ok=True)
                        
                        # Save the file
                        file_content.seek(0)
                        with open(item_path, 'wb') as f:
                            f.write(file_content.read())
                        print(f"Downloaded file saved to: {item_path}")
                    except Exception as file_error:
                        print(f"Error downloading file {item['name']}: {file_error}")
        else:
            # Handle single file download
            print(f"Downloading single file: {file['name']}")
            try:
                request = service.files().get_media(fileId=file_id)
                file_content = io.BytesIO()
                downloader = MediaIoBaseDownload(file_content, request)
                
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    print(f"Download progress: {int(status.progress() * 100)}%")
                
                # Ensure the directory exists
                os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                
                # If destination is a directory, use the file name from Drive
                if os.path.isdir(destination_path):
                    destination_path = os.path.join(destination_path, file['name'])
                
                # Save the file
                file_content.seek(0)
                with open(destination_path, 'wb') as f:
                    f.write(file_content.read())
                print(f"Downloaded file saved to: {destination_path}")
            except Exception as file_error:
                print(f"Error downloading file: {file_error}")
                return False
        
        print("Download from Google Drive completed successfully")
        return True
    except Exception as e:
        print(f"Error downloading from Google Drive: {e}")
        return False

def list_drive_backups():
    """List all backups in Google Drive."""
    try:
        service = get_google_drive_service()
        
        # Search for backup folders
        results = service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and name contains 'backup_'",
            fields="files(id, name, createdTime)"
        ).execute()
        
        backups = results.get('files', [])
        
        if not backups:
            print("No backups found in Google Drive.")
            return []
        
        print("\nGoogle Drive Backups:")
        print("-------------------")
        for backup in backups:
            print(f"Name: {backup['name']}")
            print(f"Created: {backup['createdTime']}")
            print(f"ID: {backup['id']}")
            print()
        
        return backups
    except Exception as e:
        print(f"Error listing Google Drive backups: {e}")
        return []

def create_cloud_backup(game_title, source_path):
    """Create a cloud backup of game save files."""
    try:
        # Validate game title
        game_title = game_title.strip()
        if not game_title:
            print("Error: Game title cannot be empty.")
            return False
            
        # Check for invalid characters in game title
        invalid_chars = '<>:"/\\|?*'
        if any(char in game_title for char in invalid_chars):
            print(f"Error: Game title cannot contain any of these characters: {invalid_chars}")
            return False
            
        source_path = source_path.strip('"\'')  # Remove extra quotes around the path

        # Verify the source path exists
        if not os.path.exists(source_path):
            print(f"Error: Source path '{source_path}' does not exist.")
            return False

        print(f"Creating cloud backup for {game_title} from {source_path}...")
        
        # Create a temporary directory for the backup
        temp_dir = os.path.join(BASE_BACKUP_LOCATION, "temp_cloud_backup")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)  # Clean up any existing temp directory
        os.makedirs(temp_dir, exist_ok=True)

        # First copy the files to our temp directory
        temp_game_dir = os.path.join(temp_dir, game_title)
        os.makedirs(temp_game_dir, exist_ok=True)
        
        print(f"Copying files to temporary location...")
        # Copy all files from source to temp directory
        for item in os.listdir(source_path):
            s = os.path.join(source_path, item)
            d = os.path.join(temp_game_dir, item)
            
            try:
                if os.path.isdir(s):
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
            except Exception as e:
                print(f"Warning: Failed to copy {s}: {e}")
        
        # Create a timestamp for the backup name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{game_title}_{timestamp}"
        
        # Create a zip file of the backup
        zip_filename = os.path.join(temp_dir, f"{backup_name}.zip")
        print(f"Creating zip archive: {zip_filename}")
        
        # Create zip file from the temp game directory
        shutil.make_archive(
            os.path.splitext(zip_filename)[0],  # Base name (without .zip)
            'zip',  
            temp_dir,  # Root directory to start from
            game_title  # Directory to include in the archive
        )
        
        print(f"Uploading to Google Drive...")
        # Upload to Google Drive
        success = upload_to_drive(zip_filename, backup_name)
        
        # Clean up temporary files
        try:
            shutil.rmtree(temp_dir)
            print("Temporary files cleaned up.")
        except Exception as e:
            print(f"Warning: Could not clean up temp files: {e}")
        
        if success:
            print(f"Cloud backup created successfully for {game_title} ✅")
            log_backup_event("cloud_backup", game_title, source_path)
            return True
        else:
            print(f"Failed to create cloud backup for {game_title}")
            return False
            
    except Exception as e:
        print(f"Error creating cloud backup: {e}")
        return False

def restore_cloud_backup(game_title, backup_id):
    """Restore a cloud backup to its original location."""
    try:
        # Get the source path from the local backup's README file
        local_backup_path = os.path.join(BASE_BACKUP_LOCATION, game_title)
        readme_path = os.path.join(local_backup_path, "README.txt")
        source_path = None
        
        if os.path.exists(readme_path):
            with open(readme_path, "r") as f:
                for line in f:
                    if "Original Save Path:" in line:
                        source_path = line.strip().replace("Original Save Path: ", "").strip('"\'')
                        break
        
        # If we couldn't find the path from local backup, use a default location
        if not source_path:
            # Create a recovery location in the base backup folder
            source_path = os.path.join(BASE_BACKUP_LOCATION, "recovered_games", game_title)
            print(f"No destination path found. Will restore to recovery location: {source_path}")
        
        # Create a temporary directory for the download
        temp_dir = os.path.join(BASE_BACKUP_LOCATION, "temp_cloud_restore")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)  # Clean up any existing temp directory
        os.makedirs(temp_dir, exist_ok=True)
        
        print(f"Downloading cloud backup for {game_title}...")
        # Download the backup from Google Drive
        success = download_from_drive(backup_id, temp_dir)
        
        if not success:
            print("Failed to download backup from Google Drive.")
            return False
        
        # Find the zip file in the temp directory
        zip_files = [f for f in os.listdir(temp_dir) if f.endswith('.zip')]
        if not zip_files:
            print("No backup zip file found in downloaded files.")
            print(f"Files in temp dir: {os.listdir(temp_dir)}")
            return False
        
        print(f"Found zip file: {zip_files[0]}")
        zip_path = os.path.join(temp_dir, zip_files[0])
        
        # Extract directly to a new extraction directory
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        print(f"Extracting zip file to: {extract_dir}")
        # Extract the zip file
        try:
            shutil.unpack_archive(zip_path, extract_dir)
            print(f"Extraction successful. Files: {os.listdir(extract_dir)}")
        except Exception as extract_error:
            print(f"Extraction error: {extract_error}")
            return False
        
        # Check if extraction worked
        if not os.listdir(extract_dir):
            print("Error: Extracted directory is empty.")
            return False
            
        # Create target directory if it doesn't exist
        os.makedirs(source_path, exist_ok=True)
        
        print(f"Copying files to destination: {source_path}")
        # Copy files from extracted directory to destination
        for item in os.listdir(extract_dir):
            s = os.path.join(extract_dir, item)
            d = os.path.join(source_path, item)
            
            try:
                if os.path.isdir(s):
                    if os.path.exists(d):
                        shutil.rmtree(d)  # Remove existing directory first
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
                print(f"Copied: {item}")
            except Exception as copy_error:
                print(f"Error copying {item}: {copy_error}")
        
        print(f"Cloud backup restored successfully for {game_title} ✅")
        log_backup_event("cloud_restore", game_title, source_path)
        
        # Clean up
        try:
            shutil.rmtree(temp_dir)
            print("Temporary files cleaned up.")
        except Exception as cleanup_error:
            print(f"Warning: Could not clean up temp files: {cleanup_error}")
            
        return True
            
    except Exception as e:
        print(f"Error restoring cloud backup: {e}")
        # Don't delete temp_dir on error to allow for debugging
        return False

def delete_cloud_backup(backup_id):
    """Delete a cloud backup from Google Drive."""
    try:
        service = get_google_drive_service()
        service.files().delete(fileId=backup_id).execute()
        print("Cloud backup deleted successfully ✅")
        return True
    except Exception as e:
        print(f"Error deleting cloud backup: {e}")
        return False

def select_cloud_backup_dialog(title="Select Cloud Backup"):
    """Function to show cloud backup selection dialog."""
    result = {"selected": None}
    
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.geometry("500x400")
    dialog.transient(root)
    dialog.grab_set()
    
    ttk.Label(dialog, text="Available Cloud Backups:").pack(anchor=tk.W, padx=10, pady=(5, 0))
    
    # Create listbox with scrollbar
    frame = ttk.Frame(dialog)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    scrollbar = ttk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    backup_list = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("Courier", 10))
    backup_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    scrollbar.config(command=backup_list.yview)
    
    # Get cloud backups
    backups = list_drive_backups()
    
    if not backups:
        backup_list.insert(tk.END, "No cloud backups found")
    else:
        for backup in backups:
            backup_list.insert(tk.END, f"{backup['name']} ({backup['createdTime']})")
    
    def on_select():
        selection = backup_list.curselection()
        if selection and backups:
            index = selection[0]
            if index < len(backups):
                result["selected"] = backups[index]
        dialog.destroy()
    
    # Buttons
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
    
    select_btn = ttk.Button(button_frame, text="Select", command=on_select)
    select_btn.pack(side=tk.RIGHT, padx=(5, 0))
    
    cancel_btn = ttk.Button(button_frame, text="Cancel", command=dialog.destroy)
    cancel_btn.pack(side=tk.RIGHT)
    
    dialog.wait_window()
    return result["selected"]

def on_create_cloud_backup():
    """Handle create cloud backup button click."""
    game_title = simpledialog.askstring("Create Cloud Backup", "Enter the game title:")
    if game_title:
        source_path = filedialog.askdirectory(title="Select source folder")
        if source_path:
            run_in_thread(lambda: create_cloud_backup(game_title, source_path),
                         "Cloud backup created successfully!")

def on_restore_cloud_backup():
    """Handle restore cloud backup button click."""
    backup = select_cloud_backup_dialog("Select Cloud Backup to Restore")
    if backup:
        try:
            # Try to extract game title from backup name (format: backup_GAMETITLE_TIMESTAMP)
            name_parts = backup['name'].split('_')
            if len(name_parts) >= 3 and name_parts[0] == 'backup':
                # If format is correct, use the second part as game title
                game_title = name_parts[1]
            else:
                # If format is different, ask user for game title
                game_title = simpledialog.askstring("Game Title", 
                                                 f"Enter the game title for backup '{backup['name']}':")
                if not game_title:
                    messagebox.showinfo("Restore Cancelled", "Restore operation cancelled.")
                    return
        except Exception:
            # If any error occurs in parsing, ask user for game title
            game_title = simpledialog.askstring("Game Title", 
                                             "Enter the game title for this backup:")
            if not game_title:
                messagebox.showinfo("Restore Cancelled", "Restore operation cancelled.")
                return
        
        # Check if we have a local backup to determine restore path
        local_backup_path = os.path.join(BASE_BACKUP_LOCATION, game_title)
        readme_path = os.path.join(local_backup_path, "README.txt")
        restore_location = "to its original location"
        
        if not os.path.exists(readme_path):
            restore_location = f"to {os.path.join(BASE_BACKUP_LOCATION, 'recovered_games', game_title)}"
        
        if messagebox.askyesno("Confirm Restore",
                             f"This will restore the cloud backup for '{game_title}' {restore_location}.\n\nContinue?"):
            run_in_thread(lambda: restore_cloud_backup(game_title, backup['id']),
                         "Cloud backup restored successfully!")

def on_delete_cloud_backup():
    """Handle delete cloud backup button click."""
    backup = select_cloud_backup_dialog("Select Cloud Backup to Delete")
    if backup:
        if messagebox.askyesno("Confirm Delete",
                             f"Are you sure you want to delete the cloud backup '{backup['name']}'?"):
            confirm = simpledialog.askstring("Final Confirmation",
                                           "Type 'DELETE' to confirm:")
            if confirm.upper() == "DELETE":
                run_in_thread(lambda: delete_cloud_backup(backup['id']),
                             "Cloud backup deleted successfully!")

def on_list_cloud_backups():
    """Handle list cloud backups button click."""
    run_in_thread(list_drive_backups)

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
    # Validate game title
    game_title = game_title.strip()
    if not game_title:
        print("Error: Game title cannot be empty.")
        return False
        
    # Check for invalid characters in game title
    invalid_chars = '<>:"/\\|?*'
    if any(char in game_title for char in invalid_chars):
        print(f"Error: Game title cannot contain any of these characters: {invalid_chars}")
        return False
        
    source_path = source_path.strip('"\'')  # Remove extra quotes around the path

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
                    source_path = line.strip().replace("Original Save Path: ", "").strip('"\'')
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
            source_path = source_path.strip('"\'')
    
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

def update_all_backups(auto_confirm=False):
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
    
    # Only ask for confirmation if not in auto_confirm mode
    if not auto_confirm:
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

def restore_all_backups(auto_confirm=False):
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
    
    # Only ask for confirmation if not in auto_confirm mode
    if not auto_confirm:
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

def view_logs_gui():
    """View backup logs in a GUI dialog."""
    if not os.path.exists(LOGS_ROOT):
        messagebox.showinfo("No Logs", "No logs found.")
        return
        
    log_file = os.path.join(LOGS_ROOT, "backup_log.txt")
    
    if not os.path.exists(log_file):
        messagebox.showinfo("No Logs", "No logs found.")
        return
    
    # Create log viewer dialog
    log_dialog = tk.Toplevel(root)
    log_dialog.title("Backup Logs")
    log_dialog.geometry("700x500")
    log_dialog.transient(root)
    log_dialog.grab_set()
    
    # Add a frame for the log content
    frame = ttk.Frame(log_dialog, padding="10")
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Add title label
    ttk.Label(frame, text="Backup Logs", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
    
    # Create scrolled text widget for logs
    log_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Consolas", 10))
    log_text.pack(fill=tk.BOTH, expand=True)
    
    # Add close button
    ttk.Button(frame, text="Close", command=log_dialog.destroy).pack(pady=10)
    
    try:
        with open(log_file, "r") as f:
            logs = f.readlines()
        
        log_text.insert(tk.END, f"Total log entries: {len(logs)}\n\n")
        
        # Display the most recent logs first
        for log in logs[::-1]:  # Reverse the logs to show newest first
            log_text.insert(tk.END, log)
        
        # Make the text widget read-only
        log_text.configure(state="disabled")
    except Exception as e:
        log_text.insert(tk.END, f"Error reading logs: {e}")
        log_text.configure(state="disabled")

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

def delete_backup(game_title=None, auto_confirm=False):
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
    
    # Confirm with the user if not auto-confirming
    if not auto_confirm:
        confirm = input(f"Are you sure you want to PERMANENTLY delete the backup for '{game_title}' and all related safety backups? (y/n): ")
        if confirm.lower() != 'y':
            print("Delete operation cancelled.")
            return False
        
        # Double-confirm for safety since this is permanent
        confirm = input("This action CANNOT be undone. Type 'DELETE' to confirm: ")
        if confirm.upper() != "DELETE":  # Changed to case-insensitive comparison
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

def check_backup_location_permissions():
    """Check if the backup location is writable."""
    try:
        # Try to create a test file
        test_file = os.path.join(BASE_BACKUP_LOCATION, ".test")
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except Exception as e:
        print(f"Error: Cannot write to backup location {BASE_BACKUP_LOCATION}: {e}")
        print("Please check the folder permissions and try again.")
        return False

def create_test_backups():
    """Create sample backups for testing purposes."""
    print("\nCreating test backups...")
    
    # Create a test directory for sample saves
    test_dir = os.path.join(BASE_BACKUP_LOCATION, "test_saves")
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    
    # Create sample game saves
    test_games = [
        "Test Game 1",
        "Test Game 2",
        "Test Game 3"
    ]
    
    for game in test_games:
        # Create a sample save directory
        game_save_dir = os.path.join(test_dir, game)
        os.makedirs(game_save_dir, exist_ok=True)
        
        # Create some dummy save files
        for i in range(3):
            save_file = os.path.join(game_save_dir, f"save_{i}.txt")
            with open(save_file, "w") as f:
                f.write(f"This is a test save file for {game}\n")
                f.write(f"Created at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Create a backup of this test game
        create_backup(game, game_save_dir)
        print(f"Created test backup for {game}")
    
    print("\nTest backups created successfully!")
    print("You can now test all features with these sample backups.")

def on_test_mode():
    """Handle test mode button click."""
    if messagebox.askyesno("Test Mode", 
                          "This will create sample backups for testing.\nContinue?"):
        run_in_thread(create_test_backups, "Test backups created successfully!")

def select_backup_dialog(title="Select Backup", allow_cancel=True):
    """Function to populate backup list and return selected title with optimized performance"""
    result = {"selected": None}
    
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.geometry("500x400")
    dialog.transient(root)
    dialog.grab_set()
    
    ttk.Label(dialog, text="Available Backups:").pack(anchor=tk.W, padx=10, pady=(5, 0))  # Reduced padding
    
    # Create listbox with scrollbar
    frame = ttk.Frame(dialog)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)  # Reduced padding
    
    scrollbar = ttk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    backup_list = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("Courier", 10))
    backup_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    scrollbar.config(command=backup_list.yview)
    
    # Get backups with optimized performance
    backups = []
    if not os.path.exists(BASE_BACKUP_LOCATION):
        backup_list.insert(tk.END, "No backups found")
    else:
        try:
            backups = [d for d in os.listdir(BASE_BACKUP_LOCATION) 
                       if os.path.isdir(os.path.join(BASE_BACKUP_LOCATION, d)) 
                       and d != "logs" 
                       and not d.endswith("_backup_")]
            
            if not backups:
                backup_list.insert(tk.END, "No backups found")
            else:
                # Batch insert items for better performance
                items_to_insert = []
                for i, backup in enumerate(backups, 1):
                    backup_path = os.path.join(BASE_BACKUP_LOCATION, backup)
                    readme_path = os.path.join(backup_path, "README.txt")
                    
                    backup_date = "Unknown"
                    
                    if os.path.exists(readme_path):
                        try:
                            with open(readme_path, "r") as f:
                                for line in f:
                                    if "Backup Date:" in line:
                                        backup_date = line.strip().replace("Backup Date: ", "")
                                        break
                        except Exception:
                            pass
                    
                    items_to_insert.append((f"{backup} - {backup_date}", i))
                
                # Insert all items at once
                for text, i in items_to_insert:
                    backup_list.insert(tk.END, text)
                    backup_list.itemconfig(i-1, {'bg': '#f0f0f0' if i % 2 == 0 else '#ffffff'})
        except Exception as e:
            backup_list.insert(tk.END, f"Error loading backups: {e}")
    
    # Buttons with optimized layout
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, padx=10, pady=(0, 5))  # Reduced padding
    
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
    
    # Check backup location permissions
    if not check_backup_location_permissions():
        input("Press Enter to exit...")
        sys.exit(1)
    
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

# GUI Callback Functions
def on_create_backup():
    """Handle create backup button click."""
    game_title = simpledialog.askstring("Create Backup", "Enter the game title:")
    if game_title:
        source_path = filedialog.askdirectory(title="Select source folder")
        if source_path:
            run_in_thread(lambda: create_backup(game_title, source_path), 
                         "Backup created successfully!")

def on_update_backup():
    """Handle update backup button click."""
    game_title = select_backup_dialog("Select Backup to Update")
    if game_title:
        run_in_thread(lambda: update_backup(game_title, auto_confirm=True),
                     "Backup updated successfully!")

def on_restore_backup():
    """Handle restore backup button click."""
    game_title = select_backup_dialog("Select Backup to Restore")
    if game_title:
        if messagebox.askyesno("Confirm Restore", 
                             "This will restore the backup to its original location. Continue?"):
            run_in_thread(lambda: restore_backup(game_title, auto_confirm=True),
                         "Backup restored successfully!")

def on_update_all():
    """Handle update all backups button click."""
    if messagebox.askyesno("Confirm Update All", 
                          "This will update all backups. Continue?"):
        run_in_thread(lambda: update_all_backups(auto_confirm=True),
                     "All backups updated successfully!")

def on_restore_all():
    """Handle restore all backups button click."""
    if messagebox.askyesno("Confirm Restore All", 
                          "⚠️ WARNING: This will restore ALL game saves to their original locations! Continue?"):
        confirm = simpledialog.askstring("Final Confirmation", 
                                       "Type 'RESTORE ALL' to confirm:")
        if confirm == "RESTORE ALL":
            run_in_thread(lambda: restore_all_backups(auto_confirm=True),
                         "All backups restored successfully!")

def on_view_logs():
    """Handle view logs button click."""
    view_logs_gui()  # Use the GUI version directly instead of run_in_thread

def on_open_savegame_pro():
    """Handle open savegame.pro button click."""
    run_in_thread(open_savegame_pro)

def on_search_game():
    """Handle search game button click."""
    game_name = simpledialog.askstring("Search Game", "Enter game name to search:")
    if game_name:
        search_url = f"{SAVEGAME_PRO_URL}?s={game_name.replace(' ', '+')}"
        webbrowser.open(search_url)

def on_delete_backup():
    """Handle delete backup button click."""
    game_title = select_backup_dialog("Select Backup to Delete")
    if game_title:
        if messagebox.askyesno("Confirm Delete", 
                             f"Are you sure you want to delete the backup for '{game_title}'?"):
            confirm = simpledialog.askstring("Final Confirmation", 
                                           "Type 'DELETE' to confirm:")
            if confirm.upper() == "DELETE":
                run_in_thread(lambda: delete_backup(game_title, auto_confirm=True),
                             "Backup deleted successfully!")

def switch_to_cli():
    """Handle switch to CLI mode button click."""
    global root
    if messagebox.askyesno("Switch Mode", 
                          "Are you sure you want to switch to CLI mode?"):
        root.quit()
        root.destroy()
        main(gui_mode=False)

# GUI Implementation
def start_gui():
    """Start the GUI interface for the backup tool."""
    global root, console
    
    # Create the main window
    root = tk.Tk()
    root.title("Save Game Backup Tool")
    root.geometry("800x600")  # Set initial size
    root.resizable(False, False)  # Disable window resizing
    
    # Add proper window closing handler
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            root.quit()
            root.destroy()
            # Force close the terminal/CMD window
            if os.name == 'nt':  # Windows
                os.system('taskkill /f /im cmd.exe /t')
            else:  # Linux/Mac
                os.system('kill -9 $PPID')
            sys.exit(0)
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Configure style with optimized settings
    style = ttk.Style()
    style.theme_use('clam')  # Use clam theme for better appearance
    
    # Configure button styles with optimized settings
    style.configure("TButton", 
                   padding=6,  # Reduced padding
                   relief="flat", 
                   background="#e1e1e1",
                   font=("Segoe UI", 9))
    style.map("TButton",
              background=[("active", "#d1d1d1")],
              relief=[("pressed", "sunken")])
    
    # Configure frame styles with optimized settings
    style.configure("TFrame", 
                   background="#f5f5f5")
    
    # Configure label styles with optimized settings
    style.configure("TLabel", 
                   background="#f5f5f5", 
                   font=("Segoe UI", 9))
    style.configure("Header.TLabel", 
                   font=("Segoe UI", 16, "bold"),
                   padding=8)  # Reduced padding
    
    # Configure paned window style with optimized settings
    style.configure("TPanedwindow", 
                   background="#f5f5f5")
    
    # Create main frame with optimized padding
    main_frame = ttk.Frame(root, padding="10")  # Reduced padding
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Header with optimized styling
    header_frame = ttk.Frame(main_frame)
    header_frame.pack(fill=tk.X, pady=(0, 10))  # Reduced padding
    
    header_label = ttk.Label(header_frame, 
                           text="Save Game Backup Tool", 
                           style="Header.TLabel")
    header_label.pack(side=tk.LEFT)
    
    config_path_label = ttk.Label(header_frame, 
                                text=f"Config: {CONFIG_FILE}",
                                font=("Segoe UI", 8))
    config_path_label.pack(side=tk.RIGHT)
    
    # Backup location info with optimized styling
    backup_info_frame = ttk.Frame(main_frame)
    backup_info_frame.pack(fill=tk.X, pady=(0, 10))  # Reduced padding
    
    backup_path_label = ttk.Label(backup_info_frame, 
                                text=f"Backup Location: {BASE_BACKUP_LOCATION}",
                                font=("Segoe UI", 9))
    backup_path_label.pack(side=tk.LEFT)
    
    def edit_config():
        try:
            if os.path.exists(CONFIG_FILE):
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
    
    edit_config_btn = ttk.Button(backup_info_frame, 
                               text="Edit Config", 
                               command=edit_config,
                               style="TButton")
    edit_config_btn.pack(side=tk.RIGHT)
    
    # Split the interface into two parts with optimized styling
    paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
    paned_window.pack(fill=tk.BOTH, expand=True)
    
    # Left panel - Buttons with optimized layout
    left_frame = ttk.Frame(paned_window)
    paned_window.add(left_frame, weight=1)
    
    # Right panel - Console output with optimized styling
    right_frame = ttk.Frame(paned_window)
    paned_window.add(right_frame, weight=2)
    
    # Console output area with optimized styling
    ttk.Label(right_frame, 
             text="Console Output:", 
             font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, padx=10, pady=(5, 0))  # Reduced padding
    
    console_frame = ttk.Frame(right_frame, borderwidth=1, relief=tk.SUNKEN)
    console_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)  # Reduced padding
    
    console = scrolledtext.ScrolledText(console_frame, 
                                      wrap=tk.WORD, 
                                      font=("Consolas", 10),
                                      bg="#ffffff",
                                      fg="#000000",
                                      maxundo=0,  # Disable undo to improve performance
                                      undo=False)  # Disable undo to improve performance
    console.pack(fill=tk.BOTH, expand=True)
    console.configure(state="disabled")
    
    # Create buttons with optimized sizing and spacing
    button_frame = ttk.Frame(left_frame)
    button_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)  # Reduced padding
    
    # Create a canvas with scrollbar for the buttons
    canvas = tk.Canvas(button_frame, bg="#f5f5f5", highlightthickness=0)
    scrollbar = ttk.Scrollbar(button_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=200)
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Pack the scrollbar and canvas
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    
    # Bind mouse wheel for scrolling
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    button_width = 25  # Fixed button width
    
    # Create all the buttons with optimized styling
    create_backup_btn = ttk.Button(scrollable_frame, 
                                 text="Create Backup", 
                                 width=button_width, 
                                 command=on_create_backup)
    create_backup_btn.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    update_backup_btn = ttk.Button(scrollable_frame, 
                                 text="Update Backup", 
                                 width=button_width, 
                                 command=on_update_backup)
    update_backup_btn.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    restore_backup_btn = ttk.Button(scrollable_frame, 
                                  text="Restore Backup", 
                                  width=button_width, 
                                  command=on_restore_backup)
    restore_backup_btn.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    update_all_btn = ttk.Button(scrollable_frame, 
                              text="Update All Backups", 
                              width=button_width, 
                              command=on_update_all)
    update_all_btn.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    restore_all_btn = ttk.Button(scrollable_frame, 
                               text="Restore All Backups", 
                               width=button_width, 
                               command=on_restore_all)
    restore_all_btn.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    list_backups_btn = ttk.Button(scrollable_frame, 
                                text="List Backups", 
                                width=button_width, 
                                command=lambda: select_backup_dialog("Backup List", allow_cancel=True))
    list_backups_btn.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    view_logs_btn = ttk.Button(scrollable_frame, 
                             text="View Logs", 
                             width=button_width, 
                             command=on_view_logs)
    view_logs_btn.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    open_savegame_btn = ttk.Button(scrollable_frame, 
                                 text="Open SaveGame.pro", 
                                 width=button_width, 
                                 command=on_open_savegame_pro)
    open_savegame_btn.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    search_game_btn = ttk.Button(scrollable_frame, 
                               text="Search Game", 
                               width=button_width, 
                               command=on_search_game)
    search_game_btn.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    delete_backup_btn = ttk.Button(scrollable_frame, 
                                 text="Delete Backup", 
                                 width=button_width, 
                                 command=on_delete_backup)
    delete_backup_btn.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    # Add separator before cloud backup section
    ttk.Separator(scrollable_frame, orient='horizontal').pack(fill=tk.X, pady=10)
    
    # Cloud backup section header
    ttk.Label(scrollable_frame, 
             text="Cloud Backup", 
             font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
    
    # Cloud backup buttons
    create_cloud_backup_btn = ttk.Button(scrollable_frame, 
                                       text="Create Cloud Backup", 
                                       width=button_width, 
                                       command=on_create_cloud_backup)
    create_cloud_backup_btn.pack(fill=tk.X, pady=(0, 5))
    
    restore_cloud_backup_btn = ttk.Button(scrollable_frame, 
                                        text="Restore Cloud Backup", 
                                        width=button_width, 
                                        command=on_restore_cloud_backup)
    restore_cloud_backup_btn.pack(fill=tk.X, pady=(0, 5))
    
    list_cloud_backups_btn = ttk.Button(scrollable_frame, 
                                      text="List Cloud Backups", 
                                      width=button_width, 
                                      command=on_list_cloud_backups)
    list_cloud_backups_btn.pack(fill=tk.X, pady=(0, 5))
    
    delete_cloud_backup_btn = ttk.Button(scrollable_frame, 
                                       text="Delete Cloud Backup", 
                                       width=button_width, 
                                       command=on_delete_cloud_backup)
    delete_cloud_backup_btn.pack(fill=tk.X, pady=(0, 5))
    
    # Add separator before exit button
    ttk.Separator(scrollable_frame, orient='horizontal').pack(fill=tk.X, pady=10)
    
    exit_btn = ttk.Button(scrollable_frame, 
                         text="Exit", 
                         width=button_width, 
                         command=on_closing)
    exit_btn.pack(fill=tk.X, pady=(0, 5))  # Reduced padding
    
    # Status bar with optimized styling
    status_bar = ttk.Label(main_frame, 
                          text=f"Backup Location: {BASE_BACKUP_LOCATION}", 
                          relief=tk.SUNKEN, 
                          anchor=tk.W,
                          padding=3,  # Reduced padding
                          font=("Segoe UI", 8))
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Welcome message in console with optimized formatting
    console.configure(state="normal")
    console.insert(tk.END, "Welcome to Save Game Backup Tool!\n")
    console.insert(tk.END, "================================\n\n")
    console.insert(tk.END, f"Base Backup Location: {BASE_BACKUP_LOCATION}\n")
    console.insert(tk.END, f"Config File: {CONFIG_FILE}\n\n")
    console.insert(tk.END, "Select an operation from the buttons on the left.\n")
    console.insert(tk.END, "Console output will appear here.\n")
    console.configure(state="disabled")
    
    # Start the main loop with improved error handling
    try:
        root.mainloop()
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        root.quit()
        root.destroy()
        sys.exit(0)

def run_in_thread(func, success_msg=None):
    """Thread-safe function executor for GUI operations."""
    global console
    # Create a queue for console output
    console_queue = queue.Queue()
    # Create a flag to signal when the operation is done
    done_flag = threading.Event()
    # Result storage
    result_container = {"success": False, "error": None}
    
    # Text redirector for capturing console output with throttling
    class ThreadSafeConsoleRedirector:
        def __init__(self, queue_obj):
            self.queue = queue_obj
            self.last_update = 0
            self.update_interval = 0.1  # 100ms between updates
            
        def write(self, string):
            current_time = time.time()
            if current_time - self.last_update >= self.update_interval:
                self.queue.put(string)
                self.last_update = current_time
            
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
        try:
            while not console_queue.empty():
                message = console_queue.get_nowait()
                console.configure(state="normal")
                console.insert(tk.END, message)
                console.see(tk.END)
                console.configure(state="disabled")
                console_queue.task_done()
        except queue.Empty:
            pass
        
        # Check if the thread is done
        if done_flag.is_set():
            if result_container["error"]:
                messagebox.showerror("Error", f"Operation failed: {result_container['error']}")
            elif success_msg and result_container["success"]:
                messagebox.showinfo("Success", success_msg)
            return  # Stop checking
        
        # Schedule the next check with a longer interval
        root.after(200, check_thread)
    
    # Start checking
    root.after(200, check_thread)

if __name__ == "__main__":
    try:
        # Create base directories if they don't exist
        for dir_path in [BASE_BACKUP_LOCATION, LOGS_ROOT, SAFETY_BACKUPS_ROOT]:
            check_create_dir(dir_path)
        
        # Start in GUI mode by default
        main(gui_mode=True)
        # Exit cleanly after GUI closes
        sys.exit(0)
            
    except Exception as e:
        print(f"Fatal error: {e}")
        print("The program will now exit.")
        sys.exit(1)