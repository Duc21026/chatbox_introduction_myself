import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

import pandas as pd
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
)
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rapidfuzz import process

REFUSAL = "Tôi không biết"


def _env_float(name, default):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Giá trị biến môi trường {name} không hợp lệ: {raw!r}"
        ) from exc


@dataclass(frozen=True)
class Config:
    answer_model: str
    embedding_model: str
    relevance_threshold: float
    fuzzy_match_cutoff: float
    data_dir: str
    qa_path: str
    ollama_base_url: str
    chunk_size: int
    chunk_overlap: int


def load_config():
    answer_model = os.environ.get("CHATBOT_ANSWER_MODEL", "qwen2.5:7b").strip()
    if answer_model.lower().startswith("qwen3"):
        raise RuntimeError(
            "Model Qwen3 không thuộc cấu hình của chatbot này. "
            "Hãy dùng một cỡ Qwen2.5 (1.5b, 3b, 7b hoặc 14b)."
        )
    return Config(
        answer_model=answer_model,
        embedding_model=os.environ.get("CHATBOT_EMBEDDING_MODEL", "bge-m3").strip(),
        relevance_threshold=_env_float("CHATBOT_RELEVANCE_THRESHOLD", 1.0),
        fuzzy_match_cutoff=_env_float("CHATBOT_FUZZY_CUTOFF", 80.0),
        data_dir=os.environ.get("CHATBOT_DATA_DIR", "data"),
        qa_path=os.environ.get("CHATBOT_QA_PATH", "qa.txt"),
        ollama_base_url=os.environ.get(
            "CHATBOT_OLLAMA_BASE_URL", "http://127.0.0.1:11434"
        ),
        chunk_size=int(_env_float("CHATBOT_CHUNK_SIZE", 500)),
        chunk_overlap=int(_env_float("CHATBOT_CHUNK_OVERLAP", 50)),
    )


config = load_config()

_db = None
_llm = None
_qa_data = None
_index_embedding_model = None


def validate_paths():
    if not os.path.isdir(config.data_dir):
        raise RuntimeError(
            f"Không tìm thấy thư mục dữ liệu: {config.data_dir}. "
            "Hãy kiểm tra CHATBOT_DATA_DIR."
        )
    if not os.path.isfile(config.qa_path):
        raise RuntimeError(
            f"Không tìm thấy tệp câu hỏi đáp: {config.qa_path}. "
            "Hãy kiểm tra CHATBOT_QA_PATH."
        )


def _load_documents():
    documents = []
    for filename in sorted(os.listdir(config.data_dir)):
        path = os.path.join(config.data_dir, filename)
        if not os.path.isfile(path):
            continue
        try:
            if filename.endswith(".txt"):
                documents.extend(
                    TextLoader(path, encoding="utf-8").load()
                )
            elif filename.endswith(".pdf"):
                documents.extend(PyPDFLoader(path).load())
            elif filename.endswith(".docx"):
                documents.extend(Docx2txtLoader(path).load())
            elif filename.endswith(".xlsx"):
                df = pd.read_excel(path)
                for _, row in df.iterrows():
                    text = " | ".join(
                        f"{col}: {row[col]}" for col in df.columns
                    )
                    documents.append(Document(page_content=text))
            elif filename.endswith(".csv"):
                df = pd.read_csv(path)
                for _, row in df.iterrows():
                    text = " | ".join(
                        f"{col}: {row[col]}" for col in df.columns
                    )
                    documents.append(Document(page_content=text))
        except Exception as exc:
            raise RuntimeError(f"Không đọc được tệp dữ liệu {path}: {exc}") from exc
    return [doc for doc in documents if doc.page_content and doc.page_content.strip()]


def _load_qa_data():
    qa_data = {}
    with open(config.qa_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or "|" not in line:
                continue
            question, answer = line.split("|", 1)
            qa_data[question.strip().lower()] = answer.strip()
    return qa_data


def get_qa_data():
    global _qa_data
    if _qa_data is None:
        _qa_data = _load_qa_data()
    return _qa_data


def get_db():
    global _db, _index_embedding_model
    if _db is None:
        validate_paths()
        documents = _load_documents()
        if not documents:
            raise RuntimeError(
                f"Không có nội dung đọc được trong thư mục dữ liệu: {config.data_dir}"
            )
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap
        )
        chunks = splitter.split_documents(documents)
        embeddings = OllamaEmbeddings(
            model=config.embedding_model, base_url=config.ollama_base_url
        )
        _db = FAISS.from_documents(chunks, embeddings)
        _index_embedding_model = config.embedding_model
    return _db


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOllama(
            model=config.answer_model, base_url=config.ollama_base_url
        )
    return _llm


def is_relevant(score):
    return score <= config.relevance_threshold


def _installed_models():
    url = config.ollama_base_url.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            "Không kết nối được Ollama tại "
            f"{config.ollama_base_url}. Hãy chạy Ollama trước khi khởi động chatbot."
        ) from exc
    return {item.get("name", "") for item in payload.get("models", [])}


def _model_present(model, installed):
    if model in installed:
        return True
    base = model.split(":", 1)[0]
    for name in installed:
        if name == model or name.startswith(model + "-"):
            return True
        if ":" not in model and name.split(":", 1)[0] == base:
            return True
    return False


def validate_models():
    installed = _installed_models()
    if not _model_present(config.answer_model, installed):
        raise RuntimeError(
            f"Không tìm thấy model trả lời {config.answer_model}. "
            "Hãy chạy 'ollama pull' cho model này, chọn cỡ Qwen2.5 nhỏ hơn, "
            "hoặc dùng dịch vụ trả lời bên ngoài."
        )
    if not _model_present(config.embedding_model, installed):
        raise RuntimeError(
            f"Không tìm thấy model embedding {config.embedding_model}. "
            "Hãy chạy 'ollama pull bge-m3'."
        )


def warm_up():
    validate_paths()
    validate_models()
    get_db()
    get_llm()


def _build_prompt(context, question):
    return f"""Bạn là trợ lý giới thiệu bản thân của Văn Phú Đức.
Chỉ trả lời dựa trên dữ liệu được cung cấp bên dưới.
Nếu dữ liệu không có thông tin, hãy trả lời đúng câu: "{REFUSAL}".
Không được tự bịa số liệu, tên riêng hay sự kiện.
Trả lời ngắn gọn, tự nhiên bằng tiếng Việt.

Dữ liệu:
{context}

Câu hỏi:
{question}"""


def ask_ai(question):
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Câu hỏi không được để trống")

    original_question = question.strip()
    normalized_question = original_question.lower()

    best_match = process.extractOne(
        normalized_question, get_qa_data().keys()
    )
    if best_match and best_match[1] > config.fuzzy_match_cutoff:
        return get_qa_data()[best_match[0]]

    retrieved_docs = get_db().similarity_search_with_score(
        normalized_question, k=2
    )
    if not retrieved_docs:
        return REFUSAL

    best_doc, best_score = retrieved_docs[0]
    if not is_relevant(best_score):
        return REFUSAL

    context = "\n".join(doc.page_content for doc, _ in retrieved_docs)
    response = get_llm().invoke(_build_prompt(context, original_question))
    return response.content
