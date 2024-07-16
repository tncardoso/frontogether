from PySide6.QtCore import Qt, QObject, QThreadPool, QRunnable, Signal

from frontogether.agent import Agent
from frontogether.server import Server

class ServerWorker(QRunnable):
    def __init__(self):
        super().__init__()
        self._server = Server()

    def stop(self):
        self._server.stop()

    def run(self):
        self._server.run()

class AgentWorkerSignals(QObject):
    content = Signal(str)
    html = Signal(str)
    completed = Signal()

class AgentWorker(QRunnable):
    def __init__(self, agent: Agent, content: str, attachment: str):
        super().__init__()
        self._agent = agent
        self._content = content
        self._attachment = attachment
        self._first_content = True
        self._first_tool = True
        self._user_style = "background-color: #bfffba; color: #050707; font-weight: bold;"
        self._assistant_style = "background-color: #ffc980; color: #2d4b4b; font-weight: bold;"
        self._tool_style = "background-color: #f6baff; color: #2d4b4b; font-weight: bold;"
        self.signals = AgentWorkerSignals()

    def _preffix(self, style: str) -> str:
        return f"<br><hr><span style=\"{style}\">"

    def _suffix(self) -> str:
        return "</span><br><br>"

    def run(self):
        def progress_callback(msg: str):
            if self._first_content:
                self.signals.html.emit(f"{self._preffix(self._assistant_style)}[ assistant ]{self._suffix()}")
                self._first_content = False
            self.signals.content.emit(msg)

        def progress_tool_callback(msg: str):
            if self._first_tool:
                self.signals.html.emit(f"{self._preffix(self._tool_style)}[ tool ]{self._suffix()}")
                self._first_tool = False
                self._first_content = True
            self.signals.content.emit(msg)

        self.signals.html.emit(f"{self._preffix(self._user_style)}[ user ]{self._suffix()}")
        self.signals.content.emit(self._content)

        resp = self._agent.answer(self._content,
            attachment=self._attachment,
            progress_callback=progress_callback,
            progress_tool_callback=progress_tool_callback,
        )
        self.signals.content.emit(f"\n\ncost: {resp.cost}")
        self.signals.completed.emit()
