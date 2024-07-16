import os
import pathlib
import json
import logging
import litellm
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel
from typing import List, Callable, Any

class FileContent(BaseModel):
    filename: str 
    content: str

class Result(BaseModel):
    messages: List[litellm.Message]
    cost: float

class Agent:
    def __init__(self):
        base_dir = pathlib.Path(__file__).parent.resolve()
        prompt_dir = base_dir.joinpath("prompts")
        self._env = Environment(
            loader=FileSystemLoader(prompt_dir),
            autoescape=select_autoescape(),
        )
        self._model = "claude-3-5-sonnet-20240620"
        self._messages = []
        self._tools = [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "",
                            },
                            "content": {
                                "type": "string",
                                "description": "",
                            },
                        },
                        "required": ["filename", "content"],
                    } 
                },
            },
        ]


    def _tool_write_file(self, filename: pathlib.Path, content: str) -> str:
        cwd = pathlib.Path.cwd()
        output = cwd.joinpath(filename).resolve()

        if output.parent != cwd:
            raise RuntimeError(f"only cwd can be written: {cwd}")

        logging.info(f"writing file: %s", output)
        with open(output, "w") as o:
            o.write(content)

        return "true"

    def _read_files(self) -> List[FileContent]:
        res = []
        dir = pathlib.Path.cwd()
        for p in os.listdir(dir):
            path = pathlib.Path(p) 
            if path.is_file():
                try:
                    content = path.read_text()
                    res.append(FileContent(filename=p, content=content))
                except UnicodeError:
                    logging.info(f"skipping file: %s", path)
        return res


    def _system_prompt(self) -> None:
        temp = self._env.get_template("system.j2")
        self._messages({
            "role": "system",
            "content": temp.render(),
        })

    def _do_call(self,
                 messages: List[Any],
                 attachment: str = None,
                 progress_callback: Callable[[str], str] = None,
                 progress_tool_callback: Callable[[str], str] = None,
                 finished_callback: Callable[[str], str] = None) -> List[object]:

        # there is a bug with stream=True and function calling
        # https://github.com/BerriAI/litellm/issues/2716
        # there are some workarounds in chunk processing
        resp = litellm.completion(
            model=self._model,
            messages=messages,
            tools=self._tools,
            stream=True,
        )

        tool_calls = []
        chunks = []
        for chunk in resp:
            logging.info(chunk)
            delta = chunk.choices[0].delta

            if delta.content and delta.content != "":
                if progress_callback:
                    progress_callback(delta.content)

            raw_tool_calls = delta.get("tool_calls", [])
            if raw_tool_calls:
                for tool_call in delta.tool_calls:
                    logging.info("tool_call %s", str(tool_call))
                    if tool_call.id:
                        tool_calls.append(tool_call)
                        if progress_tool_callback:
                            progress_tool_callback(f"\nfunc({tool_call.function.name})")
                    elif tool_call.function.arguments:
                        tool_calls[-1].function.arguments += tool_call.function.arguments
                        if progress_tool_callback:
                            progress_tool_callback(f".")

            chunks.append(chunk)

        final = litellm.stream_chunk_builder(chunks)
        # append tool_calls because of bug
        final.choices[0].message.tool_calls = tool_calls
        logging.info(final)
        if finished_callback:
            finished_callback(final.choices[0].message)

        new_messages = []
        new_messages.append(final.choices[0].message)

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            logging.info(tool_call.function.arguments)
            function_args = json.loads(tool_call.function.arguments)

            if function_name == "write_file":
                function_response = self._tool_write_file(
                    function_args.get("filename"),
                    function_args.get("content"),
                )
            else:
                raise RuntimeError(f"invalid tool: {function_name}")

            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": function_response,
            }

            new_messages.append(tool_msg)

        ret = Result(
            messages=new_messages,
            cost=litellm.completion_cost(final),
        )
            
        if len(tool_calls) > 0:
            # functions were called, get new message
            res = self._do_call(
                messages=messages + new_messages,
                attachment=attachment,
                progress_callback=progress_callback,
                progress_tool_callback=progress_tool_callback,
                finished_callback=finished_callback,
            )

            ret.messages += res.messages
            ret.cost += res.cost

        return ret

    def answer(self, content: str,
               attachment:str = None,
               progress_callback: Callable[[str], str] = None,
               progress_tool_callback: Callable[[str], str] = None,
               finished_callback: Callable[[str], str] = None) -> List[object]:
        files = self._read_files()
        temp = self._env.get_template("message.j2")
        prompt = temp.render(files=files, content=content)

        if attachment:
            self._messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{str(attachment)}",
                        },
                    },
                ],
            })
            #import sys; sys.exit(1)
        else:
            self._messages.append({
                "role": "user",
                "content": prompt,
            })

        ret = self._do_call(
            messages=self._messages,
            progress_callback=progress_callback,
            progress_tool_callback=progress_tool_callback,
            finished_callback=finished_callback,
        )

        self._messages += ret.messages
        return ret


if __name__ == "__main__":
    def progress_callback(msg):
        print(f"prog: {msg}")
    a = Agent()
    print(a.answer("create an index with a hello world",
             progress_callback=progress_callback))
