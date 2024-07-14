import sys
import logging
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QTextEdit
from PySide6.QtWidgets import QLineEdit, QPushButton, QSplitter
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QUrl, QThreadPool, QRunnable, Slot, Signal
from PySide6.QtCore import QObject, QBuffer, QIODevice
from frontogether.server import Server
from frontogether.agent import Agent
from frontogether.worker import ServerWorker, AgentWorker
from frontogether.canvas import Canvas


class FrontogetherGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("frontender")
        self.setGeometry(100, 100, 1200, 800)

        self._agent = Agent()
        self._threadpool = QThreadPool()
        self._server = ServerWorker()
        self._threadpool.start(self._server)

        main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(main_splitter)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        main_splitter.addWidget(left_widget)

        chat_file_splitter = QSplitter(Qt.Vertical)
        left_layout.addWidget(chat_file_splitter)

        # chat history
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        self._chat = QTextEdit()
        self._chat.setReadOnly(True)
        self._chat.insertPlainText(f"[frontogether]\n")
        chat_layout.addWidget(self._chat)

        # chat input
        chat_input_layout = QHBoxLayout()
        self._chat_input = QTextEdit()
        self._chat_input.setMaximumHeight(100)
        chat_input_layout.addWidget(self._chat_input)

        self._send_screen = QCheckBox("attach screenshot")
        chat_input_layout.addWidget(self._send_screen)

        send_button = QPushButton("send")
        send_button.clicked.connect(self.send)
        send_button.setShortcut("Ctrl+Return")
        chat_input_layout.addWidget(send_button)
        chat_layout.addLayout(chat_input_layout)
        chat_file_splitter.addWidget(chat_widget)

        # opened file input
        self._editor = QTextEdit()
        chat_file_splitter.addWidget(self._editor)

        # right pane
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        main_splitter.addWidget(right_widget)

        result_draw_splitter = QSplitter(Qt.Vertical)
        right_layout.addWidget(result_draw_splitter)

        # web view
        self._web_view = QWebEngineView()
        result_draw_splitter.addWidget(self._web_view)
        self._web_view.setZoomFactor(0.25)
        self._web_view.load(QUrl("http://localhost:8000"))

        # canvas
        canvas_widget = QWidget()
        canvas_layout = QVBoxLayout(canvas_widget)
        self._canvas = Canvas()
        canvas_layout.addWidget(self._canvas)

        # canvas menu
        canvas_menu_layout = QHBoxLayout()

        screen_button = QPushButton("screenshot")
        screen_button.clicked.connect(self.screenshot)
        canvas_menu_layout.addWidget(screen_button)

        clear_button = QPushButton("clear")
        clear_button.clicked.connect(self.clear_screenshot)
        canvas_menu_layout.addWidget(clear_button)

        canvas_layout.addLayout(canvas_menu_layout)
        result_draw_splitter.addWidget(canvas_widget)


        # Set initial sizes
        main_splitter.setSizes([600, 600])
        chat_file_splitter.setSizes([400, 400])
        result_draw_splitter.setSizes([400, 400])

    def closeEvent(self, event):
        logging.info("stopping server")
        self._server.stop()
        event.accept()

    def screenshot(self):
        size = self._web_view.contentsRect()
        img = QPixmap(size.width(), size.height())
        self._web_view.render(img)
        #img.save("test.png")
        self._canvas.set_bg(img)
        self._canvas.update()

    def clear_screenshot(self):
        self._canvas.clear()
        self._canvas.update()

    def insert_text(self, msg: str):
        self._chat.insertPlainText(msg)

    def completed(self):
        self._web_view.load(QUrl("http://localhost:8000"))

    def send(self):
        inp = self._chat_input.toPlainText()

        if inp.startswith("/"):
            self._chat.insertPlainText(f"command {inp}")
            if inp.startswith("/open "):
                url = inp.lstrip("/open ")
                self._web_view.load(QUrl(url))
            else:
                self._chat.insertPlainText(f"error: invalid command {inp}")

        else:
            attachment = None
            if self._send_screen.checkState():
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                self._canvas.grab().save(buffer, "PNG")
                attachment = buffer.data().toBase64().toStdString()
                self._send_screen.setChecked(False)

            self.insert_text(f"\nuser: {inp}\n")
            worker = AgentWorker(self._agent, inp, attachment)
            worker.signals.content.connect(self.insert_text)
            worker.signals.completed.connect(self.completed)
            self._threadpool.start(worker)


        self._chat_input.setText("")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FrontogetherGui()
    window.show()
    sys.exit(app.exec())
