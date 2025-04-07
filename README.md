# Game Backup Manager

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A robust backup solution for PC game saves with version control and cross-platform support.

![Application Screenshot](screenshot.png) <!-- Add screenshot later -->

## Features

- 🕑 Version-controlled backups with timestamps
- 🔄 One-click update/restore for individual games
- ⚡ Bulk operations for all configured games
- 🛡️ Automatic corruption detection
- 🌐 Online save location search integration
- 🎨 Modern GUI with dark/light themes
- 📂 Customizable backup root directory

## Requirements

- Python 3.8+
- Windows/macOS/Linux

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/game-backup-manager.git
cd game-backup-manager
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### GUI Mode (Recommended)
```bash
python main.py --gui
```

### CLI Mode
```bash
python main.py
```

### Key Functions
| Action                | CLI Command | GUI Button        |
|-----------------------|-------------|-------------------|
| Create new backup     | Option 1    | 📁 Create Backup  |
| Update existing       | Option 2    | 🔄 Update Backup  |
| Restore backup        | Option 3    | ⏮️ Restore Backup|
| Change root directory | Option 5    | 📂 Change Root    |

## Configuration

The `game_backup_config.json` file stores settings:
```json
{
    "root_backup_dir": "C:\\save game",
    "games": {
        "Game Name": {
            "source_path": "C:\\Path\\To\\Saves",
            "backup_dir": "C:\\save game\\Game Name"
        }
    }
}
```

## Contributing

1. Fork the repository
2. Create your feature branch:
```bash
git checkout -b feature/your-feature
```
3. Commit changes:
```bash
git commit -m 'Add some feature'
```
4. Push to branch:
```bash
git push origin feature/your-feature
```
5. Open a Pull Request

## License
Distributed under the MIT License. See `LICENSE` for more information.

## Acknowledgments
- CustomTkinter library for modern UI components
- SaveGamePro for save location database