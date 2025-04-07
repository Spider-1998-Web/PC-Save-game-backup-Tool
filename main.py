from core.backup_manager import GameBackupCore
from ui.cli_interface import BackupUI
from ui.gui_interface import BackupGUI
import sys

def main():
    core = GameBackupCore()
    
   
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        cli = BackupUI(core)
        cli.show_main_menu()
    else:
        gui = BackupGUI(core)
        gui.run()

if __name__ == "__main__":
    main()