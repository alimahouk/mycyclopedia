import json
import openai
import re
import tiktoken
import time
from typing import Any

from app import openai_client
from app.config import (
    ChatMessageSenderRole,
    Configuration,
    OpenAIModel,
    openai_model_context_len,
    openai_model_token_limits
)
from app.modules.chat_message import ChatMessage


def get_entry_chat_completion(context: str,
                              proficiency: str,
                              section_md: str,
                              topic: str,
                              messages: list[ChatMessage],
                              attempts: int = 0) -> str | None:
    """
    This function interacts with the OpenAI API to generate responses.

    Parameters:
    messages (list): A list of message dictionaries. Each interaction (from user or assistant)
                    should be appended to this list as a new dictionary. Each dictionary should 
                    have 'role' (can be 'system', 'user', or 'assistant') and 'content' (the text of 
                    the message from the role). Example:
                    [
                        {"role": "user", "content": "hi"},
                        {"role": "assistant", "content": "Hello! How can I help you today?"}
                    ]

    Returns:
    response_str (str): This is the content of the assistant's message from the response object 
                        returned by the OpenAI API.
    """

    model = OpenAIModel.GPT_35_16K
    model_context_len = openai_model_context_len.get(model)
    model_token_limit = openai_model_token_limits.get(model)
    prompt = (
        f"Entry Topic: \"{topic}\"\n"
        f"Reader Proficiency: {proficiency}\n"
        f"Entry text for context: ```{section_md}```"
    )
    try:
        if len(messages) == 1:
            # First message, inject the context into the user's message.
            user_message = messages[0]
            user_message.content_md = f"\"{context}\"\n" + user_message.content_md

        # Since we have a token limit, we insert chat messages
        # until we're on the verge of exceeding the limit.
        messages_reversed = messages[::-1]
        messages_final = [
            {"role": ChatMessageSenderRole.SYSTEM.value, "content": "You are the Assistant, an AI chatbot designed to assist with the entries of Mycyclopedia, which is an AI-powered encyclopedia. Be comprehensive in your responses and format them as Markdown. Use headings, tables and lists when applicable"},
            {"role": ChatMessageSenderRole.ASSISTANT.value, "content": prompt}
        ]
        for m in messages_reversed:
            token_count = num_tokens_from_messages(messages_final, model=model)
            if token_count < model_context_len:
                messages_final.insert(3, m.prompt_format())

        messages_final.append({"role": ChatMessageSenderRole.ASSISTANT.value, "content": "You: "})

        token_count = num_tokens_from_messages(messages_final)
        response = openai_client.chat.completions.create(
            model=OpenAIModel.GPT_35_16K,
            max_tokens=model_token_limit - token_count,
            messages=messages_final,
            temperature=1,
            timeout=60
        )
        response_str = response.choices[0].message.content
    except openai.APITimeoutError as e:
        print("OpenAI API request timed out!")
        if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
            time.sleep(Configuration.OPENAI_RETRY_DELAY)
            response_str = get_entry_chat_completion(
                attempts=attempts + 1,
                context=context,
                section_md=section_md,
                messages=messages,
                proficiency=proficiency,
                topic=topic
            )
    except Exception as e:
        print(e)
    return response_str


