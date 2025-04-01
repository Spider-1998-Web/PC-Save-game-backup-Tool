# Save Game Backup Tool

A Python application for easily backing up, managing, and restoring video game save files across your computer.

## 🎮 Overview

The Save Game Backup Tool is a command-line utility designed to help gamers create and manage backups of their save game files. Never lose your progress again by maintaining organized backups that can be easily restored when needed.

## 🆕 GUI Interface Now Available!

The tool now features a graphical user interface for easier operation:

![GUI Interface](gui_screenshot.png)

To launch the tool in GUI mode:
```
python Game_Save_backup_script.py --gui
```

Or select "G. Switch to GUI Mode" from the command-line menu.

## ⚙️ Configuration

The tool now uses a configuration file (`config.ini`) that is automatically created on first run. You can easily customize:

- **Backup Location**: The directory where all game backups will be stored
- **URL Settings**: Links to external resources like SaveGame.pro

On first launch, the tool will create a default `config.ini` file in the same directory as the script. You can edit this file with any text editor to customize your settings.

Example `config.ini` file:
```ini
[PATHS]
base_backup_location = C:\save game

[URLS]
savegame_pro_url = https://savegame.pro/
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
- **Configurable Settings**: Easy configuration via an external config file
- **GUI Interface**: User-friendly graphical interface with all features accessible via buttons

## 📋 Requirements

- Python 3.6 or higher
- Windows operating system
- Internet connection (for SaveGame.pro features)
- tkinter (included with standard Python installation)

## 🚀 Getting Started

1. Clone or download this repository
2. Make sure Python is installed on your system
3. Run the script for the first time to generate the configuration file:
   ```
   python Game_Save_backup_script.py
   ```
4. Edit the generated `config.ini` file to set your preferred backup location
5. Run the script again to start using the tool
6. To use the GUI mode, run with the `--gui` flag:
   ```
   python Game_Save_backup_script.py --gui
   ```

## 📝 Usage

### Command-Line Interface

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
G. Switch to GUI Mode
Q. Exit
```

### GUI Interface

The GUI interface provides the same functionality with a more user-friendly experience:

- Left panel: Operation buttons for all functions
- Right panel: Console output showing operation results
- Dialog boxes for input and confirmation
- File browser for selecting save game locations
- Edit Config button for quick access to configuration

### Creating a Backup

1. Select "Create Backup"
2. Enter the game title
3. Optionally search for the save location on SaveGame.pro
4. Enter/browse the source folder path containing the save files

### Restoring a Backup

1. Select "Restore Backup"
2. Choose the game from the displayed list
3. Confirm the restore operation

## 🔒 Safety Features

- **Safety Backups**: The tool automatically creates a safety copy before any restore operation
- **Confirmation Prompts**: Critical operations require explicit confirmation
- **Detailed Logging**: All operations are logged for future reference

## 📚 File Structure

- `Game_Save_backup_script.py`: Main Python script
- `config.ini`: Configuration file (generated on first run)
- `Save Game Backup Tool launcher.bat`: Windows batch launcher
- `BASE_BACKUP_LOCATION/`: Root directory for all backups (location from config)
  - `[Game Title]/`: Individual game backup folders
  - `logs/`: Activity logs
  - `logs/safety_backups/`: Safety backup storage

## 🤝 Credits

- [SaveGame.pro](https://savegame.pro/) for providing a comprehensive database of save game locations 