# main_window.py (incorporating multi-file, DB persistence, QTimer fix, OpenAI API)
import sys
import markdown
import re
import os
from pathlib import Path
import tempfile
import uuid
from functools import partial # For connecting signals with arguments
import base64 # Needed if passing base64 directly, but API module handles it
import io     # Needed if passing base64 directly

# --- Library Imports with Error Handling ---
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QTextEdit, QListWidget, QListWidgetItem, QMessageBox,
        QInputDialog, QSplitter, QLabel, QSizePolicy, QFrame, QDialog,
        QDialogButtonBox, QMenu, QScrollArea, QFileDialog, QSpacerItem # Added QSpacerItem
    )
    from PyQt6.QtGui import (
        QAction, QIcon, QColor, QPalette, QFont, QTextCursor,
        QTextBlockFormat, QTextFormat, QFontMetrics, QPixmap, QImage
    )
    from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QObject, QTimer, QMimeData
except ImportError as e:
    print(f"Error importing PyQt6: {e}. Please install it using 'pip install PyQt6'")
    sys.exit(1)

try: from PIL import Image
except ImportError: print("Warning: Pillow library not found. Image support disabled. `pip install Pillow`"); Image = None
try: import fitz # PyMuPDF
except ImportError: print("Warning: PyMuPDF library not found. PDF support disabled. `pip install PyMuPDF`"); fitz = None
try: import markdown
except ImportError: print("Warning: Markdown library not found. Formatting disabled. `pip install Markdown`"); markdown = None

from typing import List, Dict, Optional, Union, Any, Iterator
# --- Local Module Imports ---
import database
import config_manager
# --- CHANGE: Import the new OpenAI API module ---
import openai_api
# ---

# --- Custom Text Edit for Pasting ---
# (PastingTextEdit class remains unchanged)
class PastingTextEdit(QTextEdit):
    image_pasted = pyqtSignal(str)
    def __init__(self, parent=None): super().__init__(parent)
    def insertFromMimeData(self, source: QMimeData):
        if source.hasImage() and Image is not None:
            image = source.imageData()
            if isinstance(image, QImage) and not image.isNull():
                try:
                    temp_dir = tempfile.gettempdir(); filename = f"pasted_image_{uuid.uuid4()}.png"; temp_path = os.path.join(temp_dir, filename)
                    if image.save(temp_path, "PNG"): print(f"Pasted image saved temporarily to: {temp_path}"); self.image_pasted.emit(temp_path)
                    else: print("Error: Failed to save pasted image to temporary file."); super().insertFromMimeData(source)
                except Exception as e: print(f"Error processing pasted image: {e}"); super().insertFromMimeData(source)
            else: super().insertFromMimeData(source)
        else: super().insertFromMimeData(source)


