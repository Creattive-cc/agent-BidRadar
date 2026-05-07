from pathlib import Path

PROFILE_DIR = Path("company_profile")


def ensure_profile_dir() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def read_profile_files() -> dict[str, str]:
    ensure_profile_dir()
    data: dict[str, str] = {}
    for md_file in PROFILE_DIR.glob("*.md"):
        data[md_file.name] = md_file.read_text(encoding="utf-8")
    return data