def get_entry_fun_facts(topic: str,
                        attempts: int = 0,
                        temperature: float = 0.8) -> list[str] | None:
    facts: list[str] | None = None
    model = OpenAIModel.GPT_35_16K
    model_token_limit = openai_model_token_limits.get(model)
    prompt = f"Entry Topic: \"{topic}\""
    messages = [
        {"role": "system", "content": "You are a documenter writing entries for an encyclopedia. Respond with 5 fun facts on the given topic as it is very important to my career"},
        {"role": "system", "content": "Format all your responses as JSON only, in a single line without whitespaces. Do not include any commentary or text outside the JSON"},
        {"role": "system", "content": "Replace any double quotes in the text with single quotes"},
        {"role": "system", "content": "Do not include a bullet number (e.g. '1. <fact>', '2. <fact>', etc.) in the fact. This is very important"},
        {"role": "system", "content": "Your response should only be a single JSON array of strings without any keys of the format: [\"fact 1\", \"fact 2\", \"fact 3\"]. Do not return any text outside the the JSON string. If you can't come up with any facts, return an empty JSON object"},
        {"role": "user", "content": prompt}
    ]

    token_count = num_tokens_from_messages(messages, model=model)
    try:
        response_raw = openai_client.chat.completions.create(
            model=OpenAIModel.GPT_35_16K,
            max_tokens=model_token_limit - token_count,
            messages=messages,
            temperature=temperature,
            timeout=90
        )
        finish_reason: str = response_raw.choices[0].finish_reason
        if finish_reason and finish_reason == "stop":
            response: str = response_raw.choices[0].message.content
            if response:
                response = re.sub("\\n|[^\x20-\x7e]", "", response)
                response = re.sub(",\\s*\\}", "", response)
                try:
                    facts = json.loads(response)
                except json.JSONDecodeError:
                    print("OpenAI Error - invalid JSON:", response)
                    if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
                        # LLM ignored instructions and probably returned invalid JSON.
                        # Pause for a bit to avoid OpenAI API throttling and try again.
                        time.sleep(Configuration.OPENAI_RETRY_DELAY)
                        facts = get_entry_fun_facts(topic, attempts=attempts + 1, temperature=max(temperature + 0.1, 1))
                    else:
                        facts = None
            else:
                print("OpenAI Error - invalid response!")
                if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
                    # LLM ignored instructions and probably returned invalid JSON.
                    # Pause for a bit to avoid OpenAI API throttling and try again.
                    time.sleep(Configuration.OPENAI_RETRY_DELAY)
                    facts = get_entry_fun_facts(topic, attempts=attempts + 1, temperature=max(temperature + 0.1, 1))
                else:
                    facts = None
        else:
            print("OpenAI Error - finish_reason:", finish_reason)
    except openai.APITimeoutError as e:
        print("OpenAI API request timed out!")
        if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
            time.sleep(Configuration.OPENAI_RETRY_DELAY)
            facts = get_entry_fun_facts(topic, attempts=attempts + 1, temperature=max(temperature + 0.1, 1))
    except Exception as e:
        print(e)

    return facts


def get_entry_related_topics(topic: str,
                             proficiency: str,
                             attempts: int = 0,
                             temperature: float = 0.8) -> list[str] | None:
    topics: list[str] | None = None
    model = OpenAIModel.GPT_35_16K
    model_token_limit = openai_model_token_limits.get(model)
    prompt = (
        f"Entry Topic: {topic}\n"
        f"Reader Proficiency: {proficiency}"
    )
    messages = [
        {"role": "system", "content": "You are a documenter writing entries for an encyclopedia. Given the following topic, respond with some other topics the reader might be interested in as it is very important to my career"},
        {"role": "system", "content": "Format all your responses as JSON only, in a single line without whitespaces. Do not include any commentary or text outside the JSON"},
        {"role": "system", "content": "Replace any double quotes in the text with single quotes"},
        {"role": "system", "content": "Do not include a bullet number (e.g. '1. <topic>', '2. <topic>', etc.) in the topic. This is very important"},
        {"role": "system", "content": "Your response should only be a single JSON array of strings without any keys of the format: [\"topic 1\", \"topic 2\", \"topic 3\"]. Do not return any text outside the the JSON string. If you can't come up with any topics, return an empty JSON object"},
        {"role": "user", "content": prompt}
    ]

    token_count = num_tokens_from_messages(messages, model=model)
    try:
        response_raw = openai_client.chat.completions.create(
            model=OpenAIModel.GPT_35_16K,
            max_tokens=model_token_limit - token_count,
            messages=messages,
            temperature=temperature,
            timeout=90
        )
        finish_reason: str = response_raw.choices[0].finish_reason
        if finish_reason and finish_reason == "stop":
            response: str = response_raw.choices[0].message.content
            if response:
                response = re.sub("\\n|[^\x20-\x7e]", "", response)
                response = re.sub(",\\s*\\}", "", response)
                try:
                    topics = json.loads(response)
                except json.JSONDecodeError:
                    print("OpenAI Error - invalid JSON:", response)
                    if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
                        # LLM ignored instructions and probably returned invalid JSON.
                        # Pause for a bit to avoid OpenAI API throttling and try again.
                        time.sleep(Configuration.OPENAI_RETRY_DELAY)
                        topics = get_entry_related_topics(
                            attempts=attempts + 1,
                            proficiency=proficiency,
                            temperature=max(temperature + 0.1, 1),
                            topic=topic
                        )
                    else:
                        topics = None
            else:
                print("OpenAI Error - invalid response!")
                if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
                    # LLM ignored instructions and probably returned invalid JSON.
                    # Pause for a bit to avoid OpenAI API throttling and try again.
                    time.sleep(Configuration.OPENAI_RETRY_DELAY)
                    topics = get_entry_related_topics(
                        attempts=attempts + 1,
                        proficiency=proficiency,
                        temperature=max(temperature + 0.1, 1),
                        topic=topic
                    )
                else:
                    topics = None
        else:
            print("OpenAI Error - finish_reason:", finish_reason)
    except openai.APITimeoutError as e:
        print("OpenAI API request timed out!")
        if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
            time.sleep(Configuration.OPENAI_RETRY_DELAY)
            topics = get_entry_related_topics(
                attempts=attempts + 1,
                proficiency=proficiency,
                temperature=max(temperature + 0.1, 1),
                topic=topic
            )
    except Exception as e:
        print(e)

    return topics


