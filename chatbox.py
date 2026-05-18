from langchain_community.document_loaders import TextLoader

from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS

from langchain_ollama import ChatOllama
import os
import pandas as pd

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader
)

documents = []

folder = "data"

for file in os.listdir(folder):

    path = os.path.join(folder, file)

    # TXT
    if file.endswith(".txt"):

        loader = TextLoader(
            path,
            encoding="utf-8"
        )

        documents.extend(loader.load())

    # PDF
    elif file.endswith(".pdf"):

        loader = PyPDFLoader(path)

        documents.extend(loader.load())

    # DOCX
    elif file.endswith(".docx"):

        loader = Docx2txtLoader(path)

        documents.extend(loader.load())

    # EXCEL
    elif file.endswith(".xlsx"):

        df = pd.read_excel(path)

        for _, row in df.iterrows():

            text = " | ".join(
                [f"{col}: {row[col]}" for col in df.columns]
            )

            documents.append(
                Document(page_content=text)
            )

    # CSV
    elif file.endswith(".csv"):

        df = pd.read_csv(path)

        for _, row in df.iterrows():

            text = " | ".join(
                [f"{col}: {row[col]}" for col in df.columns]
            )

            documents.append(
                Document(page_content=text)
            )


# Chia text
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)

docs = text_splitter.split_documents(documents)

# Embedding
embeddings = OllamaEmbeddings(model="nomic-embed-text")

# Vector DB
db = FAISS.from_documents(docs, embeddings)

# Chat model
llm = ChatOllama(model="tinyllama")

from ollama import chat

# QA cố định
qa_data = {}

with open("qa.txt", encoding="utf-8") as f:

    for line in f:

        line = line.strip()

        # bỏ dòng trống
        if not line:
            continue

        # kiểm tra có |
        if "|" not in line:
            continue

        question, answer = line.split("|", 1)

        qa_data[question.lower()] = answer


while True:

    question = input("You: ").lower()

    # ưu tiên QA cố định
    if question in qa_data:

        print("AI:", qa_data[question])

    # không có thì dùng RAG
    else:

        # tìm dữ liệu liên quan
        retrieved_docs = db.similarity_search(
        question,
        k=2
        )



        for doc in retrieved_docs:



        # ghép context
            context = "\n".join(
                [doc.page_content for doc in retrieved_docs]
            )

        # nếu không có dữ liệu
        if not context.strip():

            print("AI: Tôi không biết")

            continue

        # prompt
        prompt = f"""
        Chỉ trả lời dựa trên dữ liệu dưới đây.


        Dữ liệu:
        {context}

        Câu hỏi:
        {question}

        Trả lời ngắn gọn, đúng trọng tâm.
        """

        # gọi model
        response = llm.invoke(prompt)

        print("AI:", response.content)