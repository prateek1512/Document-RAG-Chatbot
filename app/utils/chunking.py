# app/utils/chunking.py
# Splits a long text into smaller chunks based on token count.
# Uses tiktoken (the same tokenizer behind many LLMs) to count tokens accurately.

import tiktoken


def chunk_text(text: str, max_tokens: int = 500, overlap_tokens: int = 50) -> list[str]:
    # 1. Pick a tokenizer (here cl100k_base is used)
    encoder = tiktoken.get_encoding("cl100k_base")

    # 2. Convert the entire text into a list of token IDs.
    all_tokens = encoder.encode(text)

    chunks = []
    start = 0

    while start < len(all_tokens):
        # 3. Grab the next `max_tokens` tokens starting from `start`.
        end = start + max_tokens
        chunk_tokens = all_tokens[start:end]

        # 4. Decode these token IDs back into a readable string.
        chunk_str = encoder.decode(chunk_tokens)
        chunks.append(chunk_str)

        # 5. Move the window forward by (max_tokens - overlap_tokens).
        start += max_tokens - overlap_tokens

    return chunks
