import json
from typing import Iterator
from adapters.base import ModelAdapter
from adapters.protocol import ChatCompletionRequest, ChatCompletionResponse, CompletionRequest, CompletionResponse
from loguru import logger
from clients.xunfei_spark.api.spark_api import SparkAPI
import time
import uuid


class XunfeiSparkAPIModel(ModelAdapter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app_id = kwargs.pop("app_id")
        self.api_key = kwargs.pop("api_key")
        self.api_secret = kwargs.pop("api_secret")
        self.api_model_version = kwargs.pop("api_model_version")
        self.prompt = kwargs.pop(
            "prompt", "You need to follow the system settings:{system}"
        )
        self.config_args = kwargs
        self.api_connection = SparkAPI(
            self.app_id, self.api_key, self.api_secret, self.api_model_version
        )

    def chat_completions(
        self, request: ChatCompletionRequest
    ) -> Iterator[ChatCompletionResponse]:
        messages = self.openai_to_client_params_chat_completions(request)
        kargs = {
            "chat_id": uuid.uuid1(),
        }
        if request.temperature:
            # openai 取值0-2 xunfei  0-1
            kargs["temperature"] = request.temperature / 2
        if request.max_length:
            kargs["max_tokens"] = request.max_length

        kargs.update(self.config_args)
        iter_content = self.api_connection.get_resp_from_messages(messages, **kargs)

        if request.stream:
            for line in iter_content:
                code = line["header"]["code"]
                if code != 0:
                    logger.error(f"请求失败:{line}")
                    raise Exception(f"请求失败:{line}")
                openai_response = self.client_response_2_chatgpt_response_stream(line)
                yield ChatCompletionResponse(**openai_response)
        else:
            openai_response = self.client_response_to_chatgpt_response_chat_completions(iter_content)
            yield ChatCompletionResponse(**openai_response)

    def completions(
        self, request: CompletionRequest
    ) -> Iterator[CompletionResponse]:
        messages = self.openai_to_client_params_completions(request)
        kargs = {
            "chat_id": uuid.uuid1(),
        }
        if request.temperature:
            # openai 取值0-2 xunfei  0-1
            kargs["temperature"] = request.temperature / 2
        if request.max_tokens:
            kargs["max_tokens"] = request.max_tokens

        kargs.update(self.config_args)
        iter_content = self.api_connection.get_resp_from_messages(messages, **kargs)

        if request.stream:
            for line in iter_content:
                code = line["header"]["code"]
                if code != 0:
                    logger.error(f"请求失败:{line}")
                    raise Exception(f"请求失败:{line}")
                openai_response = self.client_response_2_chatgpt_response_stream(line)
                yield CompletionResponse(**openai_response)
        else:
            openai_response = self.client_response_to_chatgpt_response_completions(iter_content)
            yield CompletionResponse(**openai_response)

    def openai_to_client_params_chat_completions(self, openai_params: ChatCompletionRequest):
        prompt = []
        for message in openai_params.messages:
            role = message.role
            if role in ["function"]:
                raise Exception(f"不支持的功能:{role}")
            if role == "system":  # 将system转为user
                role = "user"
                content = self.prompt.format(system=message.content)
                prompt.append({"role": role, "content": content})
                prompt.append({"role": "assistant", "content": "ok"})
            else:
                content = message.content
                prompt.append({"role": role, "content": content})
        return prompt
    
    def openai_to_client_params_completions(self, openai_params: ChatCompletionRequest):
        prompt = []
        for p in openai_params.prompt:
            prompt.append({"role": "user", "content": p})
        return prompt

    def client_response_2_chatgpt_response_stream(self, resp_json):
        completion = resp_json["payload"]["choices"]["text"][0]["content"]
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        if resp_json["payload"]["choices"]["status"] == 2:
            usage = resp_json["payload"]["usage"]["text"]
            prompt_tokens = usage["prompt_tokens"]
            completion_tokens = usage["completion_tokens"]
            total_tokens = usage["total_tokens"]

        openai_response = {
            "id": resp_json["header"]["sid"],
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "gpt-3.5-turbo-0613",
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": completion,
                    },
                    "index": 0,
                    "finish_reason": "stop"
                    if resp_json["payload"]["choices"]["status"] == 2
                    else None,
                }
            ],
        }
        return openai_response

    def client_response_to_chatgpt_response_chat_completions(self, iter_resp):
        completions = []
        id = None
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        for resp_json in iter_resp:
            code = resp_json["header"]["code"]
            if code != 0:
                logger.error(f"请求失败:{resp_json}")
                raise Exception(f"请求失败:{resp_json}")
            content = resp_json["payload"]["choices"]["text"][0]["content"]
            completions.append(content)
            id = resp_json["header"]["sid"]
            logger.info(f"resp_json: {resp_json}")
            if resp_json["payload"]["choices"]["status"] == 2:
                usage = resp_json["payload"]["usage"]["text"]
                prompt_tokens = usage["prompt_tokens"]
                completion_tokens = usage["completion_tokens"]
                total_tokens = usage["total_tokens"]
        openai_response = {
            "id": id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "xunfei-spark3.0",
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "".join(completions),
                    },
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
        }
        return openai_response
    
    def client_response_to_chatgpt_response_completions(self, iter_resp):
        completions = []
        id = None
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        for resp_json in iter_resp:
            code = resp_json["header"]["code"]
            if code != 0:
                logger.error(f"请求失败:{resp_json}")
                raise Exception(f"请求失败:{resp_json}")
            content = resp_json["payload"]["choices"]["text"][0]["content"]
            completions.append(content)
            id = resp_json["header"]["sid"]
            logger.info(f"resp_json: {resp_json}")
            if resp_json["payload"]["choices"]["status"] == 2:
                usage = resp_json["payload"]["usage"]["text"]
                prompt_tokens = usage["prompt_tokens"]
                completion_tokens = usage["completion_tokens"]
                total_tokens = usage["total_tokens"]
        pass
        openai_response = {
            "id": id,
            "object": "text_completion",
            "created": int(time.time()),
            "model": "xunfei-spark3.0",
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "choices": [
                {
                    "text": "".join(completions),
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
        }
        return openai_response