# --- Widget Classes ---
# (TextMessageWidget class remains unchanged)
class TextMessageWidget(QWidget):
    # Uses QTimer to set pixmaps after construction
    def __init__(self, role: str, content_html: str, show_role_label: bool = True,
                 image_paths: List[str] | None = None,
                 image_pixmaps: List[QPixmap] | None = None,
                 parent=None):
        super().__init__(parent)
        print(f"\n--- TextMessageWidget __init__ --- Role: {role}")
        self._role = role # Store role for later use
        self._image_paths = image_paths or []
        self._image_pixmaps = image_pixmaps or []

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 3 if (self._image_paths or self._image_pixmaps) else 5)
        self.layout.setSpacing(4)

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.text_label.setOpenExternalLinks(True)

        style_sheet = ""
        label_text = ""
        label_color = "#E0E0E0"

        if role == "user": style_sheet = "background-color: #4A6A80; color: #FFFFFF; padding: 8px; border-radius: 5px;"; label_text = "You:"; label_color = "#B3E5FC"
        elif role == "model": style_sheet = "background-color: #404040; color: #E0E0E0; padding: 8px; border-radius: 5px;"; label_text = "Assistant:"; label_color = "#A0D0A0" # Changed label
        elif role == "error": style_sheet = "background-color: #6B2E2E; color: #F5CACA; padding: 8px; border-radius: 5px;"; label_text = "Error:"; label_color = "#FFCDD2"
        elif role == "system": style_sheet = "color: #AAAAAA; font-style: italic;"; label_text = ""
        else: style_sheet = "color: #E0E0E0;"; label_text = role.capitalize() + ":"

        final_html = ""
        if label_text and show_role_label:
            final_html += f"<b style='color: {label_color};'>{label_text}</b><br>"
        if content_html.strip():
            final_html += content_html

        # Store style sheet for later use if images are added
        self._base_style_sheet = style_sheet

        # Set initial text label style (might be overridden later if images exist)
        self.text_label.setStyleSheet(f"QLabel {{ {style_sheet} }}")
        self.text_label.setText(final_html)
        self.layout.addWidget(self.text_label)

        # Placeholder for the image container
        self.image_container_widget = None

        self.setLayout(self.layout)

        # Schedule the image loading/setting after this constructor finishes
        if self._role == "user" and (self._image_paths or self._image_pixmaps):
             print("Widget Init: Scheduling _setup_images call.")
             QTimer.singleShot(0, self._setup_images) # Delay=0 means run ASAP in event loop

        print(f"--- TextMessageWidget __init__ END ---")

    def _setup_images(self):
        """Loads/sets pixmaps and adds the image container to the layout."""
        print(f"--- TextMessageWidget _setup_images ---")
        if self.image_container_widget: # Avoid running twice
            print("Setup Images: Already run, skipping.")
            return
        if self._role != "user":
             print("Setup Images: Not user role, skipping.")
             return

        pixmaps_to_display = []
        # Prioritize using preloaded pixmaps
        if self._image_pixmaps:
            for pm in self._image_pixmaps:
                if pm and not pm.isNull():
                    pixmaps_to_display.append(pm)
            print(f"Setup Images: Using {len(pixmaps_to_display)} provided QPixmaps.")

        # Fallback/Supplement with loading from paths
        if self._image_paths:
            print(f"Setup Images: Attempting to load images from paths: {self._image_paths}")
            for img_path in self._image_paths:
                 if os.path.exists(img_path):
                     try:
                         pixmap = QPixmap(img_path)
                         if not pixmap.isNull():
                             pixmaps_to_display.append(pixmap)
                             print(f"Setup Images: Loaded pixmap from path {img_path}. Size: {pixmap.size()}")
                         else: print(f"Setup Images: WARNING - Loaded pixmap isNull for {img_path}")
                     except Exception as e: print(f"Setup Images: ERROR loading pixmap from path {img_path}: {e}")
                 else: print(f"Setup Images: WARNING - Image file not found at path: {img_path}")

        # --- Add the image container if we have pixmaps ---
        if pixmaps_to_display:
             print(f"Setup Images: Creating image container for {len(pixmaps_to_display)} pixmaps.")
             self.image_container_widget = QWidget() # Create container now
             image_layout = QHBoxLayout(self.image_container_widget) # Horizontal layout for images
             image_layout.setContentsMargins(0, 5, 0, 0) # Add some top margin
             image_layout.setSpacing(5)
             max_preview_width = 150 # Smaller previews if multiple
             max_preview_height = 120
             for i, pixmap in enumerate(pixmaps_to_display):
                 if i >= 4: # Limit number of previews shown directly
                      placeholder = QLabel(f"+{len(pixmaps_to_display) - i} more")
                      placeholder.setStyleSheet("color: #AAAAAA; font-style: italic;")
                      image_layout.addWidget(placeholder)
                      break
                 try:
                     img_label = QLabel()
                     scaled_pixmap = pixmap.scaled(max_preview_width, max_preview_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                     img_label.setPixmap(scaled_pixmap)
                     img_label.setToolTip(f"Attachment {i+1}") # Basic tooltip
                     img_label.setStyleSheet("background-color: transparent; border-radius: 3px;")
                     image_layout.addWidget(img_label)
                 except Exception as e: print(f"Setup Images: ERROR creating preview for image {i}: {e}") # LOG
             image_layout.addStretch() # Push images to the left

             # Adjust styles now that images are confirmed
             self.setStyleSheet(f"QWidget {{ {self._base_style_sheet} }}")
             self.text_label.setStyleSheet("background-color: transparent; padding: 0px; border-radius: 0px;")

             # Add the container to the main layout
             print("Setup Images: Adding image container to layout.")
             self.layout.addWidget(self.image_container_widget)
        else:
             print(f"Setup Images: No pixmaps to display.")

        print(f"--- TextMessageWidget _setup_images END ---")


    def _add_placeholder_label(self, text: str):
        # This might be called during __init__ if path loading fails early
        error_label = QLabel(text)
        error_label.setStyleSheet("color: #FFAAAA; font-style: italic; background-color: transparent;")
        self.layout.addWidget(error_label)

# (CodeMessageWidget class remains unchanged)
class CodeMessageWidget(QWidget):
    def __init__(self, language: str, code: str, parent=None):
        super().__init__(parent); self.code_content = code; self.layout = QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 5); self.layout.setSpacing(0)
        header_widget = QWidget(); header_layout = QHBoxLayout(header_widget); header_layout.setContentsMargins(5, 2, 5, 2); lang_label = QLabel(language if language else "Code"); lang_label.setStyleSheet("color: #AAAAAA; font-size: 9pt; background-color: transparent;")
        copy_button = QPushButton("Copy"); copy_button.setFixedSize(60, 22); copy_button.setStyleSheet(""" QPushButton { font-size: 9pt; padding: 2px 5px; background-color: #555; border: 1px solid #666; color: #DDD; border-radius: 3px; min-height: 0px; } QPushButton:hover { background-color: #666; } QPushButton:pressed { background-color: #444; } """); copy_button.clicked.connect(self._copy_code)
        header_layout.addWidget(lang_label); header_layout.addStretch(); header_layout.addWidget(copy_button)
        self.code_display = QTextEdit(); self.code_display.setReadOnly(True); self.code_display.setPlainText(code.strip()); self.code_display.setFont(QFont("Consolas", 10))
        font_metrics = QFontMetrics(self.code_display.font()); line_count = code.strip().count('\n') + 1; content_height = line_count * font_metrics.height() + 20; max_height = 400; actual_height = min(content_height, max_height); self.code_display.setFixedHeight(actual_height)
        self.code_display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if content_height > max_height else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container_style = "background-color: #2A2A2A; border: 1px solid #555; border-radius: 4px;"; self.setStyleSheet(f"QWidget#codeMessageContainer {{ {container_style} }}"); self.setObjectName("codeMessageContainer")
        self.code_display.setStyleSheet(""" QTextEdit { background-color: #2A2A2A; color: #A9B7C6; border: none; padding: 10px; } """)
        self.layout.addWidget(header_widget); self.layout.addWidget(self.code_display); self.setLayout(self.layout)
    def _copy_code(self): clipboard = QApplication.clipboard(); clipboard.setText(self.code_content); print("Code copied to clipboard.")


# --- Worker Class (UPDATED) ---
class GenerationWorker(QObject):
    chunk_received = pyqtSignal(str)
    generation_finished = pyqtSignal(str)
    generation_error = pyqtSignal(str)
    generation_stopped = pyqtSignal()

    def __init__(self, api_key, history, prompt_data: Union[str, list]):
        super().__init__()
        self.api_key = api_key
        self.history = history
        self.prompt_data = prompt_data
        self._is_running = True
        self._full_response = ""

    def run(self):
        try:
            # --- CHANGE: Call the OpenAI API stream function ---
            stream = openai_api.generate_openai_stream(
                self.api_key, self.history, self.prompt_data
            )
            # ---
            for chunk in stream:
                if not self._is_running:
                    self.generation_stopped.emit()
                    return
                self._full_response += chunk
                self.chunk_received.emit(chunk)

            if self._is_running:
                self.generation_finished.emit(self._full_response)
        except Exception as e:
            print(f"Error in generation thread: {e}")
            self.generation_error.emit(str(e)) # Pass the error message

    def stop(self):
        print("Stop signal received by worker.")
        self._is_running = False


