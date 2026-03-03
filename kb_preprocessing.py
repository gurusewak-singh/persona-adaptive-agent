from pathlib import Path

CHUNK_SIZE = 250
OVERLAP = 50
KB_ROOT = Path("knowledge base")


def tokenize(text: str) -> list[str]:
    return text.split()


def chunk_tokens(tokens: list[str], chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[list[str]]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    step = chunk_size - overlap
    chunks = []
    for start in range(0, len(tokens), step):
        end = start + chunk_size
        chunk = tokens[start:end]
        if chunk:
            chunks.append(chunk)
    return chunks


def process_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    tokens = tokenize(text)
    pieces = chunk_tokens(tokens)
    title = path.stem
    records = []
    for i, chunk in enumerate(pieces, start=1):
        records.append(
            {
                "title": title,
                "chunk_id": f"{title}-{i}",
                "text": " ".join(chunk),
            }
        )
    return records


def load_knowledge_base(root: Path = KB_ROOT) -> list[dict]:
    records = []
    for path in sorted(root.glob("**/*.txt")):
        records.extend(process_file(path))
    return records


if __name__ == "__main__":
    chunks = load_knowledge_base()
    for row in chunks:
        print(row)
