import dataclasses
import logging
import pickle
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from random import shuffle
from typing import Any, List, Optional, TypedDict

import numpy as np
import openai
import tenacity
import tiktoken
from IPython import get_ipython
from IPython.display import Markdown, display
from openai.error import (APIConnectionError, APIError, RateLimitError,
                          ServiceUnavailableError, Timeout)
from scipy import spatial

logger = logging.getLogger(__name__)


class Message(TypedDict):
    """OpenAI Message object containing a role and the message content"""

    role: str
    content: str


DEFAULT_SYSTEM_PROMPT = 'You are a helpful assistant. Respond using markdown.'
DEFAULT_GPT_MODEL = "gpt-3.5-turbo"
EMBEDDING_MODEL = "text-embedding-ada-002"
EMBED_DIM = 1536


def token_limits(model: str = DEFAULT_GPT_MODEL) -> int:
    """Return the maximum number of tokens for a model."""
    return {
        "gpt-3.5-turbo": 4096,
        "gpt-4": 8192,
        "gpt-4-32k": 32768,
        "text-embedding-ada-002": 8191,
    }[model]


def count_message_tokens(messages: List[Message],
                         model: str = "gpt-3.5-turbo-0301") -> int:
    """
    Returns the number of tokens used by a list of messages.

    Args:
        messages (list): A list of messages, each of which is a dictionary
            containing the role and content of the message.
        model (str): The name of the model to use for tokenization.
            Defaults to "gpt-3.5-turbo-0301".

    Returns:
        int: The number of tokens used by the list of messages.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logger.warn("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo":
        # !Note: gpt-3.5-turbo may change over time.
        # Returning num tokens assuming gpt-3.5-turbo-0301.")
        return count_message_tokens(messages, model="gpt-3.5-turbo-0301")
    elif model == "gpt-4":
        # !Note: gpt-4 may change over time. Returning num tokens assuming gpt-4-0314.")
        return count_message_tokens(messages, model="gpt-4-0314")
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = (
            4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        )
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model == "gpt-4-0314":
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        raise NotImplementedError(
            f"num_tokens_from_messages() is not implemented for model {model}.\n"
            " See https://github.com/openai/openai-python/blob/main/chatml.md for"
            " information on how messages are converted to tokens.")
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def count_string_tokens(string: str, model_name: str) -> int:
    """
    Returns the number of tokens in a text string.

    Args:
        string (str): The text string.
        model_name (str): The name of the encoding to use. (e.g., "gpt-3.5-turbo")

    Returns:
        int: The number of tokens in the text string.
    """
    encoding = tiktoken.encoding_for_model(model_name)
    return len(encoding.encode(string))


def create_chat_message(role, content) -> Message:
    """
    Create a chat message with the given role and content.

    Args:
    role (str): The role of the message sender, e.g., "system", "user", or "assistant".
    content (str): The content of the message.

    Returns:
    dict: A dictionary containing the role and content of the message.
    """
    return {"role": role, "content": content}


def generate_context(prompt,
                     relevant_memory,
                     full_message_history,
                     model,
                     summary=None):
    current_context = [
        create_chat_message("system", prompt),
        create_chat_message(
            "system", f"The current time and date is {time.strftime('%c')}"),
        create_chat_message(
            "system",
            f"This reminds you of these events from your past:\n{relevant_memory}\n\n",
        ),
    ]
    if summary is not None:
        current_context.append(
            create_chat_message(
                "system",
                f"This is a summary of the conversation so far:\n{summary}\n\n"
            ))

    # Add messages from the full message history until we reach the token limit
    next_message_to_add_index = len(full_message_history) - 1
    insertion_index = len(current_context)
    # Count the currently used tokens
    current_tokens_used = count_message_tokens(current_context, model)
    return (
        next_message_to_add_index,
        current_tokens_used,
        insertion_index,
        current_context,
    )


@tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
                stop=tenacity.stop_after_attempt(5),
                retry=tenacity.retry_if_exception_type(
                    (RateLimitError, APIError, Timeout,
                     ServiceUnavailableError, APIConnectionError)))
def create_chat_completion(
    messages: List[Message],  # type: ignore
    model: Optional[str] = None,
    temperature: float = 0.9,
    max_tokens: Optional[int] = None,
) -> str:
    """Create a chat completion using the OpenAI API

    Args:
        messages (List[Message]): The messages to send to the chat completion
        model (str, optional): The model to use. Defaults to None.
        temperature (float, optional): The temperature to use. Defaults to 0.9.
        max_tokens (int, optional): The max tokens to use. Defaults to None.

    Returns:
        str: The response from the chat completion
    """
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    try:
        resp = response.choices[0].message["content"]
    except:
        try:
            return response.error.message
        except:
            logger.error(f"Error in create_chat_completion: {response}")
        raise
    return resp


@tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
                stop=tenacity.stop_after_attempt(5),
                retry=tenacity.retry_if_exception_type(
                    (RateLimitError, APIError, Timeout,
                     ServiceUnavailableError, APIConnectionError)))
def get_embedding(
    text: str,
    *_,
    model: str = EMBEDDING_MODEL,
    **kwargs,
) -> List[float]:
    """Create an embedding using the OpenAI API

    Args:
        text (str): The text to embed.
        kwargs: Other arguments to pass to the OpenAI API embedding creation call.

    Returns:
        List[float]: The embedding.
    """
    return openai.Embedding.create(
        model=model,
        input=[text],
        **kwargs,
    )["data"][0]["embedding"]


def chat_with_ai(prompt,
                 user_input,
                 full_message_history,
                 permanent_memory,
                 summary=None,
                 model=DEFAULT_GPT_MODEL,
                 token_limit=None):
    """Interact with the OpenAI API, sending the prompt, user input, message history,
    and permanent memory.

    Args:
        prompt (str): The prompt explaining the rules to the AI.
        user_input (str): The input from the user.
        full_message_history (list): The list of all messages sent between the
            user and the AI.
        permanent_memory (Obj): The memory object containing the permanent
            memory.
        summary (str): The summary of the conversation so far.
        model (str): The name of the model to use for tokenization.
        token_limit (int): The maximum number of tokens allowed in the API call.

    Returns:
        str: The AI's response.
    """

    # Reserve 1000 tokens for the response

    if token_limit is None:
        token_limit = token_limits(model)

    logger.debug(f"Token limit: {token_limit}")
    send_token_limit = token_limit - 1000
    if len(full_message_history) == 0:
        relevant_memory = ""
    else:
        recent_history = full_message_history[-5:]
        shuffle(recent_history)
        relevant_memories = permanent_memory.get_relevant(
            str(recent_history), 5)
        if relevant_memories:
            shuffle(relevant_memories)
        relevant_memory = str(relevant_memories)

    logger.debug(f"Memory Stats: {permanent_memory.get_stats()}")

    (
        next_message_to_add_index,
        current_tokens_used,
        insertion_index,
        current_context,
    ) = generate_context(prompt, relevant_memory, full_message_history, model,
                         summary)

    while current_tokens_used > 2500:
        # remove memories until we are under 2500 tokens
        relevant_memory = relevant_memory[:-1]
        (
            next_message_to_add_index,
            current_tokens_used,
            insertion_index,
            current_context,
        ) = generate_context(prompt, relevant_memory, full_message_history,
                             model, summary)

    current_tokens_used += count_message_tokens(
        [create_chat_message("user", user_input)],
        model)  # Account for user input (appended later)

    while next_message_to_add_index >= 0:
        # print (f"CURRENT TOKENS USED: {current_tokens_used}")
        message_to_add = full_message_history[next_message_to_add_index]

        tokens_to_add = count_message_tokens([message_to_add], model)
        if current_tokens_used + tokens_to_add > send_token_limit:
            break

        # Add the most recent message to the start of the current context,
        #  after the two system prompts.
        current_context.insert(insertion_index,
                               full_message_history[next_message_to_add_index])

        # Count the currently used tokens
        current_tokens_used += tokens_to_add

        # Move to the next most recent message in the full message history
        next_message_to_add_index -= 1

    # Append user input, the length of this is accounted for above
    current_context.extend([create_chat_message("user", user_input)])

    # Calculate remaining tokens
    tokens_remaining = token_limit - current_tokens_used
    # assert tokens_remaining >= 0, "Tokens remaining is negative.

    # TODO: use a model defined elsewhere, so that model can contain
    # temperature and other settings we care about
    assistant_reply = create_chat_completion(
        model=model,
        messages=current_context,
        max_tokens=tokens_remaining,
    )

    # Update full message history
    full_message_history.append(create_chat_message("user", user_input))
    full_message_history.append(
        create_chat_message("assistant", assistant_reply))

    return assistant_reply


def create_default_embeddings():
    return np.zeros((0, EMBED_DIM)).astype(np.float32)


@dataclasses.dataclass
class CacheContent:
    texts: List[str] = dataclasses.field(default_factory=list)
    embeddings: np.ndarray = dataclasses.field(
        default_factory=create_default_embeddings)


class LocalCache():
    """A class that stores the memory in a local file"""

    def __init__(self, path=None) -> None:
        """Initialize a class instance

        Args:
            path: str

        Returns:
            None
        """
        if path is None:
            self.filename = None
        else:
            self.filename = Path(path)
            self.filename.touch(exist_ok=True)
        try:
            with open(self.filename, 'rb') as f:
                self.data = pickle.load(f)
        except:
            self.data = CacheContent()

    def add(self, text: str):
        """
        Add text to our list of texts, add embedding as row to our
            embeddings-matrix

        Args:
            text: str

        Returns: None
        """
        if "Command Error:" in text:
            return ""
        self.data.texts.append(text)

        embedding = get_embedding(text)

        vector = np.array(embedding).astype(np.float32)
        vector = vector[np.newaxis, :]
        self.data.embeddings = np.concatenate(
            [
                self.data.embeddings,
                vector,
            ],
            axis=0,
        )

        if self.filename is not None:
            with open(self.filename, "wb") as f:
                pickle.dump(self.data, f)
        return text

    def clear(self) -> str:
        """
        Clears the data in memory.

        Returns: A message indicating that the memory has been cleared.
        """
        self.data = CacheContent()
        return "Obliviated"

    def get(self, data: str) -> list[Any] | None:
        """
        Gets the data from the memory that is most relevant to the given data.

        Args:
            data: The data to compare to.

        Returns: The most relevant data.
        """
        return self.get_relevant(data, 1)

    def get_relevant(self, text: str, k: int) -> list[Any]:
        """ "
        matrix-vector mult to find score-for-each-row-of-matrix
         get indices for top-k winning scores
         return texts for those indices
        Args:
            text: str
            k: int

        Returns: List[str]
        """
        if self.data.embeddings.shape[0] == 0:
            return []
        embedding = get_embedding(text)

        scores = np.dot(self.data.embeddings, embedding)

        top_k_indices = np.argsort(scores)[-k:][::-1]

        return [self.data.texts[i] for i in top_k_indices]

    def get_stats(self) -> tuple[int, tuple[int, ...]]:
        """
        Returns: The stats of the local cache.
        """
        return len(self.data.texts), self.data.embeddings.shape


class Completion():

    def __init__(self,
                 system_prompt=DEFAULT_SYSTEM_PROMPT,
                 model=DEFAULT_GPT_MODEL):
        self.messages = [{"role": "system", "content": system_prompt}]
        self.title = 'untitled'
        self.last_time = datetime.now()
        self.completion = None
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.model = model

    def make_title(self):

        text = [
            f'{d["role"]} :\n"""\n{d["content"]}\n"""'
            for d in self.messages[1:]
        ]

        messages = [{
            "role": "system",
            "content": 'You are a helpful assistant.'
        }, {
            'role':
            "user",
            'content': ("总结以下对话的内容并为其取个标题以概括对话的内容，标题长度不超过100个字符。"
                        "不得包含`?:*,<>\\/` 等不能用于文件路径的字符。"
                        "返回的结果除了标题本身，不要包含额外的内容，省略结尾的句号。\n" + '\n\n'.join(text))
        }]
        completion = openai.ChatCompletion.create(model=self.model,
                                                  messages=messages)
        content = completion.choices[0].message['content']
        return f"{time.strftime('%Y%m%d%H%M')} {content}"

    def say(self, msg):
        self.last_time = datetime.now()
        self.messages.append({"role": "user", "content": msg})
        self.completion = openai.ChatCompletion.create(model=self.model,
                                                       messages=self.messages)
        self.total_tokens += self.completion.usage.total_tokens
        self.completion_tokens += self.completion.usage.completion_tokens
        self.prompt_tokens += self.completion.usage.prompt_tokens
        message = self.completion.choices[0].message
        self.messages.append({
            "role": message['role'],
            "content": message['content']
        })
        return message['content']

    def save(self):
        if self.title == 'untitled':
            self.title = self.make_title()

        filepath = Path.home() / 'chatGPT' / f"{self.title}.completion"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)


class Conversation():

    def __init__(self,
                 system_prompt=DEFAULT_SYSTEM_PROMPT,
                 model=DEFAULT_GPT_MODEL):
        self.system_prompt = system_prompt
        self.summary = None
        self.history = []
        self.memory = LocalCache()
        self.title = None
        self.last_time = datetime.now()
        self.model = model
        self._pool = ThreadPoolExecutor()
        self._save_future = None

    def __del__(self):
        if self._save_future is not None:
            self._save_future.result()
        self._pool.shutdown()

    def _validate_title(self, title: str) -> str:
        title.replace('\\/:.*?%&#\"\'<>{}|\n\r\t_', ' ')
        title = title.strip()
        title = '_'.join(title.split())
        if len(title) > 70:
            title = title[:70]
        while title[-1] in ' .。,，-_':
            title = title[:-1]
        return title

    def make_title(self):
        messages = [{
            "role": "system",
            "content": 'You are a helpful assistant.'
        }]

        tokens = count_string_tokens(messages[0]['content'], self.model)

        query = ("请根据以下对话内容，总结出中文标题，长度不超过100个字符。"
                 "请注意，标题必须是合法的文件名，省略结尾的句号。返回结果不得包含额外的解释和格式。\n"
                 "对话内容：\n")

        text = []
        for msg in self.history:
            text.append(f'{msg["role"]} :\n<quote>{msg["content"]}</quote>')
            tokens += count_string_tokens(query + '\n'.join(text), self.model)
            if tokens > token_limits(self.model) - 500:
                text.pop()
                break
        messages.append({"role": "user", "content": query + '\n'.join(text)})

        try:
            self.last_time = datetime.now()
            content = create_chat_completion(messages, self.model)
            title = self._validate_title(content)
            return f"{time.strftime('%Y%m%d%H%M%S')} {title}"
        except:
            return f"{time.strftime('%Y%m%d%H%M%S')} untitled"

    def ask(self, query):
        self.last_time = datetime.now()

        reply = chat_with_ai(self.system_prompt, query, self.history,
                             self.memory, self.summary, self.model,
                             token_limits(self.model))
        return reply

    def _save(self):
        if len(self.history) == 0:
            return

        if self.title is None:
            self.title = self.make_title()

        filepath = Path.home() / 'chatGPT' / f"{self.title}.conversation"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)

    def save(self):
        self._save_future = self._pool.submit(self._save)
        return self._save_future

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['_pool']
        del state['_save_future']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._pool = ThreadPoolExecutor(max_workers=1)
        self._save_future = None


ipy = get_ipython()

current_completion = Conversation()


def chat(line, cell):
    global current_completion
    if line:
        args = line.split()
        current_completion.save()
        model = DEFAULT_GPT_MODEL
        if args[0] in ['gpt-4', 'gpt-3.5', 'gpt-3.5-turbo']:
            model = args[0]
            if model == 'gpt-3.5':
                model = 'gpt-3.5-turbo'
            if len(args) > 1:
                prompt = ' '.join(args[1:])
            else:
                prompt = DEFAULT_SYSTEM_PROMPT
        current_completion = Conversation(system_prompt=prompt, model=model)
        if args[0] in ['end', 'save', 'bye']:
            return
    content = current_completion.ask(cell)
    display(Markdown(content))
    ipy.set_next_input('%%chat\n')


def autosave_completion():
    global current_completion
    if (datetime.now() - current_completion.last_time).seconds > 300 and len(
            current_completion.history) >= 3:
        current_completion.save()
    elif len(current_completion.history) > 7:
        current_completion.save()


def load_chat(index):
    global current_completion

    filepath = Path.home() / 'chatGPT'
    if not filepath.exists():
        return
    for i, f in enumerate(
            sorted(filepath.glob('*.conversation'),
                   key=lambda f: f.stat().st_mtime,
                   reverse=True)):
        if i == index:
            if current_completion is not None:
                current_completion.save().result()
            with open(f, 'rb') as f:
                current_completion = pickle.load(f)
            break


def show_chat(index=None):
    if index is not None:
        load_chat(index)
    messages = current_completion.history
    for msg in messages:
        display(Markdown(f"**{msg['role']}**\n\n{msg['content']}"))
    ipy.set_next_input('%%chat\n')


def list_chat():
    filepath = Path.home() / 'chatGPT'
    if not filepath.exists():
        return
    rows = ["|index|title|length|time|", "|:---:|:---:|:---:|:---:|"]
    for i, f in enumerate(
            sorted(filepath.glob('*.conversation'),
                   key=lambda f: f.stat().st_mtime,
                   reverse=True)):
        with open(f, 'rb') as f:
            completion = pickle.load(f)
        rows.append(
            f"|{i}|{completion.title}|{len(completion.history)}|{completion.last_time}|"
        )
    display(Markdown('\n'.join(rows)))


if ipy is not None:
    ipy.register_magic_function(chat, 'cell', magic_name='chat')
    ipy.events.register('post_run_cell', autosave_completion)
