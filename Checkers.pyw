"""
Бесконсольный запуск приложения «Шашки — Анализатор & Оверлей».
При двойном клике в Windows запускается через pythonw.exe без появления окна консоли.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Шашечный Аналитик")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
