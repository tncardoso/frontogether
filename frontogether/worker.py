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
    completed = Signal()

class AgentWorker(QRunnable):
    def __init__(self, agent: Agent, content: str, attachment: str):
        super().__init__()
        self._agent = agent
        self._content = content
        self._attachment = attachment
        self.signals = AgentWorkerSignals()

    def run(self):
        def progress_callback(msg: str):
            self.signals.content.emit(msg)

        def progress_tool_callback(msg: str):
            self.signals.content.emit(msg)

        resp = self._agent.answer(self._content,
            attachment=self._attachment,
            progress_callback=progress_callback,
            progress_tool_callback=progress_tool_callback,
        )
        self.signals.content.emit(f"\n\ncost: {resp.cost}")
        self.signals.completed.emit()
