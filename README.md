# Save Game Backup Tool

A tool for managing game save backups locally and in the cloud.

## Features

- Local backup creation and management
- Cloud backup using Google Drive
- Automatic backup updates
- Backup restoration
- Backup logging
- User-friendly GUI interface
- Integration with savegame.pro

## Setup

1. Install Python 3.7 or higher
2. Install required packages:
   ```
   pip install -r requirements.txt
   ```

### Google Drive Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Drive API for your project
4. Go to Credentials
5. Create OAuth 2.0 Client ID credentials
6. Download the credentials and save them as `credentials.json` in the same directory as the script
7. Run the script and follow the authentication process when prompted

## Usage

### Local Backups

1. Click "Create Backup" to create a new backup
2. Enter the game title and select the source folder
3. Use "Update Backup" to update existing backups
4. Use "Restore Backup" to restore backups to their original location

### Cloud Backups

1. Click "Create Cloud Backup" to upload a backup to Google Drive
2. Use "List Cloud Backups" to view available cloud backups
3. Use "Restore Cloud Backup" to download and restore a cloud backup
4. Use "Delete Cloud Backup" to remove a backup from Google Drive

## Configuration

The tool uses a `config.ini` file for configuration. You can edit this file to change:
- Base backup location
- Savegame.pro URL

## Logs

All backup operations are logged in the logs directory. You can view the logs using the "View Logs" button.

## Safety Features

- Automatic safety backups before restore operations
- Double confirmation for destructive operations
- Backup verification before restoration
- Error handling and recovery

## Support

For issues or questions, please create an issue in the repository. 