import hashlib
import urllib.request
from pathlib import Path

CODE_URL = (
    "https://assets.publishing.service.gov.uk/government/uploads/system/uploads/"
    "attachment_data/file/744071/"
    "CoP_FOI_Code_of_Practice_-_Minor_Amendments_20180926_.pdf"
)
CODE_SHA256 = "88c2b96146acbe3f8aadf4a3973a062ab882b8419c9b2850eca5a5ca3f8c4084"
CORPUS_PATH = Path("data/corpus/foi-code-of-practice.pdf")
MANUAL_DOWNLOAD = (
    f"Try manually downloading the Freedom of Information Code of Practice from {CODE_URL} and save it as {CORPUS_PATH}."
)

class CorpusError(Exception):
    pass

def setup_corpus() -> str:
    if CORPUS_PATH.is_file():
        if _sha256(CORPUS_PATH) != CODE_SHA256:
            raise _unexpected_version(CORPUS_PATH)
        return "present"

    request = urllib.request.Request(CODE_URL)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            CORPUS_PATH.write_bytes(response.read())
    except OSError as exc:
        CORPUS_PATH.unlink(missing_ok=True)
        raise CorpusError(
            f"Could not download the Code of Practice ({exc}).\n\n{MANUAL_DOWNLOAD}"
        ) from exc

    if _sha256(CORPUS_PATH) != CODE_SHA256:
        CORPUS_PATH.unlink(missing_ok=True)
        raise _unexpected_version(CORPUS_PATH)
    return "downloaded"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unexpected_version(path: Path) -> CorpusError:
    return CorpusError(
        f"{path} does not match the expected Code of Practice."
        "The version may be different.\n\n"
        f"{MANUAL_DOWNLOAD}"
    )
