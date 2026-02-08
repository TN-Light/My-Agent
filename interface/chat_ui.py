"""
Chat UI - User Interaction Window
PySide6-based interface for sending instructions and viewing action logs.

Async-first design to prevent UI freezing during agent reasoning.
"""
import logging
from typing import Optional, Callable
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel
)
from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtGui import QFont, QKeyEvent

logger = logging.getLogger(__name__)


class HistoryLineEdit(QLineEdit):
    """QLineEdit with up/down arrow command history."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._history: list[str] = []
        self._history_index: int = -1
        self._current_text: str = ""
        self.MAX_HISTORY = 100
    
    def add_to_history(self, text: str):
        """Add a command to history (deduplicated)."""
        text = text.strip()
        if not text:
            return
        # Remove duplicate if already in history
        if self._history and self._history[-1] == text:
            pass  # Don't add consecutive duplicates
        else:
            self._history.append(text)
        # Trim to max size
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]
        self._history_index = -1
        self._current_text = ""
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle up/down arrow keys for history navigation."""
        if event.key() == Qt.Key_Up:
            if self._history:
                if self._history_index == -1:
                    # Save current text before navigating
                    self._current_text = self.text()
                    self._history_index = len(self._history) - 1
                elif self._history_index > 0:
                    self._history_index -= 1
                self.setText(self._history[self._history_index])
            return
        elif event.key() == Qt.Key_Down:
            if self._history_index != -1:
                if self._history_index < len(self._history) - 1:
                    self._history_index += 1
                    self.setText(self._history[self._history_index])
                else:
                    # Restore current text
                    self._history_index = -1
                    self.setText(self._current_text)
            return
        else:
            super().keyPressEvent(event)


class ChatSignals(QObject):
    """Signals for cross-thread communication."""
    log_message = Signal(str, str)  # (message, level)
    status_update = Signal(str)     # (status_text)

class WorkerThread(QThread):
    """
    Worker thread to run execution engine logic without freezing UI.
    """
    finished = Signal()
    error = Signal(Exception)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._is_running = True

    def run(self):
        try:
            if self._is_running:
                self.func(*self.args, **self.kwargs)
        except Exception as e:
            self.error.emit(e)
        finally:
            self.finished.emit()

    def stop(self):
        self._is_running = False

