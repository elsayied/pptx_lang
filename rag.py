import os
import time
from io import StringIO

import chromadb
import pandas as pd
from chromadb.utils import embedding_functions
from google import genai

# --- ChromaDB Client ---
# Use a persistent client to store data on disk
CHROMA_DATA_PATH = "chroma_data"
db_client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)

# --- Sentence Transformer Model ---
# Using a lightweight model suitable for local execution
SENTENCE_TRANSFORMER_MODEL = "all-MiniLM-L6-v2"
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=SENTENCE_TRANSFORMER_MODEL
)


def create_chroma_collection_from_file(file_path: str, collection_name: str):
    """
    Creates a ChromaDB collection from a text file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Simple chunking by paragraphs
        chunks = [p.strip() for p in content.split("\n\n") if p.strip()]

        collection = db_client.get_or_create_collection(
            name=collection_name, embedding_function=embedding_function
        )

        # Use file path as a unique ID for each chunk
        ids = [f"{file_path}-{i}" for i in range(len(chunks))]

        collection.add(documents=chunks, ids=ids)

        return collection_name
    except Exception as e:
        return f"An error occurred during collection creation: {e}"


def answer_question_with_rag(
    question: str, api_key: str, collection_name: str, history: list = None
) -> str:
    """
    Answers a question using a local RAG model with ChromaDB, maintaining conversation history.
    """
    try:
        genai_client = genai.Client(api_key=api_key)

        collection = db_client.get_collection(
            name=collection_name, embedding_function=embedding_function
        )

        # Query the collection to find relevant documents
        results = collection.query(query_texts=[question], n_results=5)
        retrieved_documents = "\n".join(results["documents"][0])

        # Prepare the prompt for Gemini
        prompt = f"""Based on the following retrieved documents, please answer the user's question.

        Retrieved Documents:
        ---
        {retrieved_documents}
        ---

        Conversation History:
        {history if history else "No history."}

        Question: {question}
        """

        contents = []
        if history:
            contents.extend(history)
        contents.append(prompt)

        response = genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )
        return response.text
    except Exception as e:
        return f"An error occurred: {e}"


def convert_qa_to_anki(qa_pairs: list[dict]) -> str:
    """
    Converts a list of question-answer dictionaries to an Anki-importable string.
    """
    df = pd.DataFrame(qa_pairs)
    # Anki uses semicolon-separated files by default
    return df.to_csv(sep=";", index=False, header=False)
