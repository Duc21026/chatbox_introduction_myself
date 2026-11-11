import hashlib
import json
import logging
import os
import re
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rapidfuzz import fuzz, process

try:
    from . import source_format
    from .documents import extract_segments, is_supported_source
    from .text_normalization import NORMALIZER_VERSION, normalize_text
except ImportError:  # direct execution from backend/
    import source_format
    from documents import extract_segments, is_supported_source
    from text_normalization import NORMALIZER_VERSION, normalize_text

logger = logging.getLogger(__name__)

REFUSAL = "Tôi không biết"
REPHRASE = "Bạn vui lòng nhập lại câu hỏi rõ ràng hơn."

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(BACKEND_DIR, "data")
DEFAULT_QA_PATH = os.path.join(BACKEND_DIR, "qa.txt")
DEFAULT_KB_PATH = os.path.join(BACKEND_DIR, "kb.json")
DEFAULT_SOURCE_PATH = os.path.join(BACKEND_DIR, "data", "chatbot.txt")


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
    top_k: int
    query_rewrite: str
    source_path: str = DEFAULT_SOURCE_PATH
    kb_path: str = DEFAULT_KB_PATH
    legacy_sources: bool = False


def load_config():
    answer_model = os.environ.get("CHATBOT_ANSWER_MODEL", "qwen2.5:7b").strip()
    if answer_model.lower().startswith("qwen3"):
        raise RuntimeError(
            "Model Qwen3 không thuộc cấu hình của chatbot này. "
            "Hãy dùng một cỡ Qwen2.5 (1.5b, 3b, 7b hoặc 14b)."
        )

    top_k = int(_env_float("CHATBOT_TOP_K", 3))
    if top_k < 1:
        raise RuntimeError("CHATBOT_TOP_K phải lớn hơn hoặc bằng 1")

    query_rewrite = os.environ.get(
        "CHATBOT_QUERY_REWRITE", "auto"
    ).strip().lower()
    if query_rewrite not in {"auto", "always", "off"}:
        raise RuntimeError(
            "CHATBOT_QUERY_REWRITE phải là một trong: auto, always, off"
        )

    legacy_sources = os.environ.get(
        "CHATBOT_LEGACY_SOURCES", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}

    return Config(
        answer_model=answer_model,
        embedding_model=os.environ.get("CHATBOT_EMBEDDING_MODEL", "bge-m3").strip(),
        relevance_threshold=_env_float("CHATBOT_RELEVANCE_THRESHOLD", 1.0),
        fuzzy_match_cutoff=_env_float("CHATBOT_FUZZY_CUTOFF", 80.0),
        data_dir=os.environ.get("CHATBOT_DATA_DIR", DEFAULT_DATA_DIR),
        qa_path=os.environ.get("CHATBOT_QA_PATH", DEFAULT_QA_PATH),
        ollama_base_url=os.environ.get(
            "CHATBOT_OLLAMA_BASE_URL", "http://127.0.0.1:11434"
        ),
        chunk_size=int(_env_float("CHATBOT_CHUNK_SIZE", 500)),
        chunk_overlap=int(_env_float("CHATBOT_CHUNK_OVERLAP", 50)),
        top_k=top_k,
        query_rewrite=query_rewrite,
        source_path=os.environ.get("CHATBOT_SOURCE_PATH", DEFAULT_SOURCE_PATH),
        kb_path=os.environ.get("CHATBOT_KB_PATH", DEFAULT_KB_PATH),
        legacy_sources=legacy_sources,
    )


config = load_config()

_db = None
_llm = None
_qa_data = None
_qa_data_signature = None
_index_embedding_model = None
_index_signature = None
_source_cache = None
_source_cache_key = None
_legacy_cache = None


class NormalizedEmbeddings(Embeddings):
    """Embedding wrapper that always feeds the shared normalized form."""

    def __init__(self, base):
        self._base = base

    def embed_documents(self, texts):
        return self._base.embed_documents(
            [
                normalize_text(text, lowercase=False) or text
                for text in texts
            ]
        )

    def embed_query(self, text):
        return self._base.embed_query(normalize_text(text) or text)


