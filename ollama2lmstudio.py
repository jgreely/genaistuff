#!/usr/bin/env python
"""
An API-translation shim that pretends to be an Ollama server and
relays all requests to an LM Studio server. Why? Because SwarmUI's
MagicPrompt extension is flaky with LM Studio.
"""

import time
import json
import asyncio
from fastapi import FastAPI, Request
import lmstudio as lms
import base64
import argparse

listen_addr = "0.0.0.0"
listen_port = 8001

parser = argparse.ArgumentParser(
    prog='ollama2lmstudio',
    add_help=False,
    formatter_class = argparse.RawDescriptionHelpFormatter,
    description = """
        Hacked-together shim that implements just enough of the
        Ollama API to translate MagicPrompt calls to LM Studio
        format, for chat, prompt, and vision.
    """
)
parser.add_argument('-h', '--host',
    type=str, default="localhost",
    help='LM Studio host')
parser.add_argument('-p', '--port',
    type=str, default="1234",
    help='LM Studio port')
parser.add_argument('-H', '--server-host',
    type=str, default="127.0.0.1",
    help='address to listen on (default 127.0.0.1)')
parser.add_argument('-P', '--server_port',
    type=int, default=11434,
    help='port to listen on (default 11434)')
args=parser.parse_args()

app = FastAPI()

lms.configure_default_client(f"{args.host}:{args.port}")
lms.set_sync_api_timeout(120)

# get model list with details, store in Ollama-compat format
models = list()
llm_only = lms.list_downloaded_models("llm")
for model in llm_only:
    # same as output of "lms ls --json"
    model_id = model.model_key
    models.append({
        "id": model.model_key,
        "name": model.model_key,
        "model": model.model_key,
        "version": "1.0.0",
        "modified_at": "2026-01-02T03:04:05Z",
        "size": 8675309,
        "digest": "aaabacadaeaf...",
        "details": {
            "format": "gguf",
            "family": "qwen",
            "parameter_size": "4B",
            "quantization_level": "Q4_K_M"
        }
    })



@app.get("/")
async def root(request: Request):
    """stub"""
    return {
        "result": "success"
    }


@app.get("/api/tags")
async def api_tags(request: Request):
    """lmstudio model list for Ollama API"""
    return {
        "models": models
    }


@app.post("/api/chat")
async def api_chat(request: Request):
    """
    pass an Ollama chat request to LM Studio and return the results
    in Ollama format. If the request includes an images array containing
    one-line base64 strings, convert them for lmstudio
    """
    body = await request.json()

    # TODO: handle all usual options
    model = lms.llm(body["model"])

    messages = body["messages"]
    last_message = messages.pop()
    new_images = list()
    if "images" in last_message:
        # we're doing vision!
        images = last_message["images"]
        for image in images:
            raw = base64.b64decode(image)
            new_images.append(lms.prepare_image(raw))
        last_message["images"] = new_images
    chat = lms.Chat.from_history({
        "messages": messages
    })
    if len(new_images) > 0:
        chat.add_user_message(last_message["content"], images=new_images)
    else:
        chat.add_user_message(last_message["content"])
        
    prediction = model.respond(chat)
    response = prediction.content

    return {
        "stream": False,
        "model": model_id,
        "created_at": "2026-01-02T03:04:05Z",
        "message": {
            "role": "assistant",
            "content": response
        },
        "done": True,
        "total_duration": 1,
        "load_duration": 1,
        "prompt_eval_count": 1,
        "prompt_eval_duration": 1,
        "eval_count": 1,
        "eval_duration": 1
    }

# NOTE: server is exposed on network for remote SwarmUI use;
# don't do this in on a public network.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=listen_addr, port=listen_port)
