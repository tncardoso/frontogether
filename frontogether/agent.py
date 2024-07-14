import os
import pathlib
import json
import logging
import litellm
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel
from typing import List, Callable

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

        logging.info(f"writing file:", output)
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
                    logging.info(f"skipping file:", path)
        return res


    def _system_prompt(self) -> None:
        temp = self._env.get_template("system.j2")
        self._messages({
            "role": "system",
            "content": temp.render(),
        })

    def _do_call(self,
                 attachment: str = None,
                 progress_callback: Callable[[str], str] = None,
                 progress_tool_callback: Callable[[str], str] = None,
                 finished_callback: Callable[[str], str] = None) -> List[object]:
        resp = litellm.completion(
            model="gpt-4o",
            messages=self._messages,
            tools=self._tools,
            stream=True,
        )
        
        first = True
        chunks = []
        for chunk in resp:
            chunk_tool_calls = chunk.choices[0].delta.get("tool_calls")
            chunk_content = chunk.choices[0].delta.get("content")

            if progress_callback and chunk_tool_calls == None and chunk_content != None:
                if first:
                    progress_callback("\nassistant: ")
                    first = False
                progress_callback(chunk_content)
            elif progress_tool_callback and chunk_tool_calls and len(chunk_tool_calls) > 0:
                func_name = chunk_tool_calls[0].function.name
                if func_name:
                    progress_tool_callback(f"\nfunc({func_name}): ")
                else:
                    progress_tool_callback(f".")
            chunks.append(chunk)

        final = litellm.stream_chunk_builder(chunks)
        tool_calls = final.choices[0].message.get("tool_calls")

        if tool_calls:
            progress_tool_callback(f"\n")
            self._messages.append(final.choices[0].message)
            if finished_callback:
                finished_callback(final.choices[0].message)
              
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                if function_name == "write_file":
                    function_response = self._tool_write_file(
                        function_args.get("filename"),
                        function_args.get("content"),
                    )
                else:
                    raise RuntimeError(f"invalid tool: {function_name}")

                self._messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                })

            
            res = self._do_call(
                attachment=attachment,
                progress_callback=progress_callback,
                progress_tool_callback=progress_tool_callback,
                finished_callback=finished_callback,
            )

            return Result(
                messages=[final.choices[0].message] + res.messages,
                cost=litellm.completion_cost(final) + res.cost,
            )

        return Result(
            messages=[final.choices[0].message],
            cost=litellm.completion_cost(final),
        )

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

        return self._do_call(
            progress_callback=progress_callback,
            progress_tool_callback=progress_tool_callback,
            finished_callback=finished_callback,
        )



if __name__ == "__main__":
    def progress_callback(msg):
        print(f"prog: {msg}")
    a = Agent()
    print(a.answer("create an index with a hello world",
             progress_callback=progress_callback))
