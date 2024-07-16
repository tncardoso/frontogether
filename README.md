# Frontogether

Frontogether is a tool for creating webpages with LLM assistance. It can read and write files in the current directory. You can interact with it using chat or screenshots.

## Usage

    $ mkdir workingdir && cd workingdir
    $ python path/to/gui.py

## Limitations

Currently the chat history is not prunned or summarized. Requests can get expensive because of tool calling and file contents. If you notice costs increasing, you can close and reopen the GUI at any time.
