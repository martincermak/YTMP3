"""
YT MP3 - vstupní bod.

  YTMP3.exe                 spustí okno aplikace
  YTMP3.exe --cli URL DIR   headless režim pro testy (viz core.run_cli)
"""
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        import core

        sys.exit(core.run_cli(sys.argv[2:]))

    from gui import run_gui

    run_gui()
