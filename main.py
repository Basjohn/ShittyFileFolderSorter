import sys
import os
import shutil
import itertools
import re
from difflib import SequenceMatcher
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, QFileDialog,
                            QProgressBar, QLabel, QMessageBox, QCheckBox, QDialog, QDialogButtonBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon
import logging

# Suppress deprecation warnings
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Set high DPI attributes before creating QApplication
if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


class SortingThread(QThread):
    update_progress = pyqtSignal(int)
    finished_signal = pyqtSignal()
    status_update = pyqtSignal(str)
    
    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self.moved_files = []  # For undo functionality
        self.media_sort_enabled = False
    
    def find_common_sequence(self, str1, str2, min_length=4):
        """Find common sequence between two strings with minimum length."""
        # Extract just the filename without extension for comparison
        name1, _ = os.path.splitext(str1)
        name2, _ = os.path.splitext(str2)
        
        # Convert to lowercase for case-insensitive matching
        name1 = name1.lower()
        name2 = name2.lower()
        
        # Find the longest common substring
        match = SequenceMatcher(None, name1, name2).find_longest_match(0, len(name1), 0, len(name2))
        if match.size >= min_length:
            common_str = name1[match.a:match.a + match.size]
            # Make sure the common string is meaningful (not just spaces or special chars)
            if re.search(r'[a-zA-Z0-9]{4,}', common_str):
                return common_str
        return None
    
    def get_all_files(self):
        """Get all files in the specified folder (not subdirectories)."""
        return [f for f in os.listdir(self.folder_path) 
                if os.path.isfile(os.path.join(self.folder_path, f))]
    
    def get_recursive_files(self):
        """Get all files in the specified folder including subdirectories."""
        file_paths = []
        for root, _, files in os.walk(self.folder_path):
            for file in files:
                file_paths.append(os.path.join(root, file))
        return file_paths
    
    def move_file_handling_conflicts(self, src, dst):
        """Move file and handle naming conflicts. Return the destination path."""
        final_dst = dst
        if os.path.exists(dst):
            # Handle conflict
            base, ext = os.path.splitext(dst)
            for i in range(1, 100):
                new_dst = f"{base}-CF{i}{ext}"
                if not os.path.exists(new_dst):
                    final_dst = new_dst
                    break
            # If we get here and final_dst is still dst, we've run out of conflict names
            if final_dst == dst:
                self.status_update.emit(f"Too many conflicts for {dst}")
                return None
        
        # Store the original path and destination for undo functionality
        self.moved_files.append((src, final_dst))
        
        # Perform the move
        try:
            shutil.move(src, final_dst)
            return final_dst
        except Exception as e:
            logging.error(f"Error moving file {src} to {final_dst}: {e}")
            return None
    
    def build_similarity_groups(self, files):
        """Build groups of files based on common substrings in their names."""
        # Dictionary to store groups of files with common substrings
        groups = {}
        
        # Compare each pair of files
        for file1, file2 in itertools.combinations(files, 2):
            common = self.find_common_sequence(file1, file2)
            if common:
                # Use the common sequence as the group key
                if common not in groups:
                    groups[common] = set()
                groups[common].add(file1)
                groups[common].add(file2)
        
        # Sort groups by size (largest first) and then by common string length
        sorted_groups = sorted(groups.items(), 
                              key=lambda x: (len(x[1]), len(x[0])), 
                              reverse=True)
        
        return sorted_groups
    
    def process_media_files(self):
        """Sort media files into Images and Videos folders within each subfolder."""
        # Define media file extensions
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif',
                          '.heic', '.heif', '.svg', '.eps', '.ico', '.psd', '.xcf', '.raw',
                          '.cr2', '.nef', '.arw', '.dng')
        
        video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
                          '.mpg', '.mpeg', '.3gp', '.rm', '.rmvb', '.vob', '.ts', '.mxf',
                          '.ogv')
        
        # Count files of each type
        image_count = 0
        video_count = 0
        
        # Get all subdirectories (excluding special folders like Images and Videos themselves)
        subdirs = []
        for item in os.listdir(self.folder_path):
            item_path = os.path.join(self.folder_path, item)
            if os.path.isdir(item_path) and item not in ["Images", "Videos"]:
                subdirs.append(item_path)
        
        # Process each subdirectory
        for subdir in subdirs:
            # Get all files in this subdirectory (not recursive)
            files = [f for f in os.listdir(subdir) if os.path.isfile(os.path.join(subdir, f))]
            
            # Count media files of each type
            images = [f for f in files if f.lower().endswith(image_extensions)]
            videos = [f for f in files if f.lower().endswith(video_extensions)]
            
            # Process images if any exist
            if images:
                # Create Images subfolder
                images_dir = os.path.join(subdir, "Images")
                os.makedirs(images_dir, exist_ok=True)
                
                # Move image files
                for file in images:
                    src = os.path.join(subdir, file)
                    dst = os.path.join(images_dir, file)
                    self.move_file_handling_conflicts(src, dst)
                    image_count += 1
            
            # Process videos if any exist
            if videos:
                # Create Videos subfolder
                videos_dir = os.path.join(subdir, "Videos")
                os.makedirs(videos_dir, exist_ok=True)
                
                # Move video files
                for file in videos:
                    src = os.path.join(subdir, file)
                    dst = os.path.join(videos_dir, file)
                    self.move_file_handling_conflicts(src, dst)
                    video_count += 1
        
        # Update status
        if image_count > 0 or video_count > 0:
            self.status_update.emit(f"Sorted {image_count} images and {video_count} videos within their group folders")
    
    def run(self):
        """Main sorting algorithm."""
        original_files = self.get_all_files()
        total_files = len(original_files)
        
        if total_files == 0:
            self.status_update.emit("No files found in the directory")
            self.finished_signal.emit()
            return
            
        # Track which files we've processed
        processed_files = set()
        processed_count = 0
        
        # First phase: Group files by common names
        self.status_update.emit("Phase 1: Grouping files by similarity...")
        
        # Keep processing until all files are sorted
        while True:
            # Get files that haven't been processed yet
            remaining_files = [f for f in self.get_all_files() 
                              if f not in processed_files]
            if not remaining_files:
                break
            
            # Build groups of files with common substrings
            groups = self.build_similarity_groups(remaining_files)
            
            # If no groups formed, place remaining files in "Miscellaneous"
            if not groups:
                if remaining_files:
                    misc_folder = os.path.join(self.folder_path, "Miscellaneous")
                    os.makedirs(misc_folder, exist_ok=True)
                    for file in remaining_files:
                        src = os.path.join(self.folder_path, file)
                        dst = os.path.join(misc_folder, file)
                        self.move_file_handling_conflicts(src, dst)
                        processed_files.add(file)
                        processed_count += 1
                        self.update_progress.emit(int(processed_count / total_files * 100))
                break
            
            # Process the largest group first
            common_str, file_set = groups[0]
            
            # Create a folder with the common string
            folder_name = common_str.strip()
            if not folder_name:  # Safety check
                folder_name = "Common_Group"
            
            # Clean folder name of invalid characters
            for char in r'<>"/\|?*':
                folder_name = folder_name.replace(char, '_')
            
            folder_path = os.path.join(self.folder_path, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            
            # Move files to the folder and mark them as processed
            for file in file_set:
                if file not in processed_files:
                    src = os.path.join(self.folder_path, file)
                    if os.path.exists(src):
                        dst = os.path.join(folder_path, file)
                        self.move_file_handling_conflicts(src, dst)
                        processed_files.add(file)
                        processed_count += 1
                        self.update_progress.emit(int(processed_count / total_files * 100))
            
            # Update progress after a group is processed
            self.update_progress.emit(int(processed_count / total_files * 100))
        
        # Second phase: Media file sorting (if enabled)
        if self.media_sort_enabled:
            self.status_update.emit("Phase 2: Sorting media files...")
            self.process_media_files()
        
        self.update_progress.emit(100)
        self.finished_signal.emit()
    
    def undo_sorting(self):
        """Restore files to their original locations."""
        try:
            for original_path, current_path in reversed(self.moved_files):
                if os.path.exists(current_path):
                    try:
                        # Ensure the parent directory exists
                        parent_dir = os.path.dirname(original_path)
                        if not os.path.exists(parent_dir):
                            os.makedirs(parent_dir, exist_ok=True)
                        
                        shutil.move(current_path, original_path)
                    except Exception as e:
                        logging.error(f"Error restoring {current_path} to {original_path}: {e}")
            
            # Remove empty folders that were created during sorting
            for root, dirs, files in os.walk(self.folder_path, topdown=False):
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    if os.path.exists(dir_path) and not os.listdir(dir_path):  # Check if directory is empty
                        try:
                            os.rmdir(dir_path)
                        except Exception as e:
                            logging.error(f"Error removing empty directory {dir_path}: {e}")
        except Exception as e:
            logging.error(f"Error during undo operation: {e}")


class UndoThread(QThread):
    finished_signal = pyqtSignal()
    
    def __init__(self, sorting_thread):
        super().__init__()
        self.sorting_thread = sorting_thread
    
    def run(self):
        try:
            if self.sorting_thread:
                self.sorting_thread.undo_sorting()
            self.finished_signal.emit()
        except Exception as e:
            logging.error(f"Error in UndoThread: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shitty File Folder Sorter")
        self.setMinimumSize(600, 250)
        
        # Set application icon
        self.setup_icon()
        
        # Create central widget and layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)
        
        # Create folder selection widgets
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Enter folder path...")
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.folder_input, 3)
        folder_layout.addWidget(browse_button, 1)
        main_layout.addLayout(folder_layout)
        
        # Create media sorting checkbox
        self.media_sort_checkbox = QCheckBox("Sort images and videos into separate folders")
        self.media_sort_checkbox.setToolTip("After initial sorting, create separate folders for images and videos based on file extensions")
        
        # Create sort button
        self.sort_button = QPushButton("Sort Into Folders")
        self.sort_button.setMinimumHeight(40)
        self.sort_button.clicked.connect(self.start_sorting)
        
        # Create progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setHidden(True)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        
        # Create undo button (initially hidden)
        self.undo_button = QPushButton("Undo")
        self.undo_button.clicked.connect(self.undo_sorting)
        self.undo_button.setHidden(True)
        
        # Add widgets to main layout
        main_layout.addWidget(self.media_sort_checkbox)
        main_layout.addWidget(self.sort_button)
        main_layout.addWidget(self.progress_bar)
        
        # Layout for status and undo button
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.status_label, 4)
        status_layout.addWidget(self.undo_button, 1)
        main_layout.addLayout(status_layout)
        
        # Add question mark button (bottom right)
        self.question_button = QPushButton()
        self.question_button.setFixedSize(28, 28)
        self.question_button.setToolTip('About/Donate/Books')
        self.question_button.clicked.connect(self.show_info_dialog)
        self.question_button.raise_()
        # Overlay the button in the bottom right
        self.floating_layout = QHBoxLayout()
        self.floating_layout.addStretch()
        self.floating_layout.addWidget(self.question_button)
        main_layout.addLayout(self.floating_layout)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Set stylesheet for a modern look
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton {
                background-color: #4a86e8;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3a76d8;
            }
            QPushButton:pressed {
                background-color: #2a66c8;
            }
            QPushButton#undo_button {
                background-color: #e84a4a;
            }
            QPushButton#undo_button:hover {
                background-color: #d83a3a;
            }
            QPushButton#undo_button:pressed {
                background-color: #c82a2a;
            }
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4a86e8;
                border-radius: 3px;
            }
            QCheckBox {
                spacing: 5px;
                color: #333;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        
        # Thread instance variables
        self.sorting_thread = None
        self.undo_thread = None
        self.previous_session = None
        
    def setup_icon(self):
        """Set up application icon."""
        # Create icon directory if it doesn't exist
        icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
        os.makedirs(icon_dir, exist_ok=True)
        
        # Path to the icon file
        icon_path = os.path.join(icon_dir, "app_icon.png")
        
        # Check if the icon exists, if not create a default one
        if not os.path.exists(icon_path):
            # If the specified icon path exists, copy it
            specified_icon = "D:\\Artwork\\Entrystuffs\\UsuWobbleBIG.jpg"
            if os.path.exists(specified_icon):
                try:
                    shutil.copy(specified_icon, icon_path)
                except Exception:
                    # If copy fails, we'll use a default icon below
                    pass
        
        # Set the icon if it exists
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
    def browse_folder(self):
        """Open file dialog to select a folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Sort")
        if folder:
            self.folder_input.setText(folder)
        
    def start_sorting(self):
        """Start the sorting process in a separate thread."""
        folder_path = self.folder_input.text()
        if not folder_path or not os.path.exists(folder_path):
            QMessageBox.warning(self, "Error", "Please select a valid folder")
            return
        
        # Save the current sorting state as previous session only if we have one
        if self.sorting_thread and self.sorting_thread.moved_files:
            self.previous_session = self.sorting_thread.moved_files.copy()
            self.undo_button.setText("Undo Previous Session")
        else:
            self.undo_button.setText("Undo")
        
        self.undo_button.setHidden(False)
        
        self.sort_button.setDisabled(True)
        self.progress_bar.setHidden(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Sorting in progress...")
        
        self.sorting_thread = SortingThread(folder_path)
        self.sorting_thread.update_progress.connect(self.update_progress)
        self.sorting_thread.status_update.connect(self.update_status)
        self.sorting_thread.finished_signal.connect(self.sorting_finished)
        self.sorting_thread.media_sort_enabled = self.media_sort_checkbox.isChecked()
        self.sorting_thread.start()
        
    def update_progress(self, value):
        """Update progress bar value."""
        self.progress_bar.setValue(value)
        
    def update_status(self, message):
        """Update status label."""
        self.status_label.setText(message)
        
    def sorting_finished(self):
        """Called when sorting is complete."""
        self.sort_button.setEnabled(True)
        self.progress_bar.setValue(100)
        self.status_label.setText("Sorting complete!")
        
    def undo_sorting(self):
        if self.previous_session:
            # Undo previous session
            self.undo_button.setText("Undo")
            self.previous_session = None
            
            # Create a new thread for undoing the previous session
            self.undo_thread = UndoThread(self.sorting_thread)
            self.undo_thread.finished_signal.connect(self.undo_complete)
            self.undo_thread.start()
        else:
            # Regular undo
            if self.sorting_thread:
                self.undo_thread = UndoThread(self.sorting_thread)
                self.undo_thread.finished_signal.connect(self.undo_complete)
                self.undo_thread.start()
        
    def undo_complete(self):
        """Called when undo operation is complete."""
        # Re-enable UI elements
        self.undo_button.setHidden(True)
        self.sort_button.setEnabled(True)
        self.status_label.setText("Changes undone!")
        QMessageBox.information(self, "Undo Complete", "All changes have been reverted.")
        
    def show_info_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Support / About')
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog)
        msg = QLabel('Made to sort out particularly obnoxious folders.  Donations or money wasted on my shitty literature are welcome')
        msg.setWordWrap(True)
        layout.addWidget(msg)
        # Bold clickable text links instead of icons
        links_label = QLabel()
        links_label.setText('<b><a href="https://www.paypal.com/donate/?business=UBZJY8KHKKLGC&no_recurring=0&item_name=Why+are+you+doing+this?+Are+you+drunk?+&currency_code=USD">Donate via PayPal</a></b><br>'
                            '<b><a href="https://www.goodreads.com/book/show/25006763-usu">Usu on Goodreads</a></b><br>'
                            '<b><a href="https://www.amazon.com/dp/B00ZV9PXP2">Usu on Amazon</a></b>')
        links_label.setOpenExternalLinks(True)
        links_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        layout.addWidget(links_label)
        # OK button
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        dialog.exec_()
        
    def open_url(self, url):
        import webbrowser
        webbrowser.open(url)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.ERROR,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'error.log')
    )
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
