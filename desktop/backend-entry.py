"""PyInstaller entry point; multiprocessing must not re-enter the IPC service."""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if "--self-check" in sys.argv:
        from bookanalyzer.runtime_check import main
    else:
        from bookanalyzer.desktop import main
    main()