class ChatUI(QMainWindow):
    """
    Main chat interface window.
    
    Allows users to:
    - Send natural language instructions
    - View action execution logs in real-time
    - See success/failure status
    
    Phase-UI-A: Observation Rendering
    Display ObservationResult outputs clearly.
    """
    
    def __init__(self, on_instruction: Callable[[str], None]):
        """
        Initialize the chat UI.
        
        Args:
            on_instruction: Callback function when user sends instruction
        """
        super().__init__()
        
        self.on_instruction = on_instruction
        self.signals = ChatSignals()
        self.signals.log_message.connect(self._append_log)
        self.signals.status_update.connect(self._set_status_gui)
        
        self._setup_ui()
        logger.info("ChatUI initialized")
    
    def _setup_ui(self):
        """Setup the UI components."""
        self.setWindowTitle("My Agent - Phase-10B")
        self.setGeometry(100, 100, 700, 500)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Layout
        layout = QVBoxLayout()
        central.setLayout(layout)
        
        # Title
        title = QLabel("Digital Twin Agent - Phase-10B")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Status label
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # Log area
        log_label = QLabel("Observation & Action Log:")
        layout.addWidget(log_label)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 9))
        self.log_area.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.log_area)
        
        # Input area
        input_label = QLabel("Instruction:")
        layout.addWidget(input_label)
        
        input_layout = QHBoxLayout()
        
        self.input_field = HistoryLineEdit()
        self.input_field.setPlaceholderText("Enter instruction (e.g. 'What do you see?') — ↑↓ for history")
        self.input_field.returnPressed.connect(self._on_send)
        input_layout.addWidget(self.input_field)
        
        self.send_button = QPushButton("Execute")
        self.send_button.clicked.connect(self._on_send)
        self.send_button.setFixedWidth(100)
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
        
        # Initial log message
        self.log("Chat UI ready. Supporting: Actions, Observations, and OCR Vision.", "INFO")
    
    def _on_send(self):
        """Handle send button click."""
        instruction = self.input_field.text().strip()
        
        if not instruction:
            return
        
        # Prevent rapid-fire: ignore if a worker is already running
        if hasattr(self, 'worker') and self.worker is not None and self.worker.isRunning():
            self.log("Still processing previous instruction, please wait.", "WARNING")
            return
        
        # Add to command history
        self.input_field.add_to_history(instruction)
        
        # Clear input
        self.input_field.clear()
        
        # Log instruction
        self.log(f"USER: {instruction}", "USER")
        self.set_status("Processing...")
        
        # Disable input during processing
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        
        # Clean up any previous worker thread to avoid leaks
        if hasattr(self, 'worker') and self.worker is not None:
            try:
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except RuntimeError:
                pass  # Signals already disconnected
            self.worker.stop()
            self.worker.quit()
            self.worker.wait(2000)  # Wait up to 2s for graceful shutdown
            self.worker = None
        
        # Offload to worker thread
        self.worker = WorkerThread(self.on_instruction, instruction)
        self.worker.finished.connect(self._on_execution_finished)
        self.worker.error.connect(self._on_execution_error)
        self.worker.start()

    def _on_execution_finished(self):
        """Called when worker thread finishes."""
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.set_status("Idle")
        self.worker = None

    def _on_execution_error(self, e: Exception):
        """Called when worker thread encounters an error."""
        logger.error(f"Error processing instruction: {e}", exc_info=True)
        self.log(f"ERROR: {e}", "ERROR")

    def log(self, message: str, level: str = "INFO"):
        """
        Add a message to the log area.
        
        Args:
            message: Message to log
            level: Log level (INFO, ERROR, SUCCESS, USER)
        """
        self.signals.log_message.emit(message, level)
        # Also print to console for headless debugging/logging capture
        # This ensures the output is visible in the terminal logs for validation
        if level in ["OBSERVATION", "SUCCESS"]:
            print(f"[{level}] {message}")
    
    def _append_log(self, message: str, level: str):
        """Append message to log area (thread-safe via signal)."""
        # Color code by level
        colors = {
            "INFO": "#d4d4d4",
            "ERROR": "#f44747",
            "SUCCESS": "#4ec9b0",
            "USER": "#569cd6",
            "WARNING": "#dcdcaa",
            "OBSERVATION": "#ce9178" # Orange/Peach for Observations
        }
        color = colors.get(level, "#d4d4d4")
        
        # Format with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Special formatting for observations
        if level == "OBSERVATION":
            # Phase-UI-A: Jarvis-style rendering
            # Use a cleaner, more assistant-like bubble
            html = f'''
            <div style="
                margin-top: 8px; 
                margin-bottom: 8px; 
                padding: 10px; 
                border-left: 3px solid #4ec9b0; 
                background-color: #1e1e1e; 
                border-radius: 4px;
                font-family: 'Segoe UI', sans-serif;
            ">
                <div style="color: #4ec9b0; font-size: 11px; margin-bottom: 4px; font-weight: bold;">
                   ASSISTANT [{timestamp}]
                </div>
                <div style="color: #d4d4d4; font-size: 13px; line-height: 1.4;">
                    {message.replace(chr(10), "<br>")}
                </div>
            </div>
            '''
        elif level == "USER":
            html = f'''
            <div style="margin-top: 10px; margin-bottom: 5px; text-align: right;">
                 <span style="
                    background-color: #007acc; 
                    color: white; 
                    padding: 8px 12px; 
                    border-radius: 12px;
                    display: inline-block;
                 ">
                    {message.replace("USER: ", "")}
                 </span>
            </div>
            '''
        else:
             html = f'<div style="color: {color}; font-family: Consolas, monospace; font-size: 11px;">[{timestamp}] {message.replace(chr(10), "<br>")}</div>'
        
        self.log_area.append(html)
    
    def set_status(self, status: str):
        """
        Update the status label (thread-safe).
        
        Args:
            status: Status text to display
        """
        self.signals.status_update.emit(status)

    def _set_status_gui(self, status: str):
        """
        Update the status label (GUI thread only).
        """
        self.status_label.setText(f"Status: {status}")
        
        # Color code
        if "error" in status.lower() or "fail" in status.lower():
            self.status_label.setStyleSheet("color: red; padding: 5px; font-weight: bold;")
        elif "success" in status.lower():
            self.status_label.setStyleSheet("color: green; padding: 5px; font-weight: bold;")
        elif "processing" in status.lower():
            self.status_label.setStyleSheet("color: orange; padding: 5px; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: gray; padding: 5px;")
    
    def closeEvent(self, event):
        """Handle window close event - ensure threads are cleaned up."""
        try:
            logger.info("ChatUI closing - cleaning up threads")
            if hasattr(self, 'worker') and self.worker is not None and self.worker.isRunning():
                self.worker.stop()
                self.worker.quit()
                self.worker.wait(3000)
                self.worker = None
            # Accept the close event
            event.accept()
        except Exception as e:
            logger.error(f"Error during ChatUI close: {e}")
            event.accept()  # Close anyway

