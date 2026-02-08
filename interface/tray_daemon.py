"""
Tray Daemon - System Tray Background Service
Manages the agent's lifecycle and provides system tray access.

Runs as a persistent background process with a system tray icon.
"""
import logging
import sys
from typing import Callable
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer

logger = logging.getLogger(__name__)


class TrayDaemon:
    """
    System tray daemon for the agent.
    
    Provides:
    - System tray icon with menu
    - Show/hide chat window
    - Exit application
    - Privacy mode toggle (future)
    """
    
    def __init__(self, app: QApplication, chat_window, on_exit: Callable[[], None]):
        """
        Initialize the tray daemon.
        
        Args:
            app: QApplication instance
            chat_window: ChatUI instance
            on_exit: Callback when user exits
        """
        self.app = app
        self.chat_window = chat_window
        self.on_exit = on_exit
        
        # Create system tray icon
        self.tray_icon = QSystemTrayIcon(self.app)
        self._setup_tray_icon()
        
        logger.info("TrayDaemon initialized")
    
    def _setup_tray_icon(self):
        """Setup the system tray icon and menu."""
        # Use a default icon (in production, use a custom icon)
        # For now, use QApplication's default icon
        self.tray_icon.setIcon(self.app.style().standardIcon(
            self.app.style().StandardPixmap.SP_ComputerIcon
        ))
        
        self.tray_icon.setToolTip("My Agent - Phase-10B")
        
        # Create menu
        menu = QMenu()
        
        # Show/Hide Chat action
        show_action = QAction("Show Chat", self.app)
        show_action.triggered.connect(self._show_chat)
        menu.addAction(show_action)
        
        hide_action = QAction("Hide Chat", self.app)
        hide_action.triggered.connect(self._hide_chat)
        menu.addAction(hide_action)
        
        menu.addSeparator()
        
        # Status action (disabled, just for display)
        status_action = QAction("Status: Idle", self.app)
        status_action.setEnabled(False)
        menu.addAction(status_action)
        self.status_action = status_action
        
        menu.addSeparator()
        
        # Exit action
        exit_action = QAction("Exit Agent", self.app)
        exit_action.triggered.connect(self._exit_agent)
        menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(menu)
        
        # Double-click to show window
        self.tray_icon.activated.connect(self._on_tray_activated)
        
        # Show the tray icon
        self.tray_icon.show()
        
        logger.info("System tray icon created")
    
    def _on_tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_chat()
    
    def _show_chat(self):
        """Show the chat window."""
        self.chat_window.show()
        self.chat_window.raise_()
        self.chat_window.activateWindow()
        logger.info("Chat window shown")
    
    def _hide_chat(self):
        """Hide the chat window."""
        self.chat_window.hide()
        logger.info("Chat window hidden")
    
    def _exit_agent(self):
        """Exit the application."""
        logger.info("Exit requested from tray")
        
        # Call cleanup callback
        if self.on_exit:
            self.on_exit()
        
        # Hide tray icon
        self.tray_icon.hide()
        
        # Quit application
        self.app.quit()
    
    def update_status(self, status: str):
        """
        Update the status display in the tray menu.
        
        Args:
            status: Status text
        """
        if hasattr(self, 'status_action'):
            self.status_action.setText(f"Status: {status}")
    
    def show_notification(self, title: str, message: str):
        """
        Show a system notification.
        
        Args:
            title: Notification title
            message: Notification message
        """
        self.tray_icon.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            3000  # 3 seconds
        )
