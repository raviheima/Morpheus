from pathlib import Path
from typing import Any, Dict, List, Set

DEFAULT_KEYWORDS_FILE = Path(__file__).parent / "keywords.txt"


def load_keyword_config(config_path: Path = None) -> Dict[str, Any]:
    """
    Loads forensic keyword configuration from keywords.txt.
    Returns fallback defaults if the configuration file is missing.
    """
    path = config_path or DEFAULT_KEYWORDS_FILE

    config = {
        "exact_suspicious_tokens": {"rat", "rats", "shell", "payload", "dump", "dumps", "beacon"},
        "prefix_suspicious_keywords": {
            "password", "credential", "secret", "private", "mimikatz",
            "lazagne", "keylog", "stealer", "meterpreter", "cobalt"
        },
        "encryption_keywords": {"truecrypt", "veracrypt", "bitlocker", "crypt", "encrypted"},
        "path_exclusions": [
            "\\windows\\system32\\winevt\\logs\\",
            "\\appdata\\local\\microsoft\\media player\\",
            "\\appdata\\roaming\\microsoft\\windows\\start menu\\",
            "\\windows\\winsxs\\",
            "\\windows\\servicing\\",
        ],
    }

    if not path.exists():
        return config

    current_section = None
    exact_tokens: Set[str] = set()
    prefix_keywords: Set[str] = set()
    encryption_keywords: Set[str] = set()
    path_exclusions: List[str] = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1].strip().lower()
                    continue

                if current_section == "exact_suspicious_tokens":
                    exact_tokens.add(line.lower())
                elif current_section == "prefix_suspicious_keywords":
                    prefix_keywords.add(line.lower())
                elif current_section == "encryption_keywords":
                    encryption_keywords.add(line.lower())
                elif current_section == "path_exclusions":
                    path_exclusions.append(line.lower())

        if exact_tokens:
            config["exact_suspicious_tokens"] = exact_tokens
        if prefix_keywords:
            config["prefix_suspicious_keywords"] = prefix_keywords
        if encryption_keywords:
            config["encryption_keywords"] = encryption_keywords
        if path_exclusions:
            config["path_exclusions"] = path_exclusions

    except Exception:
        pass

    return config