@dataclass(frozen=True)
class NormalizedQuestion:
    original: str
    normalized: str
    rewritten: Optional[str] = None
    rewrite_applied: bool = False

    @property
    def search_form(self):
        return self.rewritten if self.rewritten else self.normalized


@dataclass
class RetrievalDiagnostic:
    original_question: str
    normalized_question: str
    rewritten_question: Optional[str] = None
    source_names: list = field(default_factory=list)
    pieces: list = field(default_factory=list)
    passed_threshold: bool = False
    outcome: str = "refused"


def validate_paths():
    if config.legacy_sources:
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
        return

    if not os.path.isfile(config.source_path):
        raise RuntimeError(
            f"Không tìm thấy tệp nguồn: {config.source_path}. "
            "Hãy kiểm tra CHATBOT_SOURCE_PATH."
        )


def _legacy_source_key():
    entries = []
    directory = config.data_dir
    if os.path.isdir(directory):
        for filename in sorted(os.listdir(directory)):
            if not is_supported_source(filename):
                continue
            path = os.path.join(directory, filename)
            if not os.path.isfile(path):
                continue
            status = os.stat(path)
            entries.append([filename, status.st_mtime_ns, status.st_size])
    extra = []
    for path in (config.qa_path, config.kb_path):
        if os.path.isfile(path):
            status = os.stat(path)
            extra.append([path, status.st_mtime_ns, status.st_size])
        else:
            extra.append([path, None, None])
    return json.dumps(
        {"files": entries, "extra": extra}, ensure_ascii=False, sort_keys=True
    )


def _load_legacy_documents():
    directory = config.data_dir
    documents = []
    target = os.path.abspath(config.source_path)
    for filename in sorted(os.listdir(directory)):
        if not is_supported_source(filename):
            continue
        path = os.path.join(directory, filename)
        if not os.path.isfile(path) or os.path.abspath(path) == target:
            continue
        try:
            segments = extract_segments(path)
        except Exception as exc:
            raise RuntimeError(
                f"Không đọc được tệp dữ liệu {path}: {exc}"
            ) from exc
        for segment in segments:
            text = segment.get("text") or ""
            if not text.strip():
                continue
            metadata = {"source": filename, "source_path": path}
            page = segment.get("page")
            if page is not None:
                metadata["page"] = page
            documents.append(
                source_format.RAGDocument(page_content=text, metadata=metadata)
            )
    return documents


