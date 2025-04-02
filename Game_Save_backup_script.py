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
import zipfile
import ctypes

class ThreadSafeConsoleRedirector:
    """A thread-safe console output redirector that uses a queue."""
    def __init__(self, queue_obj):
        self.queue = queue_obj

    def write(self, string):
        """Write a string to the queue."""
        if string.strip():  # Only queue non-empty strings
            self.queue.put(string)

    def flush(self):
        """Flush the queue."""
        pass

# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive']  # Use full access scope instead of drive.file

def get_google_drive_service(force_refresh=False):
    """Get or create Google Drive service with authentication.
    
    Args:
        force_refresh (bool): If True, will ignore existing token and force re-authentication
        
    Returns:
        service: The Google Drive service object
    """
    creds = None
    
    # Get the token file location
    token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.pickle")
    credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
    
    # Check if credentials file exists
    if not os.path.exists(credentials_path):
        print(f"Error: credentials.json file not found at {credentials_path}")
        print("You need to obtain OAuth 2.0 credentials from Google Cloud Console.")
        print("See https://developers.google.com/drive/api/v3/quickstart/python")
        raise FileNotFoundError(f"credentials.json not found at {credentials_path}")
    
    # Delete token if force refresh is requested
    if force_refresh and os.path.exists(token_path):
        try:
            os.remove(token_path)
            print(f"Removed existing token file for re-authentication")
        except Exception as e:
            print(f"Warning: Could not remove token file: {e}")
    
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
            print("Loaded existing authentication token")
        except Exception as e:
            print(f"Error loading token file: {e}")
            creds = None
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expired, refreshing...")
            try:
                creds.refresh(Request())
                print("Token refreshed successfully")
            except Exception as refresh_error:
                print(f"Error refreshing token: {refresh_error}")
                # If refresh fails, force new authentication
                print("Initiating new authentication flow...")
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            print("No valid token found. Initiating authentication flow...")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        try:
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
            print(f"Saved authentication token to {token_path}")
        except Exception as save_error:
            print(f"Warning: Could not save token: {save_error}")
    
    try:
        service = build('drive', 'v3', credentials=creds)
        print("Google Drive API service initialized successfully")
        return service
    except Exception as build_error:
        print(f"Error building service: {build_error}")
        raise

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

def find_or_create_main_folder(service):
    """Find or create main backup folder in Google Drive."""
    try:
        main_folder_name = "Game Save Tool Backups"
        print(f"Searching for main backup folder: '{main_folder_name}'")
        
        # First, try to find the folder
        query = f"mimeType='application/vnd.google-apps.folder' and name='{main_folder_name}' and trashed=false"
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        
        items = results.get('files', [])
        
        if items:
            folder_id = items[0]['id']
            print(f"Found existing main folder: {main_folder_name} (ID: {folder_id})")
            return folder_id
        
        # If not found, create it
        print(f"Main folder not found. Creating new folder: {main_folder_name}")
        folder_metadata = {
            'name': main_folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        folder = service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        
        folder_id = folder.get('id')
        print(f"Created main folder with ID: {folder_id}")
        return folder_id
        
    except Exception as e:
        print(f"Error finding or creating main folder: {e}")
        return None

def create_backup_folder(service, parent_folder_id, folder_name):
    """Create a folder within the parent folder in Google Drive."""
    try:
        print(f"Creating folder '{folder_name}' in parent folder ID: {parent_folder_id}")
        
        # First check if the folder already exists
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{parent_folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        
        items = results.get('files', [])
        
        if items:
            folder = items[0]
            print(f"Found existing folder: {folder['name']} (ID: {folder['id']})")
            return folder
        
        # If not found, create it
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        
        folder = service.files().create(
            body=folder_metadata,
            fields='id, name'
        ).execute()
        
        print(f"Created new folder: {folder['name']} (ID: {folder['id']})")
        return folder
        
    except Exception as e:
        print(f"Error creating folder: {e}")
        return None

def list_folder_contents(service, folder_id):
    """List the contents of a folder in Google Drive."""
    try:
        print(f"Listing contents of folder with ID: {folder_id}")
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType)",
            pageSize=100
        ).execute()
        
        items = results.get('files', [])
        if not items:
            print(f"Folder is empty or not accessible")
            return []
            
        print(f"Found {len(items)} items in folder")
        for item in items:
            item_type = "Folder" if item['mimeType'] == 'application/vnd.google-apps.folder' else "File"
            print(f"  - {item['name']} ({item_type}, ID: {item['id']})")
            
        return items
    except Exception as e:
        print(f"Error listing folder contents: {e}")
        return []

def get_game_folders(service, main_folder_id):
    """Get all game folders within the main backup folder."""
    try:
        print(f"Retrieving game folders from main folder (ID: {main_folder_id})...")
        
        # First, check if the main folder still exists and is accessible
        try:
            folder_info = service.files().get(fileId=main_folder_id, fields="name,mimeType").execute()
            print(f"Main folder info: {folder_info.get('name')} ({folder_info.get('mimeType')})")
        except Exception as folder_error:
            print(f"Warning: Could not access main folder: {folder_error}")
            print("Will attempt to find it again...")
            new_main_id = find_or_create_main_folder(service)
            if new_main_id:
                print(f"Found/created main folder with ID: {new_main_id}")
                main_folder_id = new_main_id
            else:
                print("Failed to find or create main folder. Using direct search for game folders.")
                # Search for any game folders without a parent reference
                all_folders_query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
                all_results = service.files().list(
                    q=all_folders_query, 
                    fields="files(id, name)"
                ).execute()
                
                # Return all folders as potential game folders
                return all_results.get('files', [])
        
        # Query for all folders inside the main folder
        query = f"mimeType='application/vnd.google-apps.folder' and '{main_folder_id}' in parents and trashed=false"
        print(f"Running query for game folders: {query}")
        
        results = service.files().list(
            q=query,
            fields="files(id, name)",
            orderBy="name"
        ).execute()
        
        game_folders = results.get('files', [])
        print(f"Found {len(game_folders)} game folders")
        
        # If no game folders are found in the main folder, try creating a test game folder
        if not game_folders:
            print("No game folders found. Creating a test game folder...")
            test_folder = create_backup_folder(service, main_folder_id, "Test Game")
            if test_folder:
                print(f"Created test game folder: {test_folder.get('name')} (ID: {test_folder.get('id')})")
                game_folders.append({"id": test_folder.get('id'), "name": test_folder.get('name')})
        
        return game_folders
    except Exception as e:
        print(f"Error retrieving game folders: {e}")
        return []

def list_drive_backups():
    """List all backups in Google Drive."""
    try:
        print("\n=== Cloud Backup List ===\n")
        service = get_google_drive_service()
        
        # Find the main backup folder
        main_folder_id = find_or_create_main_folder(service)
        if not main_folder_id:
            print("No main backup folder found in Google Drive.")
            return []
            
        # Get all game folders
        game_folders = get_game_folders(service, main_folder_id)
        if not game_folders:
            print("No game backups found in Google Drive.")
            return []
            
        # Sort game folders alphabetically
        game_folders.sort(key=lambda x: x['name'].lower())
        
        total_backups = 0
        for game_folder in game_folders:
            game_title = game_folder['name']
            game_id = game_folder['id']
            
            print(f"\n📁 Game: {game_title}")
            print("=" * (len(game_title) + 7))  # Underline the game title
            
            # Get all backups for this game
            query = f"'{game_id}' in parents and mimeType='application/vnd.google-apps.folder'"
            results = service.files().list(
                q=query,
                fields="files(id, name, createdTime)"
            ).execute()
            
            backups = results.get('files', [])
            if not backups:
                print("  No backups found")
                continue
                
            # Sort backups by creation time (newest first)
            backups.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
            
            for backup in backups:
                backup_name = backup['name']
                created_time = backup.get('createdTime', '')
                
                if created_time:
                    try:
                        # Format the date from ISO format
                        created_dt = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                        formatted_date = created_dt.strftime('%Y-%m-%d %H:%M')
                        print(f"  📦 {backup_name}")
                        print(f"     Created: {formatted_date}")
                    except Exception:
                        print(f"  📦 {backup_name}")
                        print(f"     Created: {created_time}")
                else:
                    print(f"  📦 {backup_name}")
                
                total_backups += 1
            
            print()  # Add a blank line between games
        
        print(f"\nTotal Backups: {total_backups}")
        print("\n=== End of Cloud Backup List ===\n")
        return game_folders
        
    except Exception as e:
        print(f"Error listing cloud backups: {e}")
        return []

