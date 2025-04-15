
__version__ = "4.1"
import sys
import subprocess
import os


def install_dependencies():
    """Install required packages if missing"""
    required = ['customtkinter']
    missing = []
    
    # Check for missing packages
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        print("First-run setup: Installing GUI dependencies...")
        try:
            # Install missing packages
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            
            # Restart application
            print("\nInstallation complete! Launching GUI...")
            os.execl(sys.executable, sys.executable, *sys.argv)
            
        except subprocess.CalledProcessError as e:
            print(f"Automatic installation failed: {str(e)}")
            print("Please install manually with:")
            print(f"pip install {' '.join(missing)}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error during installation: {str(e)}")
            sys.exit(1)

def launch_gui():
    """Directly start the GUI"""
    try:
        from core.backup_manager import GameBackupCore
        from ui.gui_interface import BackupGUI
        
        core = GameBackupCore()
        app = BackupGUI(core)
        app.run()
    except ImportError as e:
        print(f"Error importing GUI components: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        install_dependencies()
        launch_gui()
    except Exception as e:
        print(f"Error during setup or launch: {str(e)}")
        sys.exit(1)