# --- Main Window Class ---
class MainWindow(QMainWindow):
    # (__init__ - unchanged)
    def __init__(self):
        super().__init__()
        self.current_chat_id: int | None = None; self.api_key: str | None = None
        self.history_for_api: list[dict[str, Any]] = []; self.generation_thread: QThread | None = None
        self.generation_worker: GenerationWorker | None = None; self.current_model_response = ""
        self.attachments: List[Dict[str, Any]] = [] # List of {'path': str, 'is_temp': bool}

        self.setWindowTitle("Local LLM Client (OpenAI Compatible)"); self.setGeometry(100, 100, 1100, 850) # Updated title
        self._load_api_key()
        if not self.api_key: self._prompt_api_key()
        if not self.api_key: QMessageBox.critical(self, "API Key Error", "API Key is required."); sys.exit(1)

        database.initialize_database(); self._apply_dark_theme(); self._init_ui()
        self._update_attachment_preview_area(); self._load_chats_into_sidebar()

    # (_apply_dark_theme - unchanged)
    def _apply_dark_theme(self):
        dark_palette = QPalette(); dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53)); dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white); dark_palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42)); dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(66, 66, 66)); dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white); dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white); dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white); dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53)); dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white); dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red); dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218)); dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218)); dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black); dark_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(128, 128, 128)); QApplication.instance().setPalette(dark_palette)
        self.setStyleSheet(""" QMainWindow { background-color: #353535; } QWidget { color: #E0E0E0; background-color: #353535; } QMenuBar { background-color: #2E2E2E; color: #E0E0E0; } QMenuBar::item:selected { background-color: #555555; } QMenu { background-color: #2E2E2E; border: 1px solid #555555; color: #E0E0E0; } QMenu::item:selected { background-color: #007ACC; color: #FFFFFF; } QLabel { color: #C0C0C0; background-color: transparent; } QListWidget { background-color: #2A2A2A; border: 1px solid #555555; color: #E0E0E0; font-size: 14px; } QListWidget::item { padding: 5px; } QListWidget::item:selected { background-color: #007ACC; color: #FFFFFF; } QListWidget::item:hover { background-color: #444444; } QScrollArea#chatScrollArea { border: 1px solid #555555; background-color: #2E2E2E; } QWidget#chatContentsWidget { background-color: #2E2E2E; } QTextEdit#userInput { background-color: #3A3A3A; border: 1px solid #555555; color: #F0F0F0; font-size: 11pt; border-radius: 5px; } QPushButton { background-color: #4A4A4A; color: #E0E0E0; border: 1px solid #666666; border-radius: 5px; padding: 8px 12px; font-size: 14px; min-height: 30px; } QPushButton:hover { background-color: #5A5A5A; border: 1px solid #777777; } QPushButton:pressed { background-color: #3A3A3A; } QPushButton:disabled { background-color: #404040; color: #888888; } QPushButton#newChatButton { background-color: #555555; font-weight: bold; } QPushButton#sendButton { background-color: #4CAF50; color: white; font-weight: bold; } QPushButton#sendButton:hover { background-color: #45a049; } QPushButton#sendButton:pressed { background-color: #3e8e41; } QPushButton#sendButton:disabled { background-color: #cccccc; color: #666666; } QPushButton#stopButton { background-color: #F44336; color: white; font-weight: bold; } QPushButton#stopButton:hover { background-color: #E53935; } QPushButton#stopButton:pressed { background-color: #D32F2F; } QSplitter::handle { background-color: #555555; height: 1px; width: 1px; } QSplitter::handle:horizontal { width: 1px; margin: 0 4px; } QSplitter::handle:vertical { height: 1px; margin: 4px 0; } QSplitter::handle:hover { background-color: #777777; }
                           QScrollArea#attachmentScrollArea { border: 1px dashed #555; background-color: #3A3A3A; min-height: 60px; max-height: 120px; }
                           QWidget#attachmentContentsWidget { background-color: #3A3A3A; }
                           QWidget#attachmentItemWidget { background-color: #444; border-radius: 3px; margin: 2px; }
                           QLabel#attachmentItemIcon { min-width: 20px; max-width: 20px; }
                           QLabel#attachmentItemName { color: #DDD; font-size: 9pt; }
                           QPushButton#removeAttachmentButton { color: #CCC; background-color: #555; border: none; border-radius: 8px; font-weight: bold; font-size: 8pt; min-width: 16px; max-width: 16px; min-height: 16px; max-height: 16px; padding: 0px; margin-left: 5px;}
                           QPushButton#removeAttachmentButton:hover { background-color: #777; }
                           QPushButton#removeAttachmentButton:pressed { background-color: #404040; }
                           """)

    # (_init_ui - unchanged)
    def _init_ui(self):
        menu_bar = self.menuBar(); file_menu = menu_bar.addMenu("&File"); settings_action = QAction("Settings", self); settings_action.triggered.connect(self._show_settings); file_menu.addAction(settings_action); exit_action = QAction("Exit", self); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)
        splitter = QSplitter(Qt.Orientation.Horizontal); left_pane = QWidget(); left_layout = QVBoxLayout(left_pane); left_layout.setContentsMargins(5, 5, 5, 5); left_layout.setSpacing(5)
        self.new_chat_button = QPushButton("➕ New Chat"); self.new_chat_button.setObjectName("newChatButton"); self.new_chat_button.clicked.connect(self._handle_new_chat); self.new_chat_button.setFixedHeight(40)
        self.chat_list_label = QLabel("Chat History:"); self.chat_list_widget = QListWidget(); self.chat_list_widget.currentItemChanged.connect(self._handle_chat_selection); self.chat_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.chat_list_widget.customContextMenuRequested.connect(self._show_chat_context_menu)
        left_layout.addWidget(self.new_chat_button); left_layout.addWidget(self.chat_list_label); left_layout.addWidget(self.chat_list_widget); splitter.addWidget(left_pane)
        right_pane = QWidget(); right_layout = QVBoxLayout(right_pane); right_layout.setContentsMargins(10, 5, 10, 10); right_layout.setSpacing(5)
        self.chat_scroll_area = QScrollArea(); self.chat_scroll_area.setObjectName("chatScrollArea"); self.chat_scroll_area.setWidgetResizable(True); self.chat_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_contents_widget = QWidget(); self.chat_contents_widget.setObjectName("chatContentsWidget"); self.chat_layout = QVBoxLayout(self.chat_contents_widget); self.chat_layout.setContentsMargins(10, 10, 10, 10); self.chat_layout.setSpacing(10); self.chat_layout.addStretch()
        self.chat_scroll_area.setWidget(self.chat_contents_widget)
        self.attachment_scroll_area = QScrollArea(); self.attachment_scroll_area.setObjectName("attachmentScrollArea"); self.attachment_scroll_area.setWidgetResizable(True); self.attachment_scroll_area.setFixedHeight(80); self.attachment_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.attachment_scroll_area.setVisible(False)
        self.attachment_contents_widget = QWidget(); self.attachment_contents_widget.setObjectName("attachmentContentsWidget")
        self.attachment_layout = QVBoxLayout(self.attachment_contents_widget); self.attachment_layout.setContentsMargins(2, 2, 2, 2); self.attachment_layout.setSpacing(2); self.attachment_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.attachment_scroll_area.setWidget(self.attachment_contents_widget)
        input_area = QWidget(); input_area_layout = QHBoxLayout(input_area); input_area_layout.setContentsMargins(0,0,0,0); input_area_layout.setSpacing(5)
        self.upload_button = QPushButton("+"); self.upload_button.setObjectName("uploadButton"); self.upload_button.setFixedSize(30, 30); self.upload_button.setToolTip("Attach File(s) (.txt, .pdf, .png, .jpg, .webp)"); self.upload_button.setStyleSheet("QPushButton { font-size: 16pt; padding-bottom: 4px; }"); self.upload_button.clicked.connect(self._handle_upload_files)
        self.user_input = PastingTextEdit(); self.user_input.setObjectName("userInput"); self.user_input.setPlaceholderText("Enter your message here..."); self.user_input.installEventFilter(self); self.user_input.setFixedHeight(80); self.user_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.user_input.image_pasted.connect(self.handle_pasted_image)
        self.send_button = QPushButton("Send"); self.send_button.setObjectName("sendButton"); self.send_button.clicked.connect(self._handle_send_or_stop); self.send_button.setFixedHeight(80); self.send_button.setFixedWidth(80)
        input_area_layout.addWidget(self.upload_button); input_area_layout.addWidget(self.user_input, 1); input_area_layout.addWidget(self.send_button)
        right_layout.addWidget(self.chat_scroll_area); right_layout.addWidget(self.attachment_scroll_area); right_layout.addWidget(input_area)
        splitter.addWidget(right_pane); splitter.setSizes([300, 800]); self.setCentralWidget(splitter); self._set_chat_view_enabled(False)

    # (eventFilter, _load_api_key, _prompt_api_key, _show_settings - unchanged)
    def eventFilter(self, source, event):
        if (source is self.user_input and event.type() == event.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)):
            if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                if self.send_button.text() == "Send": self._handle_send_message()
                return True
        return super().eventFilter(source, event)
    def _load_api_key(self): self.api_key = config_manager.load_api_key(); print("API Key loaded." if self.api_key else "API Key not found in .env.")
    def _prompt_api_key(self, force_prompt=False):
        current_key = config_manager.load_api_key(); prompt_needed = not current_key or force_prompt
        if prompt_needed:
            text, ok = QInputDialog.getText( self, "API Key Required" if not current_key else "Update API Key", f"Enter your Google API Key (used via OpenAI endpoint):", text=current_key or "") # Updated prompt text
            if ok and text: self.api_key = text.strip(); config_manager.save_api_key(self.api_key); print("API Key updated and saved to .env.")
            elif ok and not text: QMessageBox.warning(self, "API Key Empty", "API Key cannot be empty."); self.api_key = None; config_manager.save_api_key("")
            else: self.api_key = current_key
        if not self.api_key: self.api_key = config_manager.load_api_key()
    def _show_settings(self): self._prompt_api_key(force_prompt=True)

    # (_load_chats_into_sidebar, _clear_chat_display, _handle_new_chat - unchanged)
    def _load_chats_into_sidebar(self):
        self.chat_list_widget.clear(); chats = database.get_all_chats()
        if not chats: print("No existing chats found."); return
        for chat_id, title, timestamp in chats:
            display_title = title if title else f"Chat from {timestamp}"; item = QListWidgetItem(display_title); item.setData(Qt.ItemDataRole.UserRole, chat_id); self.chat_list_widget.addItem(item)
        print(f"Loaded {len(chats)} chats into sidebar.")
    def _clear_chat_display(self):
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0); widget = item.widget()
            if widget: widget.deleteLater()
    def _handle_new_chat(self):
        self._stop_generation_if_running(); self.chat_list_widget.clearSelection(); self.current_chat_id = None; self.history_for_api = []
        self._clear_chat_display(); self._clear_all_attachments(); self.user_input.clear(); self.user_input.setPlaceholderText("Enter your message here to start a new chat...")
        self._set_chat_view_enabled(True); self.user_input.setFocus(); print("Started new chat.")

    # (_handle_chat_selection - unchanged, relies on DB format)
    def _handle_chat_selection(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        self._stop_generation_if_running()
        if current_item is None:
            self.current_chat_id = None; self._clear_chat_display(); self.history_for_api = []
            self._clear_all_attachments(); self._set_chat_view_enabled(False); return

        selected_chat_id = current_item.data(Qt.ItemDataRole.UserRole)
        if selected_chat_id == self.current_chat_id: return

        self.current_chat_id = selected_chat_id
        print(f"Selected chat ID: {self.current_chat_id}")
        self._clear_chat_display()
        self._clear_all_attachments() # Clear any pending attachments from previous view
        self.user_input.setPlaceholderText("Enter your message here...")
        self._set_chat_view_enabled(True)

        # Load history, including the parsed list of attachment paths
        loaded_history = database.get_chat_history(self.current_chat_id)
        self.history_for_api = [] # Reset API history context
        print(f"Loading history for chat {self.current_chat_id}. Messages: {len(loaded_history)}")
        for i, message_data in enumerate(loaded_history):
            role = message_data['role']
            # Ensure 'parts' exists and has content before accessing
            content = ""
            if 'parts' in message_data and message_data['parts']:
                content = message_data['parts'][0] # Assuming text is always first part in DB history
            else:
                print(f"Warning: Message data for role {role} at index {i} is missing 'parts' or 'parts' is empty.")


            # Get the list of paths parsed by the database function
            attachment_paths_list = message_data.get('attachment_paths', []) # Default to empty list

            print(f"  Msg {i}: Role={role}, Attachments={attachment_paths_list}") # Log loaded paths

            # Store history in the format needed by _format_openai_messages later
            # We store the simple text part here. The API module will format it.
            self.history_for_api.append({"role": role, "parts": [content]})

            # Pass the list of paths directly to the widget for display
            self._add_message_widget(role, content, image_paths=attachment_paths_list) # Pass the list

        QTimer.singleShot(50, self._scroll_to_bottom)
        self.user_input.setFocus()

    # --- Attachment Handling ---
    # (handle_pasted_image, _handle_upload_files, _remove_specific_attachment, _clear_all_attachments, _update_attachment_preview_area - unchanged)
    def handle_pasted_image(self, temp_file_path: str):
        print(f"Handling pasted image: {temp_file_path}")
        self.attachments.append({'path': temp_file_path, 'is_temp': True})
        print(f"Appended temporary attachment: {temp_file_path}")
        self._update_attachment_preview_area()
    def _handle_upload_files(self):
        file_filter = "Supported Files (*.txt *.pdf *.png *.jpg *.jpeg *.webp);;All Files (*)"
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Attach File(s)", "", file_filter)
        if not file_paths: print("File selection cancelled."); return
        added_count = 0
        for file_path in file_paths:
            if not os.path.exists(file_path): print(f"Skipping non-existent file: {file_path}"); continue
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == ".pdf" and fitz is None: QMessageBox.critical(self, "Missing Library", "PyMuPDF library is required for PDF processing but not installed.\nPlease install it using 'pip install PyMuPDF'."); continue
            if file_ext in ('.png', '.jpg', '.jpeg', '.webp') and Image is None: QMessageBox.critical(self, "Missing Library", "Pillow library is required for image processing but not installed.\nPlease install it using 'pip install Pillow'."); continue
            try:
                file_size = os.path.getsize(file_path); limit_mb = 20 # Keep a reasonable limit
                if file_size > limit_mb * 1024 * 1024: QMessageBox.warning(self, "File Too Large", f"File '{os.path.basename(file_path)}' ({file_size / (1024*1024):.1f} MB) exceeds the limit ({limit_mb}MB). Skipping."); continue
            except OSError as e: QMessageBox.warning(self, "File Error", f"Could not get file size for '{os.path.basename(file_path)}': {e}. Skipping."); continue
            self.attachments.append({'path': file_path, 'is_temp': False}); print(f"Attached file: {file_path}"); added_count += 1
        if added_count > 0: self._update_attachment_preview_area()
    def _remove_specific_attachment(self, path_to_remove: str):
        print(f"--- _remove_specific_attachment --- Path: {path_to_remove}"); found_attachment = None
        for attachment in self.attachments:
            if attachment['path'] == path_to_remove: found_attachment = attachment; break
        if found_attachment:
            is_temp = found_attachment['is_temp']; self.attachments.remove(found_attachment); print(f"Removed attachment from list: {path_to_remove}")
            if is_temp: print(f"Deleting temporary file immediately: {path_to_remove}"); self._delete_temp_file(path_to_remove)
            self._update_attachment_preview_area()
        else: print(f"Warning: Could not find attachment with path {path_to_remove} to remove.")
    def _clear_all_attachments(self):
        print("--- _clear_all_attachments ---"); paths_to_delete = []
        for attachment in self.attachments:
            if attachment['is_temp']: paths_to_delete.append(attachment['path'])
        self.attachments = []; print("Cleared attachments list.")
        for path in paths_to_delete: print(f"Deleting temporary file from clear all: {path}"); self._delete_temp_file(path)
        self._update_attachment_preview_area()
    def _update_attachment_preview_area(self):
        while self.attachment_layout.count():
            item = self.attachment_layout.takeAt(0); widget = item.widget()
            if widget: widget.deleteLater()
        if not self.attachments: self.attachment_scroll_area.setVisible(False); return
        for attachment in self.attachments:
            path = attachment['path']; filename = os.path.basename(path)
            item_widget = QWidget(); item_widget.setObjectName("attachmentItemWidget"); item_layout = QHBoxLayout(item_widget); item_layout.setContentsMargins(4, 2, 4, 2); item_layout.setSpacing(5)
            icon_label = QLabel("📄"); icon_label.setObjectName("attachmentItemIcon") # Placeholder icon
            name_label = QLabel(filename); name_label.setObjectName("attachmentItemName"); name_label.setToolTip(path)
            remove_button = QPushButton("x"); remove_button.setObjectName("removeAttachmentButton"); remove_button.setToolTip(f"Remove {filename}")
            remove_button.clicked.connect(partial(self._remove_specific_attachment, path))
            item_layout.addWidget(icon_label); item_layout.addWidget(name_label, 1); item_layout.addWidget(remove_button)
            self.attachment_layout.addWidget(item_widget)
        self.attachment_scroll_area.setVisible(True)

    # --- Sending Messages and API Interaction ---
    # (_handle_send_or_stop - unchanged)
    def _handle_send_or_stop(self):
        if self.send_button.text() == "Send": self._handle_send_message()
        else: self._stop_generation_if_running()

    # UPDATED: _handle_send_message prepares prompt_data list for new API module
    def _handle_send_message(self):
        print(f"\n--- _handle_send_message START (OpenAI API) ---")
        user_prompt_text = self.user_input.toPlainText().strip(); print(f"User prompt text: '{user_prompt_text}'"); print(f"Number of attachments: {len(self.attachments)}")
        if not user_prompt_text and not self.attachments: print("No prompt or attachments provided."); return
        if not self.api_key: QMessageBox.warning(self, "API Key Missing", "Cannot send message. Please set your API Key in File -> Settings."); return

        # --- Prepare prompt_data for the API module ---
        # This list will contain strings and PIL Image objects
        prompt_data_for_api = []
        error_occurred = False
        sent_attachments = list(self.attachments) # Copy list
        temp_files_sent = []
        image_paths_for_widget = [] # Non-temp image paths for UI
        pixmaps_for_widget = []     # Preloaded QPixmaps for temp images for UI
        non_temp_paths_to_save = [] # Non-temp paths for DB

        # Add text part first if it exists
        if user_prompt_text:
            prompt_data_for_api.append(user_prompt_text)

        print("Processing attachments for API and UI...")
        for attachment in sent_attachments:
            file_path = attachment['path']; is_temp = attachment['is_temp']; print(f"Processing: {file_path} (Temp: {is_temp})")
            if not os.path.exists(file_path): print(f"ERROR: File not found during send processing: {file_path}. Skipping."); error_occurred = True; continue
            file_ext = os.path.splitext(file_path)[1].lower()
            try:
                # Add path to save list if it's NOT temporary
                if not is_temp:
                    non_temp_paths_to_save.append(file_path)

                # Process content for API data list
                if file_ext == ".txt":
                    with open(file_path, 'r', encoding='utf-8') as f: file_content = f.read(); prompt_data_for_api.append(file_content); print("  Added .txt content to API data.")
                elif file_ext == ".pdf":
                    if fitz is None: error_occurred = True; raise ImportError("PyMuPDF not found")
                    pdf_text = ""; doc = fitz.open(file_path);
                    for page in doc: pdf_text += page.get_text("text")
                    doc.close();
                    if pdf_text: prompt_data_for_api.append(pdf_text); print(f"  Added .pdf text content ({len(pdf_text)} chars) to API data.")
                    else: print("  WARNING: Could not extract text from PDF.")
                elif file_ext in ('.png', '.jpg', '.jpeg', '.webp'):
                     if Image is None: error_occurred = True; raise ImportError("Pillow not found")
                     # Load image as PIL object for the API module
                     img = Image.open(file_path); prompt_data_for_api.append(img); print("  Added PIL Image object to API data.")
                     # Also prepare for UI display
                     if is_temp:
                         try:
                             pixmap = QPixmap(file_path)
                             if not pixmap.isNull(): pixmaps_for_widget.append(pixmap); print(f"  Preloaded QPixmap for temp file {file_path}")
                             else: print(f"  WARNING: Failed to preload QPixmap for {file_path}")
                         except Exception as e: print(f"  ERROR preloading QPixmap: {e}")
                     else: image_paths_for_widget.append(file_path) # Add non-temp path for immediate UI display
                else: print(f"  WARNING: Unsupported file type '{file_ext}' for API processing. Skipping content.")

                # Track temporary files sent
                if is_temp: temp_files_sent.append(file_path)

            except FileNotFoundError: print(f"ERROR: File not found during processing: {file_path}"); error_occurred = True
            except ImportError as imp_err: QMessageBox.critical(self, "Missing Library", f"A required library is missing for {file_ext}: {imp_err}"); error_occurred = True
            except Exception as e: QMessageBox.critical(self, "File Read Error", f"Failed to read/process attachment '{os.path.basename(file_path)}': {e}"); error_occurred = True
            if error_occurred: print("Error occurred during attachment processing. Aborting send."); return

        # Ensure we have something to send (either text or processed attachments)
        if not prompt_data_for_api: print("Cannot send empty prompt after processing attachments."); return

        # Determine the final prompt data structure (string if only text, list otherwise)
        # The API module now expects the list format for multimodal, so we pass the list directly if it contains non-text items.
        # If prompt_data_for_api only contains one string, pass that string. Otherwise, pass the list.
        final_api_prompt_data: Union[str, list] = prompt_data_for_api[0] if len(prompt_data_for_api) == 1 and isinstance(prompt_data_for_api[0], str) else prompt_data_for_api


        # Create chat if it's new
        if self.current_chat_id is None:
            title_basis = user_prompt_text if user_prompt_text else f"{len(sent_attachments)} Attachment(s)"; title = title_basis[:30] + "..." if len(title_basis) > 30 else title_basis
            self.current_chat_id = database.create_new_chat(title=title); item = QListWidgetItem(title); item.setData(Qt.ItemDataRole.UserRole, self.current_chat_id); self.chat_list_widget.insertItem(0, item); self.chat_list_widget.setCurrentItem(item)

        # Add user message bubble to UI
        print(f"Calling _add_message_widget for USER with {len(image_paths_for_widget)} paths and {len(pixmaps_for_widget)} pixmaps.")
        self._add_message_widget("user", user_prompt_text, image_paths=image_paths_for_widget, image_pixmaps=pixmaps_for_widget)

        # Save user message to DB (only text and non-temp paths)
        print(f"Saving message to DB. Non-temporary paths: {non_temp_paths_to_save}")
        database.add_message_to_chat(
            self.current_chat_id,
            "user",
            user_prompt_text, # Save only the text part of the user prompt
            attachment_paths=non_temp_paths_to_save # Pass the collected list of non-temp paths
        )

        # Add user message (text only) to the history context for the *next* API call
        self.history_for_api.append({"role": "user", "parts": [user_prompt_text]})

        # Clear input and start generation
        self.user_input.clear(); self._set_generating_state(True); self.current_model_response = ""; self._append_thinking_message_widget()

        # Prepare history context for *this* API call (excluding the message we just added)
        history_context = self.history_for_api[:-1]

        # --- CHANGE: Use the new API module in the worker ---
        self.generation_worker = GenerationWorker(
            self.api_key,
            history_context, # Pass history *before* this turn
            final_api_prompt_data # Pass the prepared list/string
        )
        # ---

        self.generation_thread = QThread(); self.generation_worker.moveToThread(self.generation_thread)
        # (Connect signals - unchanged)
        self.generation_worker.chunk_received.connect(self._handle_chunk); self.generation_worker.generation_finished.connect(self._handle_generation_finished); self.generation_worker.generation_error.connect(self._handle_generation_error); self.generation_worker.generation_stopped.connect(self._handle_generation_stopped)
        self.generation_thread.finished.connect(self._on_thread_finished); self.generation_worker.generation_finished.connect(self.generation_thread.quit); self.generation_worker.generation_error.connect(self.generation_thread.quit); self.generation_worker.generation_stopped.connect(self.generation_thread.quit)
        self.generation_thread.started.connect(self.generation_worker.run); self.generation_thread.start()

        # Clear pending attachments and schedule temp file deletion
        print(f"--- Clearing attachments post-send ---"); self.attachments = []; self._update_attachment_preview_area(); print(f"Cleared attachments list and UI.")
        if temp_files_sent:
            delay_ms = 2000; print(f"Scheduling deletion of {len(temp_files_sent)} temporary files in {delay_ms} ms.")
            for temp_path in temp_files_sent: QTimer.singleShot(delay_ms, partial(self._delete_temp_file, temp_path))
        else: print("No temporary files were sent, no deletion scheduled.")
        print(f"--- _handle_send_message END ---")

    # (Method for delayed deletion - unchanged)
    def _delete_temp_file(self, path_to_delete: str):
        print(f"--- _delete_temp_file (Scheduled Timer/Immediate) --- Path: {path_to_delete}")
        try:
            if os.path.exists(path_to_delete): os.remove(path_to_delete); print(f"SUCCESS: Deleted file: {path_to_delete}")
            else: print(f"WARNING: File no longer exists: {path_to_delete}")
        except OSError as e: print(f"ERROR: Deleting file {path_to_delete}: {e}")
        except Exception as e: print(f"UNEXPECTED ERROR during file deletion: {e}")

    # (_stop_generation_if_running, _append_thinking_message_widget, _remove_thinking_message_widget - unchanged)
    def _stop_generation_if_running(self):
        stopped = False
        if self.generation_thread and self.generation_thread.isRunning(): print("Sending stop signal to worker thread...");
        if self.generation_worker: self.generation_worker.stop(); stopped = True
        return stopped
    def _append_thinking_message_widget(self):
        self._remove_thinking_message_widget(); thinking_label = QLabel("<i>Assistant is thinking...</i>"); thinking_label.setStyleSheet("color: #AAAAAA; margin-bottom: 10px; padding: 8px;"); thinking_label.setObjectName("thinkingWidget") # Changed label
        if self.chat_layout: self.chat_layout.insertWidget(self.chat_layout.count() - 1, thinking_label); QTimer.singleShot(50, self._scroll_to_bottom)
    def _remove_thinking_message_widget(self):
        if not self.chat_layout: return
        for i in range(self.chat_layout.count()):
            item = self.chat_layout.itemAt(i); widget = item.widget()
            if widget and widget.objectName() == "thinkingWidget": widget.deleteLater(); print("Removed thinking widget."); return

    # (_handle_chunk - unchanged)
    def _handle_chunk(self, chunk: str): self.current_model_response += chunk

    # UPDATED: _handle_generation_finished uses 'model' role consistent with DB/history
    def _handle_generation_finished(self, full_response: str):
        print("Generation finished successfully."); self._remove_thinking_message_widget()
        # Use 'model' role internally and for DB, consistent with previous setup
        self._add_message_widget("model", full_response)
        if self.current_chat_id is not None:
            database.add_message_to_chat(self.current_chat_id, "model", full_response)
            # Add response to history using internal format
            self.history_for_api.append({"role": "model", "parts": [full_response]})
        self._set_generating_state(False); QTimer.singleShot(50, self._scroll_to_bottom)

    # (_handle_generation_error, _handle_generation_stopped - unchanged logic, maybe update labels)
    def _handle_generation_error(self, error_msg: str):
        print(f"Generation error: {error_msg}"); self._remove_thinking_message_widget();
        # Display the error message received from the worker/API module
        self._add_message_widget("error", f"API Error: {error_msg}")
        self._set_generating_state(False); QTimer.singleShot(50, self._scroll_to_bottom)
    def _handle_generation_stopped(self):
        print("Generation stopped by user."); self._remove_thinking_message_widget(); stopped_message = "[Stopped by user]"
        if self.current_model_response:
            final_display_content = self.current_model_response.strip() + f"\n\n{stopped_message}"
            # Use 'model' role for partially generated content
            self._add_message_widget("model", final_display_content)
        else:
            self._add_message_widget("system", stopped_message)
        self._set_generating_state(False); QTimer.singleShot(50, self._scroll_to_bottom)

    # (_on_thread_finished, _cleanup_thread_references - unchanged)
    def _on_thread_finished(self): print("Generation thread finished signal received."); self._cleanup_thread_references()
    def _cleanup_thread_references(self): print("Cleaning up thread references."); self.generation_worker = None; self.generation_thread = None; self._set_generating_state(False)

    # (_set_chat_view_enabled, _set_generating_state - unchanged)
    def _set_chat_view_enabled(self, enabled: bool):
        self.user_input.setEnabled(enabled); self.upload_button.setEnabled(enabled)
        if not enabled: self.user_input.setPlaceholderText("Select a chat or start a new one."); self.send_button.setEnabled(False)
        else:
            is_generating = (self.generation_thread is not None and self.generation_thread.isRunning())
            if not is_generating: self.user_input.setPlaceholderText("Enter your message here..."); self.send_button.setEnabled(True)
            else: self.user_input.setPlaceholderText("Waiting for response..."); self.send_button.setEnabled(True) # Keep send (stop) enabled
    def _set_generating_state(self, is_generating: bool):
        if is_generating: self.send_button.setText("Stop"); self.send_button.setObjectName("stopButton"); self.user_input.setEnabled(False); self.upload_button.setEnabled(False); self.user_input.setPlaceholderText("Waiting for response..."); self.send_button.setEnabled(True)
        else:
            self.send_button.setText("Send"); self.send_button.setObjectName("sendButton"); can_interact = self.current_chat_id is not None
            self.user_input.setEnabled(can_interact); self.upload_button.setEnabled(can_interact)
            if can_interact: self.user_input.setPlaceholderText("Enter your message here...")
            else: self.user_input.setPlaceholderText("Select a chat or start a new one.")
            # Check if input has text OR attachments to enable send
            can_send = can_interact and (bool(self.user_input.toPlainText().strip()) or bool(self.attachments))
            self.send_button.setEnabled(can_send)
        # Re-apply stylesheet to update button appearance
        self.style().unpolish(self.send_button); self.style().polish(self.send_button)


    # --- Adding Message Widgets to UI ---
    # UPDATED: _add_message_widget uses 'model' role consistently
    def _add_message_widget(self, role: str, raw_content: str,
                            image_paths: List[str] | None = None,
                            image_pixmaps: List[QPixmap] | None = None):
        print(f"\n--- _add_message_widget --- Role: {role}")
        # Standardize on 'model' for assistant responses internally
        display_role = "model" if role == "assistant" else role

        if display_role == "user":
            html_content = self._format_content_html(raw_content)
            print(f"Creating TextMessageWidget for USER with {len(image_paths or [])} paths and {len(image_pixmaps or [])} pixmaps.")
            widget = TextMessageWidget(display_role, html_content, show_role_label=True, image_paths=image_paths, image_pixmaps=image_pixmaps)
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, widget)
            QTimer.singleShot(50, self._scroll_to_bottom); return

        # Handle model/error/system roles (including code blocks)
        code_block_pattern = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL); last_end = 0; widget_added = False; is_first_widget_for_role = True
        for match in code_block_pattern.finditer(raw_content):
            start, end = match.span(); language = match.group(1).strip(); code = match.group(2).strip()
            text_part = raw_content[last_end:start].strip()
            if text_part:
                html_content = self._format_content_html(text_part); show_label=(display_role != "model") or is_first_widget_for_role
                widget = TextMessageWidget(display_role, html_content, show_role_label=show_label)
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, widget); widget_added = True; is_first_widget_for_role = False
            # Add code block widget
            widget = CodeMessageWidget(language, code); self.chat_layout.insertWidget(self.chat_layout.count() - 1, widget); widget_added = True; is_first_widget_for_role = False; last_end = end

        # Handle any remaining text after the last code block
        remaining_text = raw_content[last_end:].strip()
        if remaining_text:
            html_content = self._format_content_html(remaining_text); show_label=(display_role != "model") or is_first_widget_for_role
            widget = TextMessageWidget(display_role, html_content, show_role_label=show_label)
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, widget); widget_added = True
        # Handle case where the entire message is just text (no code blocks)
        elif not widget_added and raw_content.strip():
             html_content = self._format_content_html(raw_content); show_label=(display_role != "model") or is_first_widget_for_role
             widget = TextMessageWidget(display_role, html_content, show_role_label=show_label)
             self.chat_layout.insertWidget(self.chat_layout.count() - 1, widget)

        QTimer.singleShot(50, self._scroll_to_bottom)


    # (_format_content_html, _scroll_to_bottom - unchanged)
    def _format_content_html(self, text: str) -> str:
        def escape_html(txt): return txt.replace('&', '&').replace('<', '<').replace('>', '>').replace('\n', '<br>') # Basic escape
        if markdown:
            try:
                # Basic Markdown extensions
                html = markdown.markdown(text, extensions=['nl2br', 'fenced_code', 'tables', 'sane_lists'])
                return html
            except Exception as e:
                print(f"Error formatting content with Markdown: {e}")
                return escape_html(text) # Fallback to basic escaping
        else:
            return escape_html(text) # Fallback if Markdown lib is missing
    def _scroll_to_bottom(self): scrollbar = self.chat_scroll_area.verticalScrollBar(); QTimer.singleShot(0, lambda: scrollbar.setValue(scrollbar.maximum()))

    # (_show_chat_context_menu, _delete_selected_chat - unchanged)
    def _show_chat_context_menu(self, position):
        item = self.chat_list_widget.itemAt(position);
        if not item: return
        menu = QMenu(); delete_action = QAction("Delete Chat", self); delete_action.triggered.connect(lambda: self._delete_selected_chat(item)); menu.addAction(delete_action)
        menu.setStyleSheet(""" QMenu { background-color: #2E2E2E; border: 1px solid #555555; color: #E0E0E0; } QMenu::item:selected { background-color: #007ACC; color: #FFFFFF; } """)
        menu.exec(self.chat_list_widget.mapToGlobal(position))
    def _delete_selected_chat(self, item: QListWidgetItem):
        chat_id_to_delete = item.data(Qt.ItemDataRole.UserRole);
        if not chat_id_to_delete: return
        reply = QMessageBox.question( self, "Confirm Delete", f"Are you sure you want to delete the chat '{item.text()}'? This cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if chat_id_to_delete == self.current_chat_id: self._stop_generation_if_running()
            print(f"Attempting to delete chat ID: {chat_id_to_delete}"); database.delete_chat(chat_id_to_delete)
            if chat_id_to_delete == self.current_chat_id: self._handle_new_chat() # Reset view if current chat deleted
            self.chat_list_widget.takeItem(self.chat_list_widget.row(item)); print(f"Chat ID {chat_id_to_delete} deleted successfully.")

    # (closeEvent - unchanged)
    def closeEvent(self, event):
        print("Close event triggered."); self._clear_all_attachments(); stopped = self._stop_generation_if_running(); finished_gracefully = True
        if stopped and self.generation_thread:
            print("Waiting for generation thread to finish before closing..."); finished_gracefully = self.generation_thread.wait(2000);
            if not finished_gracefully: print("Warning: Generation thread did not finish within timeout. Forcing quit."); self.generation_thread.quit(); self.generation_thread.wait(100)
            else: print("Generation thread finished gracefully.")
        self._cleanup_thread_references(); print("Closing application."); event.accept()

# (main execution block in main.py remains unchanged)