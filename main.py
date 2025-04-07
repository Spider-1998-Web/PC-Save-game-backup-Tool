from core.backup_manager import GameBackupCore
from ui.cli_interface import BackupUI
from ui.gui_interface import BackupGUI
import sys

def main():
    core = GameBackupCore()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        gui = BackupGUI(core)
        gui.run()
    else:
        cli = BackupUI(core)
        cli.show_main_menu()

if __name__ == "__main__":
    main()