def _load_legacy_qa_data():
    qa_data = {}
    with open(config.qa_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or "|" not in line:
                continue
            question, answer = line.split("|", 1)
            normalized = normalize_text(question)
            if not normalized:
                continue
            qa_data[normalized] = answer.strip()
    return qa_data


def _load_legacy_kb_items():
    path = config.kb_path
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Không đọc được KB cũ {path}: {exc}") from exc
    if not isinstance(raw, list):
        raise RuntimeError("KB cũ phải là một JSON array.")
    items = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        topic = item.get("topic")
        questions = item.get("questions")
        if (
            not isinstance(item_id, str)
            or not item_id
            or item_id in seen
            or not isinstance(topic, str)
            or not topic
            or not isinstance(questions, list)
            or not questions
        ):
            continue
        bullets = item.get("answer_bullets")
        answer = item.get("answer")
        if not answer and not bullets:
            continue
        seen.add(item_id)
        items.append(
            source_format.KBItem(
                id=item_id,
                topic=topic,
                questions=[q for q in questions if isinstance(q, str) and q.strip()],
                answer=answer if isinstance(answer, str) else None,
                answer_bullets=[b for b in bullets if isinstance(b, str)]
                if isinstance(bullets, list)
                else None,
            )
        )
    return items


def _build_legacy_source():
    global _legacy_cache
    logger.warning(
        "CHATBOT_LEGACY_SOURCES đang bật: dùng qa.txt/kb.json/data/. "
        "Cấu hình này đã deprecated; hãy chuyển sang chatbot.txt."
    )
    key = _legacy_source_key()
    if _legacy_cache is not None and _legacy_cache[0] == key:
        return _legacy_cache[1]

    qa_data = _load_legacy_qa_data()
    kb_items = _load_legacy_kb_items()
    qa_pairs = []
    for index, (question, answer) in enumerate(qa_data.items()):
        qa_pairs.append(
            source_format.QAPair(
                question=question,
                normalized_question=question,
                answer=answer,
                record_id=f"legacy-{index}",
            )
        )
    rag_documents = _load_legacy_documents()

    kb_payload = [item.as_dict() for item in kb_items]
    kb_hash = hashlib.sha256(
        json.dumps(kb_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    content_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
    source_file = source_format.SourceFile(
        path="legacy",
        version="0",
        encoding="utf-8",
        text="",
        size_bytes=0,
        content_hash=content_hash,
        mtime_ns=0,
        records=[],
        warnings=[],
    )
    derived = source_format.DerivedSource(
        source_file=source_file,
        qa_pairs=qa_pairs,
        kb_items=kb_items,
        rag_documents=rag_documents,
        kb_hash=kb_hash,
        signature=source_format.SourceSignature(
            path="legacy",
            mtime_ns=0,
            size_bytes=0,
            content_hash=content_hash,
            embedding_model=config.embedding_model,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            normalizer_version=NORMALIZER_VERSION,
        ),
    )
    _legacy_cache = (key, derived)
    return derived


def _source_key(path):
    try:
        status = os.stat(path)
    except OSError:
        return None
    return (status.st_mtime_ns, status.st_size)


def get_source(force=False):
    """Return the cached ``DerivedSource``; keep the old index on bad edits."""

    global _source_cache, _source_cache_key

    if config.legacy_sources:
        return _build_legacy_source()

    key = _source_key(config.source_path)
    if _source_cache is not None and _source_cache_key == key and not force:
        return _source_cache

    try:
        derived = source_format.load_source(
            config.source_path,
            embedding_model=config.embedding_model,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )
    except Exception as exc:
        if _source_cache is not None:
            logger.error(
                "Tệp nguồn mới không hợp lệ; giữ chỉ mục cũ: %s", exc
            )
            return _source_cache
        raise

    _source_cache = derived
    _source_cache_key = key
    return derived


def _load_documents():
    return [
        Document(page_content=document.page_content, metadata=dict(document.metadata))
        for document in get_source().rag_documents
    ]


def _source_signature():
    return get_source().signature


def get_qa_data():
    global _qa_data, _qa_data_signature
    source = get_source()
    if _qa_data is None or _qa_data_signature != source.signature:
        _qa_data = {
            pair.normalized_question: pair.answer
            for pair in source.qa_pairs
            if pair.normalized_question
        }
        _qa_data_signature = source.signature
    return _qa_data


def get_db():
    global _db, _index_embedding_model, _index_signature
    validate_paths()
    source = get_source()
    signature = source.signature

    if _db is not None and signature == _index_signature:
        return _db

    documents = [
        Document(page_content=document.page_content, metadata=dict(document.metadata))
        for document in source.rag_documents
    ]
    if not documents:
        _db = None
        _index_embedding_model = config.embedding_model
        _index_signature = signature
        return None

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    counters = {}
    for chunk in chunks:
        source_name = chunk.metadata.get("source", "")
        chunk_index = counters.get(source_name, 0)
        chunk.metadata["chunk_index"] = chunk_index
        counters[source_name] = chunk_index + 1

    embeddings = NormalizedEmbeddings(
        OllamaEmbeddings(
            model=config.embedding_model, base_url=config.ollama_base_url
        )
    )
    new_db = FAISS.from_documents(chunks, embeddings)

    _db = new_db
    _index_embedding_model = config.embedding_model
    _index_signature = signature
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


def _has_vietnamese_diacritics(text):
    if "đ" in text or "Đ" in text:
        return True
    decomposed = unicodedata.normalize("NFD", text)
    return any(unicodedata.combining(character) for character in decomposed)


def _has_noise(text):
    return bool(re.search(r"(\S)\1{2,}", text)) or bool(
        re.search(r"([!?.,])\1+", text)
    )


def _should_rewrite(original, normalized):
    if config.query_rewrite == "off":
        return False
    if config.query_rewrite == "always":
        return True
    return (not _has_vietnamese_diacritics(normalized)) or _has_noise(original)


def _rewrite_query(question):
    prompt = (
        "Bạn là bộ sửa lỗi chính tả tiếng Việt. "
        "Hãy sửa lỗi chính tả và bổ sung dấu tiếng Việt còn thiếu cho câu hỏi sau. "
        "Giữ nguyên tên riêng, viết tắt và con số. "
        "Chỉ trả về đúng một câu đã sửa, không giải thích.\n\n"
        f"Câu hỏi: {question}"
    )
    try:
        response = get_llm().invoke(prompt)
        candidate = (response.content or "").strip()
    except Exception:
        return None

    if not candidate:
        return None
    if len(candidate) > max(len(question) * 3, len(question) + 60):
        return None

    normalized = normalize_text(candidate)
    return normalized or None


def prepare_question(question):
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Câu hỏi không được để trống")

    original = question.strip()
    normalized = normalize_text(original)
    if not normalized:
        return NormalizedQuestion(original=original, normalized="")

    if _should_rewrite(original, normalized):
        rewritten = _rewrite_query(original)
        if rewritten:
            rewritten = normalize_text(rewritten) or None
        if rewritten:
            return NormalizedQuestion(
                original=original,
                normalized=normalized,
                rewritten=rewritten,
                rewrite_applied=True,
            )

    return NormalizedQuestion(original=original, normalized=normalized)


def ask_ai_detailed(question):
    prepared = prepare_question(question)
    diagnostic = RetrievalDiagnostic(
        original_question=prepared.original,
        normalized_question=prepared.normalized,
        rewritten_question=prepared.rewritten,
    )

    if not prepared.normalized:
        diagnostic.outcome = "rephrase"
        return REPHRASE, diagnostic

    qa_data = get_qa_data()
    if qa_data:
        best_match = process.extractOne(
            prepared.normalized,
            qa_data.keys(),
            scorer=fuzz.ratio,
        )
        if best_match and best_match[1] > config.fuzzy_match_cutoff:
            diagnostic.outcome = "answered"
            return qa_data[best_match[0]], diagnostic

    db = get_db()
    if db is None:
        diagnostic.outcome = "refused"
        return REFUSAL, diagnostic

    retrieved_docs = db.similarity_search_with_score(
        prepared.search_form, k=config.top_k
    )

    selected = []
    for document, score in retrieved_docs:
        if not is_relevant(score):
            continue
        selected.append(document)
        source = document.metadata.get("source", "")
        if source and source not in diagnostic.source_names:
            diagnostic.source_names.append(source)
        diagnostic.pieces.append(
            {
                "source_name": source,
                "chunk_index": document.metadata.get("chunk_index"),
                "score": score,
                "excerpt": document.page_content[:200],
            }
        )

    diagnostic.passed_threshold = bool(selected)
    if not selected:
        diagnostic.outcome = "refused"
        return REFUSAL, diagnostic

    context = "\n".join(document.page_content for document in selected)
    response = get_llm().invoke(_build_prompt(context, prepared.original))
    diagnostic.outcome = "answered"
    return response.content, diagnostic


def ask_ai(question):
    return ask_ai_detailed(question)[0]


def ask_ai_stream(question):
    """Yield answer text incrementally without exposing diagnostics."""

    prepared = prepare_question(question)

    if not prepared.normalized:
        yield REPHRASE
        return

    qa_data = get_qa_data()
    if qa_data:
        best_match = process.extractOne(
            prepared.normalized,
            qa_data.keys(),
            scorer=fuzz.ratio,
        )
        if best_match and best_match[1] > config.fuzzy_match_cutoff:
            yield qa_data[best_match[0]]
            return

    db = get_db()
    if db is None:
        yield REFUSAL
        return

    retrieved_docs = db.similarity_search_with_score(
        prepared.search_form, k=config.top_k
    )
    selected = [
        document
        for document, score in retrieved_docs
        if is_relevant(score)
    ]
    if not selected:
        yield REFUSAL
        return

    context = "\n".join(document.page_content for document in selected)
    prompt = _build_prompt(context, prepared.original)
    for chunk in get_llm().stream(prompt):
        content = getattr(chunk, "content", "")
        if isinstance(content, str):
            yield content
        elif content:
            yield str(content)
