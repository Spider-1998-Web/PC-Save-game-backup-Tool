from core.backup_manager import GameBackupCore
from ui.gui_interface import BackupGUI

def main():
    core = GameBackupCore()
    
    # Launch the GUI directly without checking for CLI argument
    gui = BackupGUI(core)
    gui.run()

if __name__ == "__main__":
    main()


# ;;;;