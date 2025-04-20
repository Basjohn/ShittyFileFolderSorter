# Building ShittyFileFolderSorter as an EXE

## Requirements
- Python 3.x
- pip
- [PyInstaller](https://pyinstaller.org/)

## Steps
1. Install dependencies:
   ```sh
   pip install -r requirements.txt
   pip install pyinstaller
   ```
2. Build the executable:
   ```sh
   pyinstaller --onefile main.py
   ```
3. The standalone executable will be in the `dist` folder.

## Notes
- Edit `main.py` as needed before building.
- Update `requirements.txt` with any extra dependencies your script uses.