def get_entry_section(proficiency: str,
                      topic: str,
                      section_title: str,
                      attempts: int = 0) -> str | None:
    section: str | None = None
    model = OpenAIModel.GPT_35_16K
    model_token_limit = openai_model_token_limits.get(model)
    prompt = (
        f"Entry Topic: {topic}\n"
        f"Reader Proficiency: {proficiency}\n"
        f"Section Title: {section_title.strip()}\n"
    )
    messages = [
        {"role": "system", "content": "You are a documenter writing entries for an encyclopedia. Respond comprehensively as it is very important to my career"},
        {"role": "system", "content": "Format your response as Markdown. Use Markdown headings, tables and lists when applicable. Do not re-include the section title supplied by the user in your response. Do not include any table of contents in your response"},
        {"role": "system", "content": "Give helpful examples when applicable"},
        {"role": "user", "content": prompt}
    ]

    token_count = num_tokens_from_messages(messages, model=model)
    try:
        response_raw = openai_client.chat.completions.create(
            model=OpenAIModel.GPT_35_16K,
            max_tokens=model_token_limit - token_count,
            messages=messages,
            temperature=0.8,
            timeout=90
        )
        finish_reason: str = response_raw.choices[0].finish_reason
        if finish_reason and finish_reason == "stop":
            section = response_raw.choices[0].message.content
            if not section:
                print("OpenAI Error - invalid response!")
                if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
                    # LLM ignored instructions and probably returned invalid JSON.
                    # Pause for a bit to avoid OpenAI API throttling and try again.
                    time.sleep(Configuration.OPENAI_RETRY_DELAY)
                    section = get_entry_section(
                        attempts=attempts + 1,
                        proficiency=proficiency,
                        section_title=section_title,
                        topic=topic
                    )
                else:
                    section = None
        else:
            print("OpenAI Error - finish_reason:", finish_reason)
    except openai.APITimeoutError as e:
        print("OpenAI API request timed out!")
        if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
            time.sleep(Configuration.OPENAI_RETRY_DELAY)
            section = get_entry_section(
                attempts=attempts + 1,
                proficiency=proficiency,
                section_title=section_title,
                topic=topic
            )
    except Exception as e:
        print(e)

    return section


