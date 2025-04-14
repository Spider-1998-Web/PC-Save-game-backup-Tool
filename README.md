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
- 🎨 Modern GUI with dark/light themes (CustomTkinter)
- 📂 Customizable backup root directory
- 🖱️ Mouse-based backup selection in GUI

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

## Usage (GUI Only)

### Launch the Application
```bash
python main.py
```


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
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for modern UI components
- [SaveGamePro](https://savegame.pro/) for save location database