def create_cloud_backup(game_title, source_path):
    """Create a cloud backup of game save files."""
    try:
        print(f"Starting cloud backup for {game_title}")
        print(f"Source path: {source_path}")
        
        # Verify source path exists
        if not os.path.exists(source_path):
            print(f"Error: Source path does not exist: {source_path}")
            messagebox.showerror("Error", f"Source path does not exist: {source_path}")
            return False
            
        # Verify source path is a directory
        if not os.path.isdir(source_path):
            print(f"Error: Source path is not a directory: {source_path}")
            messagebox.showerror("Error", f"Source path is not a directory: {source_path}")
            return False
        
        try:
            service = get_google_drive_service()
            print("Connected to Google Drive.")
        except Exception as auth_error:
            error_msg = f"Failed to authenticate with Google Drive: {auth_error}"
            print(f"Error: {error_msg}")
            
            # Offer to re-authenticate
            if messagebox.askyesno("Authentication Error", 
                                 f"Failed to connect to Google Drive: {str(auth_error)}\n\n"
                                 "Would you like to try re-authenticating?"):
                try:
                    # Force refresh of credentials
                    service = get_google_drive_service(force_refresh=True)
                    print("Re-authentication successful.")
                except Exception as reauth_error:
                    print(f"Re-authentication failed: {reauth_error}")
                    messagebox.showerror("Authentication Failed", 
                                       f"Could not authenticate with Google Drive.\n\n"
                                       "Please check your credentials.json file and internet connection.")
                    return False
            else:
                messagebox.showerror("Authentication Failed", 
                                   "Please check your credentials.json file and internet connection.")
                return False
        
        # Create a temporary directory for the backup
        temp_dir = os.path.join(BASE_BACKUP_LOCATION, "temp_cloud_backup")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)  # Clean up any existing temp directory
        os.makedirs(temp_dir, exist_ok=True)
        print(f"Created temporary directory: {temp_dir}")

        # Create a timestamp for the backup name in a more readable format
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        backup_name = f"{game_title} - {timestamp}"  # More readable format
        
        # Find or create the main backup folder
        print("Locating main backup folder in Google Drive...")
        main_folder_id = find_or_create_main_folder(service)
        if not main_folder_id:
            error_msg = "Failed to create or find the main backup folder in Google Drive."
            print(f"Error: {error_msg}")
            messagebox.showerror("Folder Error", error_msg)
            return False
            
        # List all folders in the main folder to verify visibility
        print("Checking visible folders in main backup folder...")
        main_folder_contents = list_folder_contents(service, main_folder_id)
        print(f"Visible folders in main backup folder: {', '.join([f['name'] for f in main_folder_contents]) or 'None'}")
        
        # Find or create a folder for this game
        print(f"Finding/creating game folder for '{game_title}'...")
        game_folder = create_backup_folder(service, main_folder_id, game_title)
        if not game_folder:
            error_msg = f"Failed to create or find the game folder for '{game_title}'."
            print(f"Error: {error_msg}")
            messagebox.showerror("Folder Error", error_msg)
            return False
        
        game_folder_id = game_folder['id']
        print(f"Using game folder: {game_title} (ID: {game_folder_id})")
        
        # List contents of the game folder to verify visibility
        print(f"Checking visible folders in game folder...")
        game_folder_contents = list_folder_contents(service, game_folder_id)
        print(f"Visible folders in game folder: {', '.join([f['name'] for f in game_folder_contents]) or 'None'}")
        
        # Create a folder for this specific backup
        print(f"Creating backup folder '{backup_name}'...")
        backup_folder = create_backup_folder(service, game_folder_id, backup_name)
        if not backup_folder:
            error_msg = "Failed to create the backup folder."
            print(f"Error: {error_msg}")
            messagebox.showerror("Folder Error", error_msg)
            return False
        
        backup_folder_id = backup_folder['id']
        print(f"Created backup folder: {backup_name} (ID: {backup_folder_id})")
        
        # Create a README file with backup information
        readme_path = os.path.join(temp_dir, "README.txt")
        with open(readme_path, "w") as f:
            f.write(f"Game Title: {game_title}\n")
            f.write(f"Original Save Path: {source_path}\n")
            f.write(f"Backup Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Created By: Save Game Backup Tool\n")
        
        # Upload the README file
        print("Uploading README file...")
        readme_metadata = {
            'name': "README.txt",
            'parents': [backup_folder_id]
        }
        
        media = MediaFileUpload(readme_path, resumable=True)
        readme_file = service.files().create(
            body=readme_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f"README file uploaded with ID: {readme_file.get('id')}")
        
        # Create the ZIP archive of the save files
        print(f"Creating ZIP archive from source: {source_path}")
        zip_filename = os.path.join(temp_dir, f"{backup_name}.zip")
        
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Calculate the archive path - make it relative to source_path
                    arcname = os.path.relpath(file_path, source_path)
                    print(f"Adding file: {arcname}")
                    zipf.write(file_path, arcname)
        
        print(f"ZIP archive created: {zip_filename}")
        
        # Upload the ZIP file
        print(f"Uploading ZIP file to backup folder...")
        zip_metadata = {
            'name': f"{backup_name}.zip",
            'parents': [backup_folder_id]
        }
        
        media = MediaFileUpload(zip_filename, resumable=True)
        file = service.files().create(
            body=zip_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f"ZIP file uploaded with ID: {file.get('id')}")
        
        # Verify the backup folder contents
        print("Verifying backup folder contents...")
        backup_folder_contents = list_folder_contents(service, backup_folder_id)
        print(f"Files in backup folder: {', '.join([f['name'] for f in backup_folder_contents])}")
        
        # Clean up temporary files
        try:
            print("Cleaning up temporary files...")
            shutil.rmtree(temp_dir)
            print("Temporary files cleaned up.")
        except Exception as cleanup_error:
            print(f"Warning: Could not clean up temp files: {cleanup_error}")
        
        print(f"Cloud backup created successfully for {game_title} ✅")
        log_backup_event("cloud_backup", game_title, source_path)
        return True
        
    except Exception as e:
        print(f"Error creating cloud backup: {e}")
        messagebox.showerror("Backup Error", f"Error creating cloud backup: {str(e)}")
        return False

