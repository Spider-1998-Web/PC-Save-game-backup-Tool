# Save Game Backup Tool

A Python application for easily backing up, managing, and restoring video game save files across your computer.

## 🎮 Overview

The Save Game Backup Tool is a command-line utility designed to help gamers create and manage backups of their save game files. Never lose your progress again by maintaining organized backups that can be easily restored when needed.

## ⚠️ Important Configuration Note

**Before using this tool, you MUST modify the base save location:**

The default backup location is set to `E:\save game`. You need to change this to a valid path on your system by editing the `BASE_BACKUP_LOCATION` variable at the top of the `Game_Save_backup_script.py` file:

```python
# Change this path to where you want to store your backups
BASE_BACKUP_LOCATION = "E:\\save game"  # Default path
```

## ✨ Features

- **Create Backups**: Back up save files from any game to a central location
- **Update Backups**: Keep your backups current with the latest save data
- **Restore Backups**: Restore saved games to their original locations when needed
- **Batch Operations**: Update or restore all backups at once
- **Safety Measures**: Automatic safety backups before any restore operations
- **Logging System**: Comprehensive activity logs to track all backup operations
- **SaveGame.pro Integration**: Look up save game locations directly through the app
- **Game Save Search**: Search for specific games on SaveGame.pro

## 📋 Requirements

- Python 3.6 or higher
- Windows operating system
- Internet connection (for SaveGame.pro features)

## 🚀 Getting Started

1. Clone or download this repository
2. Make sure Python is installed on your system
3. **Edit the `Game_Save_backup_script.py` file to set your preferred backup location (see Important Configuration Note above)**
4. Run the launcher batch file or execute the Python script directly:
   ```
   python Game_Save_backup_script.py
   ```

## 📝 Usage

The application presents a simple menu-driven interface:

```
Options:
1. Create Backup
2. Update Backup
3. Restore Backup
4. Update All Backups
5. Restore All Backups
6. List Backups
7. List Safety Backups
8. View Logs
9. Open SaveGame.pro Website
D. Delete Backup
S. Search Game on SaveGame.pro
Q. Exit
```

### Creating a Backup

1. Select option 1
2. Enter the game title
3. Optionally search for the save location on SaveGame.pro
4. Enter the source folder path containing the save files

### Restoring a Backup

1. Select option 3
2. Choose the game from the displayed list
3. Confirm the restore operation

## ⚙️ Configuration

The application stores all data in the location specified by `BASE_BACKUP_LOCATION`. The default structure includes:
- Main backup directory: `E:\save game` (or your custom path)
- Logs directory: `E:\save game\logs`
- Safety backups: `E:\save game\logs\safety_backups`

## 🔒 Safety Features

- **Safety Backups**: The tool automatically creates a safety copy before any restore operation
- **Confirmation Prompts**: Critical operations require explicit confirmation
- **Detailed Logging**: All operations are logged for future reference

## 📚 File Structure

- `Game_Save_backup_script.py`: Main Python script
- `Save Game Backup Tool launcher.bat`: Windows batch launcher
- `BASE_BACKUP_LOCATION/`: Root directory for all backups
  - `[Game Title]/`: Individual game backup folders
  - `logs/`: Activity logs
  - `logs/safety_backups/`: Safety backup storage

## 🤝 Credits

- [SaveGame.pro](https://savegame.pro/) for providing a comprehensive database of save game locations 