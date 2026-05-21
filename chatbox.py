from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader
)

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

from langchain_ollama import (
    OllamaEmbeddings,
    ChatOllama
)

from langchain_community.vectorstores import FAISS

from langchain_core.documents import Document

from rapidfuzz import process

import pandas as pd
import os


# =========================
# LOAD DOCUMENTS
# =========================

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


# =========================
# SPLIT TEXT
# =========================

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)

docs = text_splitter.split_documents(
    documents
)


# =========================
# EMBEDDING
# =========================

embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)


# =========================
# VECTOR DB
# =========================

db = FAISS.from_documents(
    docs,
    embeddings
)


# =========================
# LLM
# =========================

llm = ChatOllama(
    model="tinyllama"
)


# =========================
# QA DATA
# =========================

qa_data = {}

with open("qa.txt", encoding="utf-8") as f:

    for line in f:

        line = line.strip()

        if not line:
            continue

        if "|" not in line:
            continue

        question, answer = line.split("|", 1)

        qa_data[question.lower()] = answer


# =========================
# MAIN FUNCTION
# =========================

def ask_ai(question):

    question = question.lower()


    # =====================
    # FUZZY MATCH
    # =====================

    best_match = process.extractOne(
        question,
        qa_data.keys()
    )

    if best_match and best_match[1] > 80:

        return qa_data[best_match[0]]


    # =====================
    # RAG SEARCH
    # =====================

    retrieved_docs = db.similarity_search_with_score(
        question,
        k=2
    )

    if not retrieved_docs:

        return "Tôi không biết"


    best_doc, best_score = retrieved_docs[0]


    # score cao = không liên quan
    if best_score > 1:

        return "Tôi không biết"


    # =====================
    # CONTEXT
    # =====================

    context = "\n".join(
        [doc.page_content for doc, score in retrieved_docs]
    )


    # =====================
    # PROMPT
    # =====================

    prompt = f"""
    Chỉ trả lời dựa trên dữ liệu dưới đây.

    Nếu không có thông tin thì nói:
    "Tôi không biết"

    Không được tự bịa.

    Dữ liệu:
    {context}

    Câu hỏi:
    {question}
    """


    # =====================
    # AI RESPONSE
    # =====================

    response = llm.invoke(prompt)

    return response.content