def get_entry_stats(topic: str,
                    attempts: int = 0,
                    temperature: float = 0.8) -> list[dict[str, str]] | None:
    stats: list[dict[str, str]] | None = None
    model = OpenAIModel.GPT_35_16K
    model_token_limit = openai_model_token_limits.get(model)
    prompt = f"Entry Topic: \"{topic}\""
    messages = [
        {"role": "system", "content": "You are a documenter writing entries for an encyclopedia. Respond with some interesting stats on the given topic and use Markdown for content formatting as it is very important to my career"},
        {"role": "system", "content": "Format all your responses as JSON only, in a single line without whitespaces. Do not include any commentary or text outside the JSON"},
        {"role": "system", "content": "Replace any double quotes in the text with single quotes"},
        {"role": "system", "content": "Your response should only be a single JSON string of the format: [{\"stat 1 label\": \"stat 1 value\"}, {\"stat 2 label\": \"stat 2 value\"}, {\"stat 3 label\": \"stat 3 value\"}, ...]. Do not return any text outside the the JSON string. If you can't come up with any stats, return an empty JSON object"},
        {"role": "user", "content": prompt}
    ]

    token_count = num_tokens_from_messages(messages, model=model)
    try:
        response_raw = openai_client.chat.completions.create(
            model=OpenAIModel.GPT_35_16K,
            max_tokens=model_token_limit - token_count,
            messages=messages,
            temperature=temperature,
            timeout=90
        )
        finish_reason: str = response_raw.choices[0].finish_reason
        if finish_reason and finish_reason == "stop":
            response: str = response_raw.choices[0].message.content
            if response:
                response = re.sub("\\n|[^\x20-\x7e]", "", response)
                response = re.sub(",\\s*\\}", "", response)
                try:
                    stats = json.loads(response)
                except json.JSONDecodeError:
                    print("OpenAI Error - invalid JSON:", response)
                    if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
                        # LLM ignored instructions and probably returned invalid JSON.
                        # Pause for a bit to avoid OpenAI API throttling and try again.
                        time.sleep(Configuration.OPENAI_RETRY_DELAY)
                        stats = get_entry_stats(topic, attempts=attempts + 1, temperature=max(temperature + 0.1, 1))
                    else:
                        stats = None
            else:
                print("OpenAI Error - invalid response!")
                if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
                    # LLM ignored instructions and probably returned invalid JSON.
                    # Pause for a bit to avoid OpenAI API throttling and try again.
                    time.sleep(Configuration.OPENAI_RETRY_DELAY)
                    stats = get_entry_stats(topic, attempts=attempts + 1, temperature=max(temperature + 0.1, 1))
                else:
                    topic = None
        else:
            print("OpenAI Error - finish_reason:", finish_reason)
    except openai.APITimeoutError as e:
        print("OpenAI API request timed out!")
        if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
            time.sleep(Configuration.OPENAI_RETRY_DELAY)
            stats = get_entry_stats(topic, attempts=attempts + 1, temperature=max(temperature + 0.1, 1))
    except Exception as e:
        print(e)

    return stats


def get_entry_summary(topic: str,
                      attempts: int = 0) -> str | None:
    summary: str | None = None
    model = OpenAIModel.GPT_35_16K
    model_token_limit = openai_model_token_limits.get(model)
    prompt = (
        f"Entry Topic: {topic}\n"
        f"Summary: "
    )
    messages = [
        {"role": "system", "content": "You are a documenter writing entries for an encyclopedia. Respond with a brief summary of the given topic. Keep it below 150 words as that is very important to my career"},
        {"role": "system", "content": "Do not include any headings or titles"},
        {"role": "user", "content": prompt}
    ]

    token_count = num_tokens_from_messages(messages, model=model)
    try:
        response_raw = openai_client.chat.completions.create(
            model=OpenAIModel.GPT_35_16K,
            max_tokens=model_token_limit - token_count,
            messages=messages,
            temperature=0.8,
            timeout=90
        )
        finish_reason: str = response_raw.choices[0].finish_reason
        if finish_reason and finish_reason == "stop":
            summary = response_raw.choices[0].message.content
            if not summary:
                print("OpenAI Error - invalid response!")
                if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
                    # LLM ignored instructions and probably returned invalid JSON.
                    # Pause for a bit to avoid OpenAI API throttling and try again.
                    time.sleep(Configuration.OPENAI_RETRY_DELAY)
                    summary = get_entry_summary(
                        attempts=attempts + 1,
                        topic=topic
                    )
                else:
                    summary = None
        else:
            print("OpenAI Error - finish_reason:", finish_reason)
    except openai.APITimeoutError as e:
        print("OpenAI API request timed out!")
        if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
            time.sleep(Configuration.OPENAI_RETRY_DELAY)
            summary = get_entry_summary(
                attempts=attempts + 1,
                topic=topic
            )
    except Exception as e:
        print(e)

    return summary


