"""Stage markdown content for MkDocs Pages build.

Copies canonical markdown from across the repo into a single `docs-build/`
tree so MkDocs sees one flat doc root without polluting the authoring layout.

Layout after staging:
  docs-build/                     <- docs/**
  docs-build/QUICKSTART.md        <- QUICKSTART.md
  docs-build/about/<name>.md      <- AGENTS | SECURITY | SUPPORT | CONTRIBUTING | CLA
  docs-build/agents/*.md          <- .github/agents/*.agent.md (suffix stripped)

Rewrites links inside each staged file based on the file's origin and
staged depth so cross-doc links resolve within the published tree.
Canonical files in the repo are never modified.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_SRC = REPO_ROOT / "docs"
STAGE = REPO_ROOT / "docs-build"

ROOT_TOP = ["QUICKSTART.md"]
ROOT_ABOUT = ["AGENTS.md", "SECURITY.md", "SUPPORT.md", "CONTRIBUTING.md"]
AGENTS_SRC = REPO_ROOT / ".github" / "agents"
CLA_SRC = REPO_ROOT / ".github" / "CLA.md"


def rewrites_for_root_top() -> list[tuple[re.Pattern[str], str]]:
    return [
        (re.compile(r"\]\(docs/"), "]("),
        (re.compile(r"\]\(\.github/agents/([^)#]+)\.agent\.md"), r"](agents/\1.md"),
        (re.compile(r"\]\(\.github/CLA\.md"), "](about/CLA.md"),
    ]


def rewrites_for_root_about() -> list[tuple[re.Pattern[str], str]]:
    return [
        (re.compile(r"\]\(docs/"), "](../"),
        (re.compile(r"\]\(\.github/agents/([^)#]+)\.agent\.md"), r"](../agents/\1.md"),
        (re.compile(r"\]\(\.github/CLA\.md"), "](CLA.md"),
        (re.compile(r"\]\(README\.md\)"), "](../index.md)"),
    ]


def rewrites_for_docs_tree(depth: int) -> list[tuple[re.Pattern[str], str]]:
    """Rewrites for a docs/ file staged `depth` dirs below docs-build root.

    Canonical links at depth N use (N+1) ``../`` segments to reach repo
    root. After staging, the file lives at docs-build/<same path>, so it
    needs N ``../`` segments to reach docs-build root. We therefore
    consume one ``../`` from every repo-root-bound link, plus remap the
    destination folders (docs/, .github/agents/, .github/CLA.md) to
    their staged locations.

    Works generically for any depth ≥ 0.
    """
    up_in = "\\.\\./" * (depth + 1)
    up_out = "../" * depth  # string prefix in replacements

    def _md(pattern_body: str, replacement_body: str) -> tuple[re.Pattern[str], str]:
        return (re.compile(r"\]\(" + up_in + pattern_body), "](" + up_out + replacement_body)

    def _click(pattern_body: str, replacement_body: str) -> tuple[re.Pattern[str], str]:
        return (re.compile(r'(click\s+\w+\s+")' + up_in + pattern_body),
                r"\1" + up_out + replacement_body)

    md_rules: list[tuple[re.Pattern[str], str]] = [
        _md(r"QUICKSTART\.md", "QUICKSTART.md"),
        _md(r"README\.md", "index.md"),
        _md(r"AGENTS\.md", "about/AGENTS.md"),
        _md(r"SECURITY\.md", "about/SECURITY.md"),
        _md(r"SUPPORT\.md", "about/SUPPORT.md"),
        _md(r"CONTRIBUTING\.md", "about/CONTRIBUTING.md"),
        _md(r"docs/", ""),
        # Repo-root pattern READMEs (e.g. patterns/sales-research-frontend/)
        # are staged into docs-build/patterns/<id>/README.md by prepare-pages.
        _md(r"patterns/", "patterns/"),
        # Custom agents are authored at .github/agents/<slug>.agent.md and
        # staged at docs-build/agents/<slug>.md (the .agent.md suffix is
        # stripped during staging). Public URL path is /agents/<slug>/.
        (re.compile(r"\]\(" + up_in + r"\.github/agents/([^)#]+)\.agent\.md"),
         "](" + up_out + r"agents/\1.md"),
        _md(r"\.github/CLA\.md", "about/CLA.md"),
    ]
    click_rules: list[tuple[re.Pattern[str], str]] = [
        _click(r"QUICKSTART\.md", "QUICKSTART.md"),
        _click(r"README\.md", "index.md"),
        (re.compile(r'(click\s+\w+\s+")' + up_in + r"\.github/agents/([^)#]+)\.agent\.md"),
         r"\1" + up_out + r"agents/\2.md"),
        _click(r"docs/", ""),
    ]
    return md_rules + click_rules


def apply_rewrites(text: str, rules: list[tuple[re.Pattern[str], str]]) -> str:
    for pat, repl in rules:
        text = pat.sub(repl, text)
    return text


# Files whose mermaid blocks should be replaced with a pre-rendered SVG at
# stage time. The committed SVG is *inlined* into the staged markdown
# (not referenced via <img>) because:
#   - <img>-embedded SVGs are not interactive — browsers do not honour
#     <a xlink:href> links inside them, so node-click navigation breaks.
#   - Inlining preserves the <a xlink:href> wrappers emitted by mmdc
#     when rendered with --securityLevel loose, keeping every node
#     clickable on the published page.
#
# Trade-off: HTML payload grows by ~SVG size (~30 KB), one-time per page
# load. Acceptable for navigation-critical diagrams.
#
# To add a new pre-rendered diagram:
#   1. Edit the source mermaid block in the markdown.
#   2. Re-render with @mermaid-js/mermaid-cli (with -c config containing
#      {"securityLevel":"loose"}) into docs/assets/diagrams/<name>.svg.
#   3. Add (source path → (svg path under docs/, alt text)) below.
MERMAID_TO_SVG: dict[str, tuple[str, str]] = {
    # source path (relative to docs/) -> (svg path relative to docs/, alt text)
    "partner-workflow.md": (
        "assets/diagrams/partner-workflow.svg",
        "Partner workflow swim-lane diagram: Delivery Lead, Partner "
        "Engineer, and Customer Ops across the seven playbook stages.",
    ),
    "index.md": (
        "assets/diagrams/10-step-flow.svg",
        "Partner walkthrough at a glance: 3 Get-ready steps feed 7 Deliver "
        "steps including architecture decision; next engagement loops back to "
        "step 5 (Discover).",
    ),
    "start/ready/01-get-oriented.md": (
        "assets/diagrams/supervisor-workers.svg",
        "Supervisor + specialist workers shape: a supervisor agent routes a "
        "customer request to specialist workers; side-effect tools pass "
        "through a HITL gate; every span emits telemetry to App Insights.",
    ),
    "start/deliver/04-provision-the-customers-azure.md": (
        "assets/diagrams/oidc-topology.svg",
        "OIDC trust path: GitHub Environment + federated credential exchange "
        "tokens with the customer's Entra app registration; the service "
        "principal has scoped RBAC on the resource group; deploy.yml runs the "
        "resolved azd target against it. No secrets cross tenants.",
    ),
}

_MERMAID_BLOCK_RE = re.compile(r"```mermaid\r?\n.*?\r?\n```", re.DOTALL)
_SVG_XML_DECL_RE = re.compile(r"<\?xml[^?]*\?>\s*", re.IGNORECASE)
_SVG_DOCTYPE_RE = re.compile(r"<!DOCTYPE[^>]*>\s*", re.IGNORECASE)
_SVG_OPEN_TAG_RE = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
_SVG_WIDTH_ATTR_RE = re.compile(r'\swidth="[^"]*"', re.IGNORECASE)
_SVG_STYLE_ATTR_RE = re.compile(r'\sstyle="[^"]*"', re.IGNORECASE)
_SVG_VIEWBOX_RE = re.compile(r'viewBox="[\d.\s\-]+"', re.IGNORECASE)


def _normalise_inline_svg(svg_text: str, alt: str) -> str:
    """Strip XML/doctype prologue and force the <svg> root to render at
    its natural pixel width so wide swim-lane diagrams keep readable
    type. The wrapping div provides horizontal scroll on narrow
    viewports."""
    svg_text = _SVG_XML_DECL_RE.sub("", svg_text, count=1)
    svg_text = _SVG_DOCTYPE_RE.sub("", svg_text, count=1)

    open_match = _SVG_OPEN_TAG_RE.search(svg_text)
    if not open_match:
        raise RuntimeError("inlined SVG has no <svg> root element")

    open_tag = open_match.group(0)
    natural_width = None
    vb = _SVG_VIEWBOX_RE.search(open_tag)
    if vb:
        parts = vb.group(0).split('"')[1].split()
        if len(parts) == 4:
            try:
                natural_width = float(parts[2])
            except ValueError:
                natural_width = None

    new_open = _SVG_WIDTH_ATTR_RE.sub("", open_tag)
    new_open = _SVG_STYLE_ATTR_RE.sub("", new_open)
    width_px = f"{int(natural_width)}px" if natural_width else "100%"
    inject = (
        f' width="{width_px}" '
        f'style="max-width: none; height: auto; display: block;" '
        f'role="img" aria-label="{alt}"'
    )
    new_open = new_open[:-1] + inject + ">"
    return svg_text.replace(open_tag, new_open, 1)


def replace_mermaid_with_svg(text: str, svg_rel: str, alt: str) -> str:
    """Inline the pre-rendered SVG inside a horizontally scrollable
    wrapper. Inlining (vs an <img>) preserves the SVG's interactive
    <a xlink:href> node links emitted by mmdc --securityLevel loose."""
    svg_path = DOCS_SRC / svg_rel
    svg_text = svg_path.read_text(encoding="utf-8")
    inlined = _normalise_inline_svg(svg_text, alt)
    replacement = (
        '<div class="workflow-diagram" style="overflow-x: auto; '
        'max-width: 100%; -webkit-overflow-scrolling: touch; '
        'padding: 0.5rem 0;">\n'
        f"{inlined}\n"
        "</div>\n"
    )
    return _MERMAID_BLOCK_RE.sub(replacement, text, count=1)


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.+?)\s*$", re.MULTILINE)


def wrap_agent_for_pages(text: str, filename: str) -> str:
    """Wrap a `*.agent.md` source for partner-facing publication.

    Custom agents are runtime system prompts for VS Code Copilot Chat — a
    wall of LLM instructions that's confusing as a standalone Pages URL.
    This function:
      1. Prepends a short partner-facing intro (what / when / what to ask).
      2. Collapses the original prompt body inside a `<details>` block so
         the page reads as orientation by default but still exposes the
         full prompt for partners who want it.

    Handles agents with or without YAML frontmatter; the `description`
    field, if present, seeds the intro paragraph. Source `.agent.md`
    files are never modified — runtime consumers (VS Code Copilot Chat)
    keep seeing the original content.
    """
    description = ""
    body = text
    fm = _FRONTMATTER_RE.match(text)
    if fm:
        body = text[fm.end():]
        desc_m = _DESCRIPTION_RE.search(fm.group(1))
        if desc_m:
            description = desc_m.group(1).strip().strip('"\'')

    slug = filename
    for suffix in (".agent.md", ".md"):
        if slug.endswith(suffix):
            slug = slug[: -len(suffix)]
            break
    command = f"/{slug}"

    intro_blurb = description or (
        "A scoped VS Code Copilot Chat custom agent bundled with this "
        "accelerator for a specific partner-delivery task."
    )

    body_stripped = body.strip()

    return (
        f"# `{command}` custom agent\n\n"
        f"!!! info \"Partner-facing intro\"\n"
        f"    **What it is:** {intro_blurb}\n\n"
        f"    **When to load it:** In **VS Code with GitHub Copilot Chat** "
        f"installed, after cloning this template repo. Open the **agents "
        f"dropdown** at the top of the Chat panel and pick `{slug}`, or "
        f"type `{command}` in the chat input. VS Code auto-discovers files "
        f"under `.github/agents/` (no workspace setting required).\n\n"
        f"    **What to ask:** Open-ended task questions in the area above; "
        f"the agent walks you through the inputs it needs and produces the "
        f"expected artifacts.\n\n"
        f"The full system prompt is reproduced below for transparency. You "
        f"don't need to read it to use the agent — Copilot loads it for "
        f"you when you select the agent or invoke `{command}`.\n\n"
        f"<details markdown=\"1\">\n"
        f"<summary><strong>System prompt (full text)</strong></summary>\n\n"
        f"{body_stripped}\n\n"
        f"</details>\n"
    )


def stage_file(src: Path, dst: Path, rules: list[tuple[re.Pattern[str], str]]) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    original = src.read_text(encoding="utf-8")
    updated = apply_rewrites(original, rules)
    # Special-case: pre-rendered SVG swap for selected wide diagrams.
    rel_key = None
    try:
        rel_key = str(src.relative_to(DOCS_SRC)).replace("\\", "/")
    except ValueError:
        pass
    if rel_key and rel_key in MERMAID_TO_SVG:
        svg_rel, alt = MERMAID_TO_SVG[rel_key]
        if not _MERMAID_BLOCK_RE.search(updated):
            raise RuntimeError(
                f"{rel_key} is registered for SVG swap but contains no "
                f"```mermaid fence. Update MERMAID_TO_SVG or restore the block."
            )
        if not (DOCS_SRC / svg_rel).exists():
            raise RuntimeError(
                f"{rel_key} maps to {svg_rel} but docs/{svg_rel} is missing. "
                f"Re-render with @mermaid-js/mermaid-cli."
            )
        updated = replace_mermaid_with_svg(updated, svg_rel, alt)
    elif _MERMAID_BLOCK_RE.search(updated):
        # Any other staged file containing a mermaid block: fail strict so
        # we don't silently regress on the client-side-render readability
        # bug. Add the file to MERMAID_TO_SVG and pre-render an SVG.
        raise RuntimeError(
            f"{rel_key or src} contains a ```mermaid fence but is not "
            f"registered in MERMAID_TO_SVG. Pre-render an SVG and add it "
            f"to the registry — client-side mermaid is unreadable in "
            f"Material's content column on narrow viewports."
        )
    dst.write_text(updated, encoding="utf-8")
    return updated != original


def stage() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    rewritten = 0

    docs_rules_cache: dict[int, list[tuple[re.Pattern[str], str]]] = {}
    for src in DOCS_SRC.rglob("*.md"):
        rel = src.relative_to(DOCS_SRC)
        depth = len(rel.parts) - 1
        rules = docs_rules_cache.setdefault(depth, rewrites_for_docs_tree(depth))
        if stage_file(src, STAGE / rel, rules):
            rewritten += 1

    # Stage non-markdown assets (workbook CSVs, ROI calculators, images,
    # etc.) so partners can download them from the published site.
    # MkDocs copies any file under `docs_dir` to the site output, so
    # mirroring the source-tree path here is enough — no nav entry
    # needed.
    asset_suffixes = {".csv", ".xlsx", ".xlsm", ".png", ".jpg", ".jpeg",
                      ".svg", ".pdf", ".gif", ".webp", ".css"}
    asset_count = 0
    for src in DOCS_SRC.rglob("*"):
        if not src.is_file() or src.suffix.lower() not in asset_suffixes:
            continue
        rel = src.relative_to(DOCS_SRC)
        dst = STAGE / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        asset_count += 1

    top_rules = rewrites_for_root_top()
    for name in ROOT_TOP:
        src = REPO_ROOT / name
        if src.exists() and stage_file(src, STAGE / name, top_rules):
            rewritten += 1

    about_rules = rewrites_for_root_about()
    for name in ROOT_ABOUT:
        src = REPO_ROOT / name
        if src.exists() and stage_file(src, STAGE / "about" / name, about_rules):
            rewritten += 1
    if CLA_SRC.exists() and stage_file(CLA_SRC, STAGE / "about" / "CLA.md", about_rules):
        rewritten += 1

    if AGENTS_SRC.exists():
        agents_dst = STAGE / "agents"
        agents_dst.mkdir(exist_ok=True)
        for agent in AGENTS_SRC.glob("*.agent.md"):
            wrapped = wrap_agent_for_pages(agent.read_text(encoding="utf-8"), agent.name)
            # Strip the .agent.md suffix in the staged filename so the
            # public URL becomes /agents/<slug>/ (no .agent in the path).
            staged_name = agent.name[: -len(".agent.md")] + ".md"
            (agents_dst / staged_name).write_text(wrapped, encoding="utf-8")

    # Stage the sales-research-frontend pattern README so the published
    # nav entry resolves. Sibling pattern READMEs (single-agent /
    # chat-with-actioning) are not staged into Pages today, so rewrite
    # those links to absolute GitHub URLs; the architecture deep-dive is
    # staged under docs/, so rewrite that to the staged path.
    frontend_pattern = REPO_ROOT / "patterns" / "sales-research-frontend" / "README.md"
    if frontend_pattern.exists():
        frontend_rules: list[tuple[re.Pattern[str], str]] = [
            (re.compile(r"\]\(\.\./single-agent/README\.md"),
             "](https://github.com/Azure-Samples/agentic-ai-solution-accelerator/blob/main/patterns/single-agent/README.md"),
            (re.compile(r"\]\(\.\./chat-with-actioning/README\.md"),
             "](https://github.com/Azure-Samples/agentic-ai-solution-accelerator/blob/main/patterns/chat-with-actioning/README.md"),
            (re.compile(r"\]\(\.\./\.\./docs/patterns/architecture/README\.md"),
             "](../architecture/README.md"),
        ]
        if stage_file(frontend_pattern,
                      STAGE / "patterns" / "sales-research-frontend" / "README.md",
                      frontend_rules):
            rewritten += 1

    total_md = sum(1 for _ in STAGE.rglob("*.md"))
    print(f"Staged {total_md} markdown files into {STAGE.relative_to(REPO_ROOT)}/")
    print(f"Staged {asset_count} non-markdown assets")
    print(f"Rewrote out-of-tree links in {rewritten} files")


if __name__ == "__main__":
    try:
        stage()
    except Exception as exc:
        print(f"prepare-pages failed: {exc}", file=sys.stderr)
        sys.exit(1)
