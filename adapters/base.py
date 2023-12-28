

from typing import Union, Iterator
from adapters.protocol import ChatCompletionRequest, ChatCompletionResponse, CompletionRequest, CompletionResponse


class ModelAdapter:

    def __init__(self, **kwargs):
        pass

    def chat_completions(self, request: ChatCompletionRequest) -> Iterator[ChatCompletionResponse]:
        """
       返回一个迭代器对象
        stream为false   第一个就是结果
        """
        pass

    def completions(self, request: CompletionRequest) -> Iterator[CompletionResponse]:
        """
       返回一个迭代器对象
        stream为false   第一个就是结果
        """
        pass
