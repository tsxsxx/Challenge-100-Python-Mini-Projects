from PySide6.QtWidgets import QApplication
import sys
import System as st

app = QApplication(sys.argv)
window = st.System()
window.show()
sys.exit(app.exec())