def get_entry_table_of_contents(proficiency: str,
                                topic: str,
                                attempts: int = 0,
                                temperature: float = 0.8) -> list[dict[str, Any]] | None:
    toc: list[dict[str, Any]] | None = None
    model = OpenAIModel.GPT_35_16K
    model_token_limit = openai_model_token_limits.get(model)
    prompt = (
        f"Entry Topic: {topic}\n"
        f"Reader Proficiency: {proficiency}\n"
    )
    messages = [
        {"role": "system", "content": "You are a documenter writing entries for an encyclopedia. Generate a comprehensive table of contents on the given topic. Include subsections when applicable as it is very important to my career"},
        {"role": "system", "content": "Format all your responses as JSON only, in a single line without whitespaces. Do not include any commentary or text outside the JSON"},
        {"role": "system", "content": "Replace any double quotes in the text with single quotes"},
        {"role": "system", "content": "Your response should only be a single JSON string of the format: [{\"title\": \"section 1 title\", \"subsections\": [{\"title\": \"subsection 1 title\"}, ...]}, {\"title\": \"section 2 title\"}, ...]. Do not return any text outside the the JSON string. If you can't come up with a table of contents, return an empty JSON object"},
        {"role": "user", "content": prompt}
    ]

    token_count = num_tokens_from_messages(messages, model=model)
    try:
        response_raw = openai_client.chat.completions.create(
            model=OpenAIModel.GPT_35_16K,
            max_tokens=model_token_limit - token_count,
            messages=messages,
            temperature=temperature,
            timeout=90
        )
        finish_reason: str = response_raw.choices[0].finish_reason
        if finish_reason and finish_reason == "stop":
            response: str = response_raw.choices[0].message.content
            if response:
                response = re.sub("\\n|[^\x20-\x7e]", "", response)
                response = re.sub(",\\s*\\}", "", response)
                try:
                    toc = json.loads(response)
                except json.JSONDecodeError:
                    print("OpenAI Error - invalid JSON:", response)
                    if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
                        # LLM ignored instructions and probably returned invalid JSON.
                        # Pause for a bit to avoid OpenAI API throttling and try again.
                        time.sleep(Configuration.OPENAI_RETRY_DELAY)
                        toc = get_entry_table_of_contents(
                            attempts=attempts + 1,
                            proficiency=proficiency,
                            temperature=max(temperature + 0.1, 1),
                            topic=topic
                        )
                    else:
                        toc = None
            else:
                print("OpenAI Error - invalid response!")
                if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
                    # LLM ignored instructions and probably returned invalid JSON.
                    # Pause for a bit to avoid OpenAI API throttling and try again.
                    time.sleep(Configuration.OPENAI_RETRY_DELAY)
                    toc = get_entry_table_of_contents(
                        attempts=attempts + 1,
                        proficiency=proficiency,
                        temperature=max(temperature + 0.1, 1),
                        topic=topic
                    )
                else:
                    topic = None
        else:
            print("OpenAI Error - finish_reason:", finish_reason)
    except openai.APITimeoutError as e:
        print("OpenAI API request timed out!")
        if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
            time.sleep(Configuration.OPENAI_RETRY_DELAY)
            toc = get_entry_table_of_contents(
                attempts=attempts + 1,
                proficiency=proficiency,
                temperature=max(temperature + 0.1, 1),
                topic=topic
            )
    except Exception as e:
        print(e)

    return toc


def get_entry_topic(user_input: str,
                    attempts: int = 0) -> str | None:
    topic: str | None = None
    invalid_topic_responses = {
        ".", ".'", "'.", "'.'"
    }
    model = OpenAIModel.GPT_35_16K
    model_token_limit = openai_model_token_limits.get(model)
    prompt = (
        f"Snippet: \"{user_input.strip()}\"\n"
        "Title: "
    )
    messages = [
        {"role": "system", "content": "You are a documenter writing entries for an encyclopedia. Respond with a suitable entry title for the given snippet but only if the snippet is valid as it is very important to my career"},
        {"role": "system", "content": "Use proper punctuation and grammar. Do not include any other commentary"},
        {"role": "system", "content": f"If you can't come up with a title, say '.'"},
        {"role": "user", "content": prompt}
    ]

    token_count = num_tokens_from_messages(messages, model=model)
    try:
        response_raw = openai_client.chat.completions.create(
            model=OpenAIModel.GPT_35_16K,
            max_tokens=model_token_limit - token_count,
            messages=messages,
            temperature=0,
            timeout=90
        )
        finish_reason: str = response_raw.choices[0].finish_reason
        if finish_reason and finish_reason == "stop":
            topic = response_raw.choices[0].message.content
            if not topic or topic in invalid_topic_responses:
                topic = ""
        else:
            print("OpenAI Error - finish_reason:", finish_reason)
    except openai.APITimeoutError as e:
        print("OpenAI API request timed out!")
        if attempts < Configuration.OPENAI_RETRY_MAX_ATTEMPTS:
            time.sleep(Configuration.OPENAI_RETRY_DELAY)
            topic = get_entry_topic(user_input, attempts=attempts + 1)
    except Exception as e:
        print(e)

    return topic


def num_tokens_from_messages(messages,
                             model=OpenAIModel.GPT_35_16K) -> int:
    """Return the number of tokens used by a list of messages."""

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens_per_message = 3
    tokens_per_name = 1
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    # every reply is primed with <|start|>assistant<|message|>.
    num_tokens += 3
    return num_tokens
