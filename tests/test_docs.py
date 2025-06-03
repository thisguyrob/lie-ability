import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"

ENV_PATTERN_ASSIGN = re.compile(r"^([A-Z]+_[A-Z0-9_]+)=(\S+)")
ENV_PATTERN_TABLE = re.compile(r"\|\s*`?([A-Z]+_[A-Z0-9_]+)`?\s*\|\s*`?([^`|]+)`?\s*\|")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((?!http)([^)#]+)(#[^)]+)?\)")


def slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9 -]", "", slug)
    slug = slug.replace(" ", "-")
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def extract_headings(text: str):
    headings = []
    in_code = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^(#+)\s+(.*)", line)
        if m:
            headings.append(m.group(2).strip())
    return headings


def extract_envs(text: str):
    envs = []
    for line in text.splitlines():
        m1 = ENV_PATTERN_ASSIGN.match(line.strip())
        if m1:
            envs.append((m1.group(1), m1.group(2)))
        m2 = ENV_PATTERN_TABLE.search(line)
        if m2:
            envs.append((m2.group(1), m2.group(2)))
    return envs


def collect_anchors(path: Path):
    anchors = set()
    text = path.read_text()
    for heading in extract_headings(text):
        anchors.add(slugify(heading))
    return anchors


def iter_docs():
    return sorted(DOCS_DIR.rglob("*.md"))


def test_no_duplicate_headings_and_no_todo():
    for md in iter_docs():
        text = md.read_text()
        assert "TODO" not in text, f"TODO found in {md}"
        headings = extract_headings(text)
        duplicates = {h for h in headings if headings.count(h) > 1}
        assert not duplicates, f"Duplicate headings in {md}: {duplicates}"


def test_env_defaults_consistent():
    defaults = {}
    for md in iter_docs():
        for env, val in extract_envs(md.read_text()):
            if env in defaults and defaults[env] != val:
                raise AssertionError(
                    f"Conflicting default for {env}: {defaults[env]} vs {val} in {md}"
                )
            defaults.setdefault(env, val)


def test_internal_links_resolve():
    anchor_cache = {}
    for md in iter_docs():
        text = md.read_text()
        for label, target, anchor in LINK_PATTERN.findall(text):
            target_path = (md.parent / target).resolve()
            assert target_path.exists(), f"Broken link {target} in {md}"
            if anchor:
                slug = anchor.lstrip("#")
                if target_path not in anchor_cache:
                    anchor_cache[target_path] = collect_anchors(target_path)
                assert (
                    slug in anchor_cache[target_path]
                ), f"Missing anchor {anchor} in {target_path}"