def restore_cloud_backup(backup_info):
    """Restore a backup from Google Drive."""
    try:
        # Extract backup information
        game_title = backup_info['game_title']
        backup_name = backup_info['backup_name']
        backup_id = backup_info['backup_id']
        
        print(f"Starting restore of cloud backup for {game_title}")
        print(f"Backup name: {backup_name}")
        print(f"Backup ID: {backup_id}")
        
        # Connect to Google Drive
        print("Connecting to Google Drive API...")
        service = get_google_drive_service()
        print("Connected to Google Drive API")
        
        # Verify that the backup folder exists
        try:
            backup_folder = service.files().get(fileId=backup_id, fields="name,mimeType").execute()
            print(f"Found backup folder: {backup_folder.get('name')} ({backup_folder.get('mimeType')})")
        except Exception as e:
            print(f"Error accessing backup folder: {e}")
            messagebox.showerror("Restore Error", f"Could not access the backup folder: {str(e)}")
            return False
        
        # Look for a README file in the backup folder to get the original save path
        source_path = None
        print("Searching for README file in backup folder...")
        
        query = f"'{backup_id}' in parents and name='README.txt'"
        try:
            results = service.files().list(q=query, fields="files(id, name)").execute()
            readme_files = results.get('files', [])
            
            if readme_files:
                readme_id = readme_files[0]['id']
                print(f"Found README file with ID: {readme_id}")
                
                # Create a temporary directory for the download
                temp_dir = os.path.join(BASE_BACKUP_LOCATION, "temp_cloud_restore")
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)  # Clean up any existing temp directory
                os.makedirs(temp_dir, exist_ok=True)
                
                # Download the README file
                request = service.files().get_media(fileId=readme_id)
                file_content = io.BytesIO()
                downloader = MediaIoBaseDownload(file_content, request)
                
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    print(f"README download progress: {int(status.progress() * 100)}%")
                
                # Parse the README file for the original save path
                file_content.seek(0)
                readme_text = file_content.read().decode('utf-8')
                
                for line in readme_text.splitlines():
                    if "Original Save Path:" in line:
                        source_path = line.strip().replace("Original Save Path: ", "").strip('"\'')
                        print(f"Found original save path in README: {source_path}")
                        break
            else:
                print("No README file found in backup folder")
        except Exception as readme_error:
            print(f"Error reading README file: {readme_error}")
        
        # If we couldn't find the path from README, use a default recovery location
        if not source_path:
            # Create a recovery location in the base backup folder
            source_path = os.path.join(BASE_BACKUP_LOCATION, "recovered_games", game_title)
            print(f"No destination path found. Will restore to recovery location: {source_path}")
        
        # Create a temporary directory for the download if it doesn't exist already
        temp_dir = os.path.join(BASE_BACKUP_LOCATION, "temp_cloud_restore")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        else:
            # Clean up any existing files
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
        
        print(f"Created temporary directory for restore: {temp_dir}")
        
        # Find and download the ZIP file from the backup folder
        print("Searching for backup ZIP file...")
        query = f"'{backup_id}' in parents and mimeType contains 'zip'"
        
        try:
            results = service.files().list(q=query, fields="files(id, name)").execute()
            zip_files = results.get('files', [])
            
            if not zip_files:
                print("No ZIP file found in backup folder")
                messagebox.showerror("Restore Error", "No backup ZIP file found in the selected backup folder.")
                return False
            
            zip_file = zip_files[0]
            zip_id = zip_file['id']
            zip_name = zip_file['name']
            print(f"Found ZIP file: {zip_name} (ID: {zip_id})")
            
            # Download the ZIP file
            print(f"Downloading backup ZIP file...")
            zip_path = os.path.join(temp_dir, zip_name)
            
            request = service.files().get_media(fileId=zip_id)
            with open(zip_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    print(f"ZIP download progress: {int(status.progress() * 100)}%")
            
            print(f"Downloaded ZIP file to: {zip_path}")
            
            # Create extraction directory
            extract_dir = os.path.join(temp_dir, "extracted")
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            os.makedirs(extract_dir, exist_ok=True)
            
            # Extract the ZIP file
            print(f"Extracting ZIP file to: {extract_dir}")
            try:
                shutil.unpack_archive(zip_path, extract_dir)
                print(f"Extraction successful. Contents: {os.listdir(extract_dir)}")
            except Exception as extract_error:
                print(f"Extraction error: {extract_error}")
                messagebox.showerror("Restore Error", f"Failed to extract backup ZIP: {str(extract_error)}")
                return False
            
            # Check if extraction worked
            if not os.listdir(extract_dir):
                print("Error: Extracted directory is empty.")
                messagebox.showerror("Restore Error", "The extracted backup is empty.")
                return False
            
            # Create destination directory if it doesn't exist
            os.makedirs(source_path, exist_ok=True)
            print(f"Created/verified destination directory: {source_path}")
            
            # Copy files from extracted directory to destination
            print(f"Copying files to: {source_path}")
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
            
            print(f"Restore completed successfully for {game_title} ✅")
            log_backup_event("cloud_restore", game_title, source_path)
            
            # Clean up temporary files
            try:
                shutil.rmtree(temp_dir)
                print("Temporary files cleaned up.")
            except Exception as cleanup_error:
                print(f"Warning: Could not clean up temporary files: {cleanup_error}")
            
            return True
            
        except Exception as zip_error:
            print(f"Error downloading or extracting ZIP file: {zip_error}")
            messagebox.showerror("Restore Error", f"Failed to download or process backup: {str(zip_error)}")
            return False
            
    except Exception as e:
        print(f"Error restoring cloud backup: {e}")
        messagebox.showerror("Restore Failed", f"Failed to restore backup: {str(e)}")
        return False

def delete_cloud_backup(backup_id):
    """Delete a cloud backup from Google Drive."""
    try:
        print(f"Connecting to Google Drive to delete backup ID: {backup_id}")
        service = get_google_drive_service()
        
        # First get the file info to confirm what we're deleting
        try:
            file_info = service.files().get(fileId=backup_id, fields="name,mimeType,parents").execute()
            print(f"Found file to delete: {file_info.get('name')} ({file_info.get('mimeType')})")
            
            # Get the parent folder ID (game folder)
            parent_id = file_info.get('parents', [None])[0]
            if parent_id:
                print(f"Parent folder ID: {parent_id}")
        except Exception as file_error:
            print(f"Warning: Could not get file info: {file_error}")
            print("Will attempt to delete anyway...")
            parent_id = None
        
        # Try to delete the file
        print(f"Attempting to delete file with ID: {backup_id}")
        service.files().delete(fileId=backup_id).execute()
        print(f"File successfully deleted from Google Drive ✅")
        
        # If we had parent folder info, check if it's empty
        if parent_id:
            try:
                # List contents of the parent folder
                query = f"'{parent_id}' in parents and trashed=false"
                results = service.files().list(q=query, fields="files(id)").execute()
                remaining_files = results.get('files', [])
                
                if not remaining_files:
                    print(f"Parent folder is empty, deleting it...")
                    service.files().delete(fileId=parent_id).execute()
                    print("Empty parent folder deleted successfully")
            except Exception as parent_error:
                print(f"Warning: Could not check/delete parent folder: {parent_error}")
        
        # If we had file info, log it
        if 'file_info' in locals():
            log_backup_event("cloud_delete", file_info.get('name', 'unknown'), f"Google Drive ID: {backup_id}")
        else:
            log_backup_event("cloud_delete", "unknown", f"Google Drive ID: {backup_id}")
        
        return True
        
    except Exception as e:
        print(f"Error deleting cloud backup: {e}")
        messagebox.showerror("Delete Error", f"Failed to delete backup: {str(e)}")
        return False

def select_cloud_backup_dialog():
    """Show a dialog to select a cloud backup to restore."""
    try:
        print("Connecting to Google Drive API...")
        service = get_google_drive_service()
        print("Connected to Google Drive API successfully")
        
        # Find the main backup folder
        print("Looking for main backup folder...")
        main_folder_id = find_or_create_main_folder(service)
        if not main_folder_id:
            print("Failed to locate or create main backup folder in Google Drive")
            MessageBox = ctypes.windll.user32.MessageBoxW
            MessageBox(None, "Could not find or create the main backup folder in Google Drive.\n\nPlease try creating a cloud backup first.", "No Backup Folder Found", 0)
            return None
            
        print(f"Found main folder with ID: {main_folder_id}")
        
        # Check the main folder contents
        print("Checking main folder contents...")
        main_folder_contents = list_folder_contents(service, main_folder_id)
        if not main_folder_contents:
            print("Main backup folder is empty")
            MessageBox = ctypes.windll.user32.MessageBoxW
            MessageBox(None, "The main backup folder is empty.\n\nPlease create a cloud backup first.", "No Backups Found", 0)
            return None
            
        # Get all game folders
        print("Retrieving game folders...")
        game_folders = get_game_folders(service, main_folder_id)
        if not game_folders:
            print("No game backups found in Google Drive")
            MessageBox = ctypes.windll.user32.MessageBoxW
            MessageBox(None, "No game backups found in Google Drive.\n\nPlease create a cloud backup first.", "No Backups Found", 0)
            return None
        
        print(f"Found {len(game_folders)} game folders")
        
        # First, ask which game to restore
        game_titles = [folder['name'] for folder in game_folders]
        print(f"Available games: {', '.join(game_titles)}")
        
        dialog = CustomListDialog(root, "Select Game to Restore", "Select the game backup to restore:", game_titles)
        if dialog.result is None:
            print("User canceled game selection")
            return None
            
        selected_game = game_titles[dialog.result]
        selected_game_id = game_folders[dialog.result]['id']
        print(f"Selected game: {selected_game} (ID: {selected_game_id})")
        
        # Get all backups for the selected game
        print(f"Retrieving backups for {selected_game}...")
        backups = []
        
        # First check if the game folder still exists
        try:
            game_folder_info = service.files().get(fileId=selected_game_id, fields="name").execute()
            print(f"Game folder info: {game_folder_info.get('name')}")
        except Exception as e:
            print(f"Error accessing game folder: {e}")
            MessageBox = ctypes.windll.user32.MessageBoxW
            MessageBox(None, f"Could not access the folder for {selected_game}.\n\nError: {str(e)}", "Folder Access Error", 0)
            return None
        
        # List the contents of the game folder to verify
        print(f"Listing contents of game folder...")
        game_folder_contents = list_folder_contents(service, selected_game_id)
        if not game_folder_contents:
            print(f"Game folder is empty for {selected_game}")
            MessageBox = ctypes.windll.user32.MessageBoxW
            MessageBox(None, f"No backups found for {selected_game}.\n\nPlease create a backup for this game first.", "No Backups Found", 0)
            return None
            
        # Filter for backup folders only
        backup_folders = [item for item in game_folder_contents 
                         if item['mimeType'] == 'application/vnd.google-apps.folder']
        
        if not backup_folders:
            print(f"No backup folders found for {selected_game}")
            MessageBox = ctypes.windll.user32.MessageBoxW
            MessageBox(None, f"No backup folders found for {selected_game}.\n\nPlease create a backup for this game first.", "No Backups Found", 0)
            return None
            
        # Sort backups by creation time (newest first)
        backup_folders.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
        
        # Format backup names for display
        formatted_backups = []
        for backup in backup_folders:
            backup_name = backup['name']
            # The backup name is already in the format "Game Title - YYYY-MM-DD_HH-MM"
            formatted_backups.append(backup_name)
        
        # Ask user to select a specific backup
        backup_dialog = CustomListDialog(root, "Select Backup", "Select which backup to restore:", formatted_backups)
        if backup_dialog.result is None:
            print("User canceled backup selection")
            return None
            
        selected_backup = backup_folders[backup_dialog.result]
        print(f"Selected backup: {selected_backup['name']}")
        
        # Return the selected backup information
        return {
            'game_title': selected_game,
            'backup_name': selected_backup['name'],
            'backup_id': selected_backup['id'],
            'game_folder_id': selected_game_id
        }
        
    except Exception as e:
        print(f"Error in select_cloud_backup_dialog: {e}")
        MessageBox = ctypes.windll.user32.MessageBoxW
        MessageBox(None, f"An error occurred while selecting a backup:\n\n{str(e)}\n\nThis might be due to connectivity issues with Google Drive. Please ensure you have internet access and try again.", "Selection Error", 0)
        return None

def on_create_cloud_backup():
    """Handle create cloud backup button click."""
    try:
        # Get game title
        game_title = simpledialog.askstring("Create Cloud Backup", "Enter the game title:")
        if not game_title:
            return
            
        # Create a custom folder selection dialog
        folder_window = tk.Toplevel(root)
        folder_window.title("Select Source Folder")
        folder_window.geometry("600x400")
        
        # Make sure the window is on top
        folder_window.lift()
        folder_window.attributes('-topmost', True)
        
        # Create a frame for the treeview and buttons
        frame = ttk.Frame(folder_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a treeview for folder selection
        tree = ttk.Treeview(frame, selectmode='browse')
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Cache for loaded folders
        loaded_folders = set()
        
        # Function to populate the treeview
        def populate_tree(path, parent=''):
            try:
                # Skip if already loaded
                if path in loaded_folders:
                    return
                
                # Add the current directory
                dir_name = os.path.basename(path) or path
                item = tree.insert(parent, 'end', text=dir_name, values=[path])
                loaded_folders.add(path)
                
                # Add a dummy item to show expand arrow
                tree.insert(item, 'end', text='Loading...', values=[''])
                
            except Exception as e:
                print(f"Error accessing directory {path}: {e}")
        
        # Function to load subfolders when expanding
        def on_expand(event):
            # Get the item that was expanded
            item = tree.focus()
            if not item:
                return
                
            path = tree.item(item)['values'][0]
            
            # Remove the dummy item
            children = tree.get_children(item)
            if children and tree.item(children[0])['text'] == 'Loading...':
                tree.delete(children[0])
            
            # Load subfolders
            try:
                count = 0
                for entry in os.scandir(path):
                    if entry.is_dir():
                        try:
                            populate_tree(entry.path, item)
                            count += 1
                            if count >= 50:  # Limit subdirectories for performance
                                break
                        except Exception as e:
                            print(f"Error accessing directory {entry.path}: {e}")
                            continue
            except Exception as e:
                print(f"Error loading subfolders for {path}: {e}")
        
        # Bind expand event
        tree.bind('<<TreeviewOpen>>', on_expand)
        
        # Function to populate initial folders
        def populate_initial_folders():
            try:
                # Add drives
                drives = [d for d in os.popen("wmic logicaldisk get caption").read().split()[1:]]
                for drive in drives:
                    if os.path.exists(drive):
                        populate_tree(drive)
                
                # Add special folders
                special_folders = {
                    "Desktop": os.path.expanduser("~/Desktop"),
                    "Documents": os.path.expanduser("~/Documents"),
                    "Downloads": os.path.expanduser("~/Downloads"),
                    "Pictures": os.path.expanduser("~/Pictures"),
                    "Videos": os.path.expanduser("~/Videos"),
                    "Music": os.path.expanduser("~/Music")
                }
                
                for name, path in special_folders.items():
                    if os.path.exists(path):
                        try:
                            populate_tree(path)
                        except Exception as e:
                            print(f"Error accessing {name} folder: {e}")
            except Exception as e:
                print(f"Error populating initial folders: {e}")
        
        # Start populating initial folders in a separate thread
        threading.Thread(target=populate_initial_folders, daemon=True).start()
        
        # Function to handle folder selection
        def on_select():
            selection = tree.selection()
            if selection:
                selected_path = tree.item(selection[0])['values'][0]
                try:
                    # Verify the path exists before proceeding
                    if os.path.exists(selected_path):
                        folder_window.destroy()
                        run_in_thread(lambda: create_cloud_backup(game_title, selected_path),
                                    "Cloud backup created successfully!")
                    else:
                        messagebox.showerror("Error", f"Selected path does not exist: {selected_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Error accessing selected path: {str(e)}")
            else:
                messagebox.showwarning("No Selection", "Please select a folder first.")
        
        # Add buttons
        button_frame = ttk.Frame(folder_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(button_frame, text="Select", command=on_select).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=folder_window.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Center the window
        folder_window.update_idletasks()
        width = folder_window.winfo_width()
        height = folder_window.winfo_height()
        x = (folder_window.winfo_screenwidth() // 2) - (width // 2)
        y = (folder_window.winfo_screenheight() // 2) - (height // 2)
        folder_window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Make the window modal and wait for it
        folder_window.transient(root)
        folder_window.grab_set()
        root.wait_window(folder_window)
        
    except Exception as e:
        print(f"Error in on_create_cloud_backup: {e}")
        messagebox.showerror("Error", f"An error occurred while creating the backup dialog: {str(e)}")

def on_restore_cloud_backup():
    """Handle restore cloud backup button click."""
    backup = select_cloud_backup_dialog()
    if backup:
        # Get the game title from the backup info
        game_title = backup['game_title']
        
        # Check if we have a local backup to determine restore path
        local_backup_path = os.path.join(BASE_BACKUP_LOCATION, game_title)
        readme_path = os.path.join(local_backup_path, "README.txt")
        restore_location = "to its original location"
        
        if not os.path.exists(readme_path):
            restore_location = f"to {os.path.join(BASE_BACKUP_LOCATION, 'recovered_games', game_title)}"
        
        # Show progress window immediately
        progress_window = tk.Toplevel(root)
        progress_window.title("Restoring Backup")
        progress_window.geometry("300x100")
        progress_window.transient(root)
        progress_window.grab_set()
        
        # Add progress message
        ttk.Label(progress_window, text=f"Restoring backup for: {game_title}", 
                 font=("Segoe UI", 10)).pack(pady=(20, 10))
        
        # Function to run restore in a thread
        def restore_thread():
            success = restore_cloud_backup(backup)
            
            # Update UI from main thread
            root.after(0, lambda: on_restore_complete(success, progress_window))
        
        # Handle thread completion
        def on_restore_complete(success, window):
            # Reset cursor
            root.config(cursor="")
            
            # Close progress window
            window.destroy()
            
            # Show appropriate message
            if success:
                messagebox.showinfo("Success", f"Backup for '{game_title}' was restored successfully!")
                # Refresh the backup list if it's currently shown
                run_in_thread(list_drive_backups)
            else:
                messagebox.showerror("Error", 
                                   "There was a problem restoring the backup.\n"
                                   "Check the console for more details.")
        
        # Start the restore thread
        print(f"Starting restore thread for {game_title}")
        threading.Thread(target=restore_thread, daemon=True).start()

def on_delete_cloud_backup():
    """Handle delete cloud backup button click."""
    print("Opening cloud backup selection dialog...")
    backup = select_cloud_backup_dialog()
    
    if backup:
        # Verify we have a valid backup object
        if not isinstance(backup, dict) or 'backup_id' not in backup:
            messagebox.showerror("Error", "Invalid backup selected. Please try again.")
            print(f"Invalid backup object: {backup}")
            return
            
        # Extract backup name and check if it exists
        backup_name = backup.get('backup_name', 'unknown backup')
        backup_id = backup.get('backup_id', None)
        
        if not backup_id:
            messagebox.showerror("Error", "The selected backup has no ID. Cannot delete.")
            print("Missing backup ID")
            return
            
        print(f"Selected backup for deletion: {backup_name} (ID: {backup_id})")
        
        # Single confirmation dialog
        if messagebox.askyesno("Confirm Delete",
                             f"Are you sure you want to delete the cloud backup '{backup_name}'?\n\nThis cannot be undone!"):
            # Show a waiting cursor
            root.config(cursor="wait")
            
            # Create a progress window
            progress_window = tk.Toplevel(root)
            progress_window.title("Deleting Backup")
            progress_window.geometry("300x100")
            progress_window.transient(root)
            progress_window.grab_set()
            
            # Add progress message
            ttk.Label(progress_window, text=f"Deleting backup: {backup_name}", 
                     font=("Segoe UI", 10)).pack(pady=(20, 10))
            
            # Function to run delete in a thread
            def delete_thread():
                success = delete_cloud_backup(backup_id)
                
                # Update UI from main thread
                root.after(0, lambda: on_delete_complete(success, progress_window))
            
            # Handle thread completion
            def on_delete_complete(success, window):
                # Reset cursor
                root.config(cursor="")
                
                # Close progress window
                window.destroy()
                
                # Show appropriate message
                if success:
                    messagebox.showinfo("Success", f"Backup '{backup_name}' was deleted successfully!")
                    # Refresh the backup list if it's currently shown
                    run_in_thread(list_drive_backups)
                else:
                    messagebox.showerror("Error", 
                                       "There was a problem deleting the backup.\n"
                                       "Check the console for more details.")
            
            # Start the delete thread
            print(f"Starting delete thread for backup ID: {backup_id}")
            threading.Thread(target=delete_thread, daemon=True).start()
    else:
        # No backup selected
        messagebox.showinfo("No Selection", "No backup was selected for deletion.")
        print("No backup was selected from the dialog")

def on_list_cloud_backups():
    """Handle list cloud backups button click."""
    # Show waiting cursor
    root.config(cursor="wait")
    
    # Create a status window
    status_window = tk.Toplevel(root)
    status_window.title("Cloud Backups")
    status_window.geometry("700x500")
    status_window.transient(root)
    status_window.grab_set()
    
    # Add a frame with padding for contents
    main_frame = ttk.Frame(status_window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Status label
    status_label = ttk.Label(main_frame, text="Connecting to Google Drive...", font=("Segoe UI", 10, "italic"))
    status_label.pack(anchor=tk.W, pady=(0, 10))
    
    # Create scrolled text for output
    output_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Consolas", 10), height=20)
    output_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
    output_text.config(state=tk.DISABLED)
    
    # Close button
    ttk.Button(main_frame, text="Close", command=status_window.destroy).pack(anchor=tk.SE)
    
    # Add text to the output
    def add_text(text):
        output_text.config(state=tk.NORMAL)
        output_text.insert(tk.END, text + "\n")
        output_text.see(tk.END)
        output_text.config(state=tk.DISABLED)
        status_window.update_idletasks()  # Force update of UI
    
    def list_backups_thread():
        # Redirect stdout to capture print output
        original_stdout = sys.stdout
        stdout_buffer = io.StringIO()
        sys.stdout = stdout_buffer
        
        try:
            backups = list_drive_backups()
            success = True
        except Exception as e:
            backups = []
            add_text(f"Error: {str(e)}")
            success = False
        
        # Restore stdout
        sys.stdout = original_stdout
        
        # Get the captured output
        output = stdout_buffer.getvalue()
        
        # Update UI from main thread
        root.after(0, lambda: update_ui(backups, output, success))
    
    def update_ui(backups, output, success):
        # Reset cursor
        root.config(cursor="")
        
        # Update status
        if success:
            if backups:
                status_label.config(text=f"Found {len(backups)} cloud backup(s)")
            else:
                status_label.config(text="No cloud backups found")
        else:
            status_label.config(text="Error listing cloud backups")
        
        # Add output to text area
        add_text(output)
        
        # If no backups or error, add some help text
        if not backups:
            add_text("\nNo cloud backups were found. Possible reasons:")
            add_text("1. You haven't created any cloud backups yet")
            add_text("2. Your Google Drive account is different from the one you used before")
            add_text("3. There was an error connecting to Google Drive")
            add_text("\nTo create a cloud backup, use the 'Create Cloud Backup' button.")
    
    # Start the thread
    threading.Thread(target=list_backups_thread, daemon=True).start()

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
        return []
        
    try:
        backups = [d for d in os.listdir(BASE_BACKUP_LOCATION) 
                   if os.path.isdir(os.path.join(BASE_BACKUP_LOCATION, d)) 
                   and d != "logs" 
                   and not d.endswith("_backup_")]
        
        if not backups:
            print("No backups found.")
            return []
            
        backup_list = []
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
            
            backup_list.append(f"{backup} - {backup_date}")
            
        return backup_list
    except Exception as e:
        print(f"Error listing backups: {e}")
        return []

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
    """Handler for searching a game on savegame.pro website."""
    game_name = simpledialog.askstring("Search Game", "Enter game name to search:")
    if game_name:
        try:
            print(f"Searching for game: {game_name}")
            search_url = f"{SAVEGAME_PRO_URL}?s={game_name.replace(' ', '+')}"
            
            # Notify user about possible no results message from the website
            messagebox.showinfo("Search Information", 
                              "The browser will open with your search request.\n\n" +
                              "If the website shows 'No items, imagine your search', try:\n" +
                              "- Using different keywords or the game's exact title\n" +
                              "- Checking for spelling errors\n" +
                              "- Searching for a related term")
            
            # Open browser with search
            webbrowser.open(search_url)
            print(f"Opened browser to search for '{game_name}'")
        except Exception as e:
            print(f"Error searching for game: {e}")
            messagebox.showerror("Search Error", f"An error occurred while searching for '{game_name}':\n\n{str(e)}")

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
    
    # Add Google Drive test button
    test_google_drive_btn = ttk.Button(scrollable_frame,
                                     text="Test Google Drive Connection",
                                     width=button_width,
                                     command=on_test_google_drive)
    test_google_drive_btn.pack(fill=tk.X, pady=(0, 5))
    
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

class CustomListDialog:
    """Custom dialog for selecting items from a list."""
    def __init__(self, parent, title, message, items):
        self.result = None
        
        # Create the dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # Create main frame with padding
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Add message label
        ttk.Label(main_frame, text=message, font=("Segoe UI", 11)).pack(anchor=tk.W, pady=(0, 10))
        
        # Create a frame for the listbox with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add listbox
        self.listbox = tk.Listbox(list_frame, font=("Segoe UI", 10), yscrollcommand=scrollbar.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Populate listbox
        for i, item in enumerate(items):
            self.listbox.insert(tk.END, item)
            # Alternate row colors for better readability
            if i % 2 == 0:
                self.listbox.itemconfig(i, {'bg': '#f0f0f0'})
        
        # Add buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # OK button
        ok_btn = ttk.Button(button_frame, text="OK", command=self.on_ok, width=10)
        ok_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Cancel button
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.on_cancel, width=10)
        cancel_btn.pack(side=tk.RIGHT)
        
        # Bind double-click
        self.listbox.bind('<Double-1>', lambda e: self.on_ok())
        
        # Bind Return key
        self.dialog.bind('<Return>', lambda e: self.on_ok())
        self.dialog.bind('<Escape>', lambda e: self.on_cancel())
        
        # Select first item
        if items:
            self.listbox.selection_set(0)
        
        # Wait for the dialog to close
        self.dialog.wait_window()
    
    def on_ok(self):
        """Handle OK button click."""
        selection = self.listbox.curselection()
        if selection:
            self.result = selection[0]
        self.dialog.destroy()
    
    def on_cancel(self):
        """Handle Cancel button click."""
        self.result = None
        self.dialog.destroy()

def test_google_drive_connection(force_refresh=False):
    """Test the Google Drive API connection and permissions."""
    try:
        print("=== Google Drive Connection Test ===")
        
        # Step 1: Connect to Google Drive API
        print("\nStep 1: Connecting to Google Drive API...")
        print(f"Force refresh: {force_refresh}")
        service = get_google_drive_service(force_refresh=force_refresh)
        print("✓ Successfully connected to Google Drive API")
        
        # Step 2: List all accessible files (top-level)
        print("\nStep 2: Listing all accessible files (max 10)...")
        results = service.files().list(
            pageSize=10,
            fields="nextPageToken, files(id, name, mimeType)"
        ).execute()
        items = results.get('files', [])
        
        if not items:
            print("✗ No files found. This may indicate permission issues.")
        else:
            print(f"✓ Found {len(items)} files/folders")
            for item in items:
                item_type = "Folder" if item['mimeType'] == 'application/vnd.google-apps.folder' else "File"
                print(f"  - {item['name']} ({item_type}, ID: {item['id']})")
        
        # Step 3: Test folder creation
        print("\nStep 3: Testing folder creation...")
        test_folder_name = f"Test_Folder_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        folder_metadata = {
            'name': test_folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        try:
            folder = service.files().create(body=folder_metadata, fields='id, name').execute()
            print(f"✓ Successfully created test folder: {folder.get('name')} (ID: {folder.get('id')})")
            
            # Clean up - delete the test folder
            print("\nStep 4: Cleaning up (deleting test folder)...")
            service.files().delete(fileId=folder.get('id')).execute()
            print(f"✓ Successfully deleted test folder")
        except Exception as folder_error:
            print(f"✗ Failed to create or delete test folder: {folder_error}")
            print("This indicates issues with folder creation/deletion permissions.")
        
        print("\n=== Test Complete ===")
        print("If any steps failed, you may need to:", 
              "\n1. Delete your token.pickle file and re-authenticate", 
              "\n2. Check your credentials.json file is valid", 
              "\n3. Ensure you have proper Google Drive permissions")
        
        return True
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        print("\nDetailed troubleshooting steps:")
        print("1. Delete the token.pickle file from your directory")
        print("2. Re-run the application to re-authenticate")
        print("3. Make sure you select a Google account with proper permissions")
        print("4. Check your internet connection")
        print("5. Verify your credentials.json file is correct")
        return False

def on_test_google_drive():
    """Handler for testing Google Drive connection."""
    # Ask user if they want to force refresh
    force_refresh = messagebox.askyesno("Force Refresh", 
                                     "Do you want to force re-authentication?\n\nThis will delete your existing token and make you sign in again to Google Drive.",
                                     icon=messagebox.QUESTION)
    
    # Create progress window
    progress_window = tk.Toplevel(root)
    progress_window.title("Testing Google Drive Connection")
    progress_window.geometry("400x150")
    progress_window.transient(root)
    progress_window.grab_set()
    
    # Center the window
    progress_window.update_idletasks()
    width = progress_window.winfo_width()
    height = progress_window.winfo_height()
    x = (progress_window.winfo_screenwidth() // 2) - (width // 2)
    y = (progress_window.winfo_screenheight() // 2) - (height // 2)
    progress_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
    
    # Add progress information
    frame = ttk.Frame(progress_window, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Testing Google Drive Connection...", font=("Segoe UI", 11, "bold")).pack(pady=(0, 10))
    if force_refresh:
        ttk.Label(frame, text="Re-authenticating with Google Drive...", font=("Segoe UI", 10)).pack(pady=(0, 15))
    else:
        ttk.Label(frame, text="Testing your connection and permissions...", font=("Segoe UI", 10)).pack(pady=(0, 15))
    
    # Add progress bar
    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.pack(fill=tk.X, pady=5)
    progress.start(10)
    
    # Status message
    status_var = tk.StringVar(value="Connecting to Google Drive...")
    status_label = ttk.Label(frame, textvariable=status_var, font=("Segoe UI", 9, "italic"))
    status_label.pack(pady=5)
    
    def on_test_complete(success):
        progress_window.destroy()
        if success:
            messagebox.showinfo("Test Complete", "Google Drive connection test completed. Check the console for detailed results.")
        else:
            messagebox.showerror("Test Failed", "Google Drive connection test failed. Check the console for detailed results.")
    
    def test_thread():
        try:
            success = test_google_drive_connection(force_refresh=force_refresh)
            # Update UI from main thread
            root.after(0, lambda: on_test_complete(success))
        except Exception as e:
            print(f"Error in test thread: {e}")
            root.after(0, lambda: on_test_complete(False))
    
    # Start test in a separate thread
    threading.Thread(target=test_thread, daemon=True).start()

def create_credentials_template():
    """Create a template credentials.json file with instructions."""
    credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
    
    # Don't overwrite existing file without confirmation
    if os.path.exists(credentials_path):
        if not messagebox.askyesno("File Exists", 
                                 f"credentials.json already exists at:\n{credentials_path}\n\nOverwrite it?"):
            return False
    
    # Template content with instructions
    template = '''{
    "IMPORTANT_INSTRUCTIONS": "This is a template file. You need to replace this content with your actual credentials from Google Cloud Console.",
    "HOW_TO_GET_CREDENTIALS": [
        "1. Go to https://console.cloud.google.com/",
        "2. Create a new project or select an existing one",
        "3. Enable the Google Drive API",
        "4. Create OAuth 2.0 Client ID credentials",
        "5. Download the credentials JSON file",
        "6. Replace this file content with the downloaded JSON content"
    ],
    "installed": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "project_id": "YOUR_PROJECT_ID",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "YOUR_CLIENT_SECRET",
        "redirect_uris": ["http://localhost"]
    }
}'''
    
    try:
        with open(credentials_path, 'w') as f:
            f.write(template)
        print(f"Created credentials template at: {credentials_path}")
        
        # Show success message with instructions
        messagebox.showinfo("Template Created", 
                         f"A credentials template file has been created at:\n{credentials_path}\n\n"
                         "Please edit this file and replace its content with the actual credentials JSON "
                         "from Google Cloud Console.")
        return True
    except Exception as e:
        print(f"Error creating credentials template: {e}")
        messagebox.showerror("Error", f"Failed to create credentials template: {str(e)}")
        return False

def check_credentials_valid():
    """Check if the credentials.json file exists and has valid format."""
    credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
    
    if not os.path.exists(credentials_path):
        print(f"credentials.json doesn't exist at: {credentials_path}")
        return False
    
    try:
        with open(credentials_path, 'r') as f:
            content = f.read()
            
        # Check if it's still the template
        if '"IMPORTANT_INSTRUCTIONS"' in content or 'YOUR_CLIENT_ID' in content:
            print("credentials.json is still a template, not actual credentials")
            return False
            
        # Check for required fields
        required_fields = ['"client_id"', '"client_secret"']
        for field in required_fields:
            if field not in content:
                print(f"credentials.json is missing required field: {field}")
                return False
                
        return True
    except Exception as e:
        print(f"Error checking credentials: {e}")
        return False

def on_setup_google_drive():
    """Handler for setting up Google Drive credentials."""
    result = messagebox.askquestion("Google Drive Setup", 
                                 "This will create a template credentials.json file and open instructions in your browser.\n\n"
                                 "Do you want to proceed?")
    if result != 'yes':
        return
        
    # Create template file
    if create_credentials_template():
        # Open browser with instructions
        webbrowser.open("https://developers.google.com/drive/api/quickstart/python")
        
        # Show additional help
        messagebox.showinfo("Next Steps", 
                         "1. Follow the instructions in your browser to set up a Google Cloud project\n"
                         "2. Enable the Google Drive API\n"
                         "3. Create OAuth credentials (Desktop app)\n"
                         "4. Download the JSON file\n"
                         "5. Replace the content of credentials.json with the content from your downloaded file\n\n"
                         "After completing these steps, use the 'Test Google Drive Connection' button.")

# Function to start the GUI
def start_gui():
    """Initialize and start the graphical user interface."""
    global root
    
    root = tk.Tk()
    root.title("Save Game Backup Tool")
    
    # Try to set a larger icon, fallback to default if not found
    try:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass  # Use default icon if custom one fails
    
    # Set window size and position
    window_width = 800
    window_height = 600
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    center_x = int((screen_width - window_width) / 2)
    center_y = int((screen_height - window_height) / 2)
    
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    # Create main frame with padding
    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Title and version
    ttk.Label(main_frame, text="Save Game Backup Tool", font=("Segoe UI", 16, "bold")).pack(pady=(0, 5))
    ttk.Label(main_frame, text="Safely backup and restore your game save files", font=("Segoe UI", 10, "italic")).pack(pady=(0, 15))
    
    # Create a notebook (tabbed interface)
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=10)
    
    # Local backup tab
    local_frame = ttk.Frame(notebook, padding=10)
    notebook.add(local_frame, text="Local Backups")
    
    # Cloud backup tab  
    cloud_frame = ttk.Frame(notebook, padding=10)
    notebook.add(cloud_frame, text="Cloud Backups")
    
    # Tools tab
    tools_frame = ttk.Frame(notebook, padding=10)
    notebook.add(tools_frame, text="Tools")
    
    # Create a scrollable frame for buttons
    # Local buttons
    local_scroll_frame = ttk.Frame(local_frame)
    local_scroll_frame.pack(fill=tk.BOTH, expand=True)
    
    # Add buttons for local backup management with same size
    button_width = 20
    
    # Create a frame for the 1st row of buttons
    local_row1 = ttk.Frame(local_scroll_frame)
    local_row1.pack(fill=tk.X, pady=5)
    
    ttk.Button(local_row1, text="Create Backup", command=on_create_backup, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(local_row1, text="Update Backup", command=on_update_backup, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(local_row1, text="Restore Backup", command=on_restore_backup, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    
    # Create a frame for the 2nd row of buttons
    local_row2 = ttk.Frame(local_scroll_frame)
    local_row2.pack(fill=tk.X, pady=5)
    
    ttk.Button(local_row2, text="Update All Backups", command=on_update_all, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(local_row2, text="Restore All Backups", command=on_restore_all, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(local_row2, text="Delete Backup", command=on_delete_backup, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    
    # Create a frame for the 3rd row of buttons
    local_row3 = ttk.Frame(local_scroll_frame)
    local_row3.pack(fill=tk.X, pady=5)
    
    ttk.Button(local_row3, text="List Backups", command=on_list_backups, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(local_row3, text="View Logs", command=view_logs_gui, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(local_row3, text="List Safety Backups", command=on_list_safety_backups, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    
    # Cloud backup buttons
    cloud_scroll_frame = ttk.Frame(cloud_frame)
    cloud_scroll_frame.pack(fill=tk.BOTH, expand=True)
    
    # First, add a note about requirements for Google Drive
    cloud_info_frame = ttk.Frame(cloud_scroll_frame)
    cloud_info_frame.pack(fill=tk.X, pady=(0, 10))
    
    ttk.Label(cloud_info_frame, 
             text="Google Drive Cloud Backup", 
             font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
    ttk.Label(cloud_info_frame, 
             text="Backup your saves securely to your own Google Drive account", 
             font=("Segoe UI", 10)).pack(anchor=tk.W)
    
    # Setup and test buttons
    cloud_setup_frame = ttk.Frame(cloud_scroll_frame)
    cloud_setup_frame.pack(fill=tk.X, pady=5)
    
    ttk.Button(cloud_setup_frame, text="Setup Google Drive", command=on_setup_google_drive, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(cloud_setup_frame, text="Test Google Drive Connection", command=on_test_google_drive, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    
    # Add cloud backup management buttons
    cloud_row1 = ttk.Frame(cloud_scroll_frame)
    cloud_row1.pack(fill=tk.X, pady=5)
    
    ttk.Button(cloud_row1, text="Create Cloud Backup", command=on_create_cloud_backup, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(cloud_row1, text="Restore Cloud Backup", command=on_restore_cloud_backup, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    
    cloud_row2 = ttk.Frame(cloud_scroll_frame)
    cloud_row2.pack(fill=tk.X, pady=5)
    
    ttk.Button(cloud_row2, text="List Cloud Backups", command=on_list_cloud_backups, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(cloud_row2, text="Delete Cloud Backup", command=on_delete_cloud_backup, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    
    # Tools buttons
    tools_scroll_frame = ttk.Frame(tools_frame)
    tools_scroll_frame.pack(fill=tk.BOTH, expand=True)
    
    # Create a frame for the 1st row of tools buttons
    tools_row1 = ttk.Frame(tools_scroll_frame)
    tools_row1.pack(fill=tk.X, pady=5)
    
    ttk.Button(tools_row1, text="SaveGame.pro Website", command=lambda: webbrowser.open(SAVEGAME_PRO_URL), width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(tools_row1, text="Backup Location", command=lambda: os.startfile(BASE_BACKUP_LOCATION) if sys.platform == 'win32' else webbrowser.open(f"file://{BASE_BACKUP_LOCATION}"), width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(tools_row1, text="Test Mode", command=on_test_mode, width=button_width).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    
    # Console output in text widget
    console_frame = ttk.LabelFrame(main_frame, text="Console Output")
    console_frame.pack(fill=tk.BOTH, expand=True, pady=10)
    
    console_text = scrolledtext.ScrolledText(console_frame, height=10, wrap=tk.WORD, font=("Consolas", 9))
    console_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    console_text.configure(state=tk.DISABLED)  # Make it read-only initially
    
    # Redirect stdout to the text widget
    class TextRedirector:
        def __init__(self, text_widget, tag="stdout"):
            self.text_widget = text_widget
            self.tag = tag
            self.buffer = ""

        def write(self, string):
            self.buffer += string
            if '\n' in string:  # Only update on newline
                self.text_widget.configure(state=tk.NORMAL)
                self.text_widget.insert(tk.END, self.buffer, (self.tag,))
                self.text_widget.see(tk.END)
                self.text_widget.configure(state=tk.DISABLED)
                self.buffer = ""
                # Update the UI
                self.text_widget.update_idletasks()

        def flush(self):
            # Flush any remaining buffer
            if self.buffer:
                self.text_widget.configure(state=tk.NORMAL)
                self.text_widget.insert(tk.END, self.buffer, (self.tag,))
                self.text_widget.see(tk.END)
                self.text_widget.configure(state=tk.DISABLED)
                self.buffer = ""
                # Update the UI
                self.text_widget.update_idletasks()
    
    # Create tag for console text
    console_text.tag_configure("stdout", foreground="black")
    console_text.tag_configure("stderr", foreground="red")
    
    # Save original stdout
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # Connect stdout and stderr to console
    sys.stdout = TextRedirector(console_text, "stdout")
    sys.stderr = TextRedirector(console_text, "stderr")
    
    # Add a status bar at the bottom
    status_bar = ttk.Label(root, text=f"Backup Location: {BASE_BACKUP_LOCATION}", anchor=tk.W, relief=tk.SUNKEN)
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Print welcome message
    print("\nWelcome to the Save Game Backup Tool!")
    print(f"Your backup location is: {BASE_BACKUP_LOCATION}")
    print("Use the buttons above to manage your game save backups.\n")
    
    # Check credentials and show notice if not found
    if not check_credentials_valid():
        print("Notice: Google Drive credentials not found or invalid.")
        print("To use cloud backup features, please click 'Setup Google Drive' button.")
    
    # Prevent text widget from becoming active when clicked
    def disable_focus(event):
        console_text.configure(state=tk.DISABLED)
        return "break"  # Prevent default behavior
    
    console_text.bind("<FocusIn>", disable_focus)
    
    # Function to restore stdout on window close
    def on_closing():
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        root.destroy()
    
    # Bind close event
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start the main loop
    root.mainloop()

# Custom dialog for selecting from a list
class CustomListDialog:
    """A dialog for selecting an item from a list."""
    def __init__(self, parent, title, message, items):
        self.result = None
        
        # Create the dialog window
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        dialog.geometry("500x400")
        dialog.transient(parent)
        dialog.grab_set()
        
        # Make dialog modal
        dialog.focus_set()
        
        # Message
        ttk.Label(dialog, text=message, font=("Segoe UI", 10)).pack(padx=10, pady=10, anchor=tk.W)
        
        # Frame for listbox and scrollbar
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("Segoe UI", 10))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbar
        scrollbar.config(command=self.listbox.yview)
        
        # Add items to listbox
        for item in items:
            self.listbox.insert(tk.END, item)
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Select", command=self.on_select).pack(side=tk.RIGHT, padx=5)
        
        # Double-click to select
        self.listbox.bind("<Double-1>", lambda e: self.on_select())
        
        # Store dialog reference
        self.dialog = dialog
        
        # Wait for the dialog to close
        parent.wait_window(dialog)
    
    def on_select(self):
        """Handle selection."""
        selection = self.listbox.curselection()
        if selection:
            self.result = selection[0]
        self.dialog.destroy()

# Thread utility for running operations in background
def run_in_thread(func, success_message=None):
    """Run a function in a separate thread with progress indication."""
    # Disable the buttons during operation
    for widget in root.winfo_children():
        if isinstance(widget, ttk.Frame):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button):
                    child.configure(state=tk.DISABLED)
    
    # Show waiting cursor
    root.config(cursor="wait")
    
    # Create a progress window
    progress_window = tk.Toplevel(root)
    progress_window.title("Working...")
    progress_window.geometry("300x120")
    progress_window.transient(root)
    progress_window.grab_set()
    
    # Center the window
    progress_window.update_idletasks()
    width = progress_window.winfo_width()
    height = progress_window.winfo_height()
    x = (progress_window.winfo_screenwidth() // 2) - (width // 2)
    y = (progress_window.winfo_screenheight() // 2) - (height // 2)
    progress_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
    
    # Add progress information
    frame = ttk.Frame(progress_window, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Working...", font=("Segoe UI", 11, "bold")).pack(pady=(0, 10))
    
    # Add progress bar
    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.pack(fill=tk.X, pady=5)
    progress.start(10)
    
    # Status message
    status_var = tk.StringVar(value="Please wait...")
    status_label = ttk.Label(frame, textvariable=status_var, font=("Segoe UI", 9, "italic"))
    status_label.pack(pady=5)
    
    def thread_function():
        result = None
        error = None
        
        try:
            result = func()
        except Exception as e:
            error = str(e)
            print(f"Error: {e}")
        
        # Schedule UI update from main thread
        root.after(0, lambda: thread_complete(result, error))
    
    def thread_complete(result, error):
        # Close progress window
        progress_window.destroy()
        
        # Reset cursor
        root.config(cursor="")
        
        # Re-enable buttons
        for widget in root.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button):
                        child.configure(state=tk.NORMAL)
        
        # Show result message if provided and no error occurred
        if error is None and success_message and (result is True or result is None):
            messagebox.showinfo("Success", success_message)
        elif error is not None:
            messagebox.showerror("Error", f"An error occurred: {error}")
    
    # Start the thread
    thread = threading.Thread(target=thread_function)
    thread.daemon = True
    thread.start()

def on_list_backups():
    """Handle list backups button click."""
    def list_backups_thread():
        # Redirect stdout to capture print output
        output_queue = queue.Queue()
        sys.stdout = ThreadSafeConsoleRedirector(output_queue)
        
        try:
            backup_list = list_backups()
            return backup_list, None, True
        except Exception as e:
            return None, str(e), False
        finally:
            sys.stdout = sys.__stdout__
    
    def update_ui(backup_list, error, success):
        # Reset cursor
        root.config(cursor="")
        
        if not success:
            messagebox.showerror("Error", f"Failed to list backups: {error}")
            return
        
        if not backup_list:
            messagebox.showinfo("No Backups", "No backups found.")
            return
        
        # Create a new window for displaying backups
        backup_window = tk.Toplevel(root)
        backup_window.title("Available Backups")
        backup_window.geometry("600x400")
        
        # Create a frame for the listbox and scrollbar
        frame = ttk.Frame(backup_window)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create a listbox with scrollbar
        listbox = tk.Listbox(frame, selectmode=tk.SINGLE)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        # Pack the listbox and scrollbar
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add backups to the listbox
        for backup in backup_list:
            listbox.insert(tk.END, backup)
        
        # Add a close button
        close_button = ttk.Button(backup_window, text="Close", command=backup_window.destroy)
        close_button.pack(pady=10)
        
        # Center the window
        backup_window.update_idletasks()
        width = backup_window.winfo_width()
        height = backup_window.winfo_height()
        x = (backup_window.winfo_screenwidth() // 2) - (width // 2)
        y = (backup_window.winfo_screenheight() // 2) - (height // 2)
        backup_window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Make sure the window is on top
        backup_window.lift()
        backup_window.attributes('-topmost', True)
    
    # Create progress window
    progress_window = tk.Toplevel(root)
    progress_window.title("Listing Backups")
    progress_window.geometry("300x100")
    progress_window.transient(root)
    progress_window.grab_set()
    
    # Center the progress window
    progress_window.update_idletasks()
    width = progress_window.winfo_width()
    height = progress_window.winfo_height()
    x = (progress_window.winfo_screenwidth() // 2) - (width // 2)
    y = (progress_window.winfo_screenheight() // 2) - (height // 2)
    progress_window.geometry(f"{width}x{height}+{x}+{y}")
    
    # Add progress bar and status label
    status_label = ttk.Label(progress_window, text="Listing backups...")
    status_label.pack(pady=10)
    
    progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
    progress_bar.pack(fill=tk.X, padx=20, pady=10)
    progress_bar.start()
    
    # Set cursor to waiting
    root.config(cursor="wait")
    
    # Disable all buttons during operation
    for widget in root.winfo_children():
        if isinstance(widget, ttk.Button):
            widget.configure(state='disabled')
    
    def on_list_complete(backup_list, error, success):
        progress_window.destroy()
        root.config(cursor="")
        
        # Re-enable all buttons
        for widget in root.winfo_children():
            if isinstance(widget, ttk.Button):
                widget.configure(state='normal')
        
        update_ui(backup_list, error, success)
    
    def list_thread():
        try:
            backup_list, error, success = list_backups_thread()
            root.after(0, on_list_complete, backup_list, error, success)
        except Exception as e:
            print(f"Error in list_thread: {e}")
            root.after(0, on_list_complete, None, str(e), False)
    
    # Start the thread
    threading.Thread(target=list_thread, daemon=True).start()

def on_list_safety_backups():
    """Handler for listing safety backups in the GUI"""
    def list_safety_backups_thread():
        # Redirect stdout to capture print output
        output_queue = queue.Queue()
        sys.stdout = ThreadSafeConsoleRedirector(output_queue)
        
        try:
            backups = list_safety_backups()
            return backups, None, True
        except Exception as e:
            return None, str(e), False
        finally:
            sys.stdout = sys.__stdout__
    
    def update_ui(backups, error, success):
        # Reset cursor
        root.config(cursor="")
        
        if not success:
            messagebox.showerror("Error", f"Failed to list safety backups: {error}")
            return
        
        if not backups:
            messagebox.showinfo("No Safety Backups", "No safety backups found.")
            return
        
        # Create a new window for displaying backups
        backup_window = tk.Toplevel(root)
        backup_window.title("Available Safety Backups")
        backup_window.geometry("600x400")
        
        # Create a frame for the listbox and scrollbar
        frame = ttk.Frame(backup_window)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create a listbox with scrollbar
        listbox = tk.Listbox(frame, selectmode=tk.SINGLE)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        
        # Pack the listbox and scrollbar
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add backups to the listbox
        for backup in backups:
            listbox.insert(tk.END, backup)
        
        # Add a close button
        close_button = ttk.Button(backup_window, text="Close", command=backup_window.destroy)
        close_button.pack(pady=10)
    
    # Create progress window
    progress_window = tk.Toplevel(root)
    progress_window.title("Listing Safety Backups")
    progress_window.geometry("300x100")
    progress_window.transient(root)
    progress_window.grab_set()
    
    # Center the progress window
    progress_window.update_idletasks()
    width = progress_window.winfo_width()
    height = progress_window.winfo_height()
    x = (progress_window.winfo_screenwidth() // 2) - (width // 2)
    y = (progress_window.winfo_screenheight() // 2) - (height // 2)
    progress_window.geometry(f"{width}x{height}+{x}+{y}")
    
    # Add progress bar and status label
    status_label = ttk.Label(progress_window, text="Listing safety backups...")
    status_label.pack(pady=10)
    
    progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
    progress_bar.pack(fill=tk.X, padx=20, pady=10)
    progress_bar.start()
    
    # Set cursor to waiting
    root.config(cursor="wait")
    
    # Disable all buttons during operation
    for widget in root.winfo_children():
        if isinstance(widget, ttk.Button):
            widget.configure(state='disabled')
    
    def on_list_complete(backups, error, success):
        progress_window.destroy()
        root.config(cursor="")
        
        # Re-enable all buttons
        for widget in root.winfo_children():
            if isinstance(widget, ttk.Button):
                widget.configure(state='normal')
        
        update_ui(backups, error, success)
    
    def list_thread():
        backups, error, success = list_safety_backups_thread()
        root.after(0, on_list_complete, backups, error, success)
    
    # Start the thread
    threading.Thread(target=list_thread, daemon=True).start()

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