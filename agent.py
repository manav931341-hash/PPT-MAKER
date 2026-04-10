"""
agent.py — GoalToFileAgent: full state machine with MySQL persistence,
parallel PPTX+XLSX generation, Unsplash, Matplotlib charts, and
iterative chat-based refinement.

States: C1_INTENT → C2_STRUCTURE → C3_STYLE → C4_CONTENT → C5_FILE → DONE
"""

import os
import json
import uuid
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import anthropic

from prompts import (
    INTENT_SYSTEM, INTENT_USER,
    STRUCTURE_SYSTEM, STRUCTURE_USER_PPTX, STRUCTURE_USER_XLSX,
    CONTENT_SYSTEM, CONTENT_USER_PPTX, CONTENT_USER_XLSX,
    REFINE_SYSTEM, REFINE_USER,
    REFERENCE_ANALYSIS_SYSTEM, REFERENCE_ANALYSIS_USER,
    PPTX_STYLE_OPTIONS, XLSX_STYLE_OPTIONS, TONE_OPTIONS,
)
from database import save_session, load_session, log_generation
from generators.pptx_generator import generate_pptx
from generators.xlsx_generator import generate_xlsx

# Output directory for generated files
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
_executor = ThreadPoolExecutor(max_workers=4)


# ── LLM call helper ───────────────────────────────────────────────────────────
def _llm(system: str, user: str, max_tokens: int = 4096) -> dict:
    """Call Claude and parse JSON response robustly."""
    msg = _client.messages.create(
        model="claude-opus-4-5",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = msg.content[0].text.strip()
    # Strip accidental markdown fences (handles ```json\n...\n``` and ```\n...\n```)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]  # drop the ```json line
    if raw.endswith("```"):
        raw = raw.rsplit("\n", 1)[0]  # drop the closing ``` line
    raw = raw.strip()
    return json.loads(raw)


# ── Session helpers ───────────────────────────────────────────────────────────
def _new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def _persist(session: dict):
    if session.get("user_id"):
        save_session(session["session_id"], session["user_id"], session)


# ══════════════════════════════════════════════════════════════════════════════
# CHECKPOINT RUNNERS
# ══════════════════════════════════════════════════════════════════════════════

def run_c1_intent(goal: str, user_id: Optional[int] = None) -> dict:
    """C1: Detect intent, create session."""
    result = _llm(INTENT_SYSTEM, INTENT_USER.format(goal=goal))

    session = {
        "session_id": _new_session_id(),
        "user_id": user_id,
        "state": "C1_INTENT",
        "goal": goal,
        "domain": result.get("domain", "business"),
        "file_type": result.get("file_type", "pptx"),
        "suggested_title": result.get("suggested_title", ""),
        "structure_options": None,
        "chosen_structure": None,
        "style": None,
        "theme_id": None,
        "font_pair_id": None,
        "tone": "professional",
        "content": None,
        "generated_files": [],
        "reference_spec": None,
        "chat_history": [],
    }
    _persist(session)

    options = [
        {"key": "A", "label": "Confirm",
         "description": f"Proceed as {result['file_type'].upper()} — {result.get('reasoning', '')}"},
        {"key": "B", "label": "Switch",
         "description": "Switch to the other file type"},
        {"key": "C", "label": "Both",
         "description": "Generate both PPTX and XLSX"},
    ]

    return {
        "session": session,
        "checkpoint": 1,
        "checkpoint_name": "Intent Detection",
        "message": (
            f"I detected you want a **{result['file_type'].upper()}**.\n\n"
            f"**Title:** {result.get('suggested_title', '')}\n"
            f"**Domain:** {result.get('domain', '')}\n"
            f"**Reasoning:** {result.get('reasoning', '')}\n\n"
            "Please confirm or switch:"
        ),
        "options": options,
    }


def confirm_c1(session: dict, choice: str, extra: str = "") -> dict:
    ft = session["file_type"]
    if choice.upper() == "B":
        ft = "xlsx" if ft == "pptx" else "pptx"
    elif choice.upper() == "C":
        ft = "both"
    session["file_type"] = ft
    session["state"] = "C2_STRUCTURE"
    _persist(session)
    return run_c2_structure(session)


def run_c2_structure(session: dict) -> dict:
    """C2: Generate 3 structure options."""
    ft     = session["file_type"]
    goal   = session["goal"]
    domain = session.get("domain", "business")

    if ft in ("pptx", "both"):
        result = _llm(STRUCTURE_SYSTEM,
                      STRUCTURE_USER_PPTX.format(goal=goal, domain=domain),
                      max_tokens=6000)
    else:
        result = _llm(STRUCTURE_SYSTEM,
                      STRUCTURE_USER_XLSX.format(goal=goal, domain=domain),
                      max_tokens=6000)

    session["structure_options"] = result.get("options", [])
    session["state"] = "C2_STRUCTURE"
    _persist(session)

    opts = [
        {
            "key": o["key"],
            "label": o["label"],
            "description": (
                o["description"] + " — "
                + str(o.get("slide_count", o.get("sheets", [{}]).__len__())) + " slides/sheets"
            ),
        }
        for o in session["structure_options"]
    ]
    opts.append({"key": "M", "label": "Modify", "description": "Describe your own structure"})

    return {
        "session": session,
        "checkpoint": 2,
        "checkpoint_name": "Structure Planning",
        "message": "Here are 3 structure options. Pick one or type M to describe your own:",
        "options": opts,
    }


def confirm_c2(session: dict, choice: str, extra: str = "") -> dict:
    if choice.upper() == "M" and extra:
        # Use LLM to parse custom structure
        custom = _llm(
            STRUCTURE_SYSTEM,
            f"The user wants this custom structure for a {session['file_type']} about: {session['goal']}\n"
            f"Custom description: {extra}\n"
            "Return ONE structure option in the same JSON schema as the others.",
        )
        session["chosen_structure"] = custom
    else:
        opts = {o["key"]: o for o in session.get("structure_options", [])}
        session["chosen_structure"] = opts.get(choice.upper(), session["structure_options"][0] if session["structure_options"] else {})

    session["state"] = "C3_STYLE"
    _persist(session)
    return run_c3_style(session)


def run_c3_style(session: dict) -> dict:
    """C3: Present style/theme options."""
    ft = session["file_type"]
    style_opts = PPTX_STYLE_OPTIONS if ft in ("pptx", "both") else XLSX_STYLE_OPTIONS

    pptx_options = [
        {"key": o["key"], "label": o["label"], "description": o["description"]}
        for o in style_opts
    ]
    tone_options = [
        {"key": f"T{o['key']}", "label": o["label"], "description": ""}
        for o in TONE_OPTIONS
    ]

    return {
        "session": session,
        "checkpoint": 3,
        "checkpoint_name": "Style & Tone",
        "message": (
            "**Step 3a — Choose a visual theme** (A–H for PPTX, A–E for XLSX):\n"
            + "\n".join(f"  **{o['key']}** — {o['label']}: {o['description']}" for o in pptx_options)
            + "\n\n**Step 3b — Choose tone** (T1–T4):\n"
            + "\n".join(f"  **{o['key']}** — {o['label']}" for o in tone_options)
            + "\n\nType your choices together, e.g. **A T2**"
        ),
        "options": pptx_options + tone_options,
    }


def confirm_c3(session: dict, choice: str, extra: str = "") -> dict:
    ft = session["file_type"]
    parts = choice.upper().split()

    # Theme choice
    theme_choice = next((p for p in parts if len(p) == 1 and p.isalpha()), "A")
    tone_choice  = next((p for p in parts if p.startswith("T")), "T1")
    tone_key     = tone_choice.replace("T", "")

    style_opts = PPTX_STYLE_OPTIONS if ft in ("pptx", "both") else XLSX_STYLE_OPTIONS
    style_map  = {o["key"]: o for o in style_opts}
    tone_map   = {o["key"]: o for o in TONE_OPTIONS}

    chosen_style = style_map.get(theme_choice, style_opts[0])
    chosen_tone  = tone_map.get(tone_key, TONE_OPTIONS[0])

    session["theme_id"]     = chosen_style.get("theme_id", "professional")
    session["font_pair_id"] = chosen_style.get("font_pair_id", "montserrat_lato")
    session["tone"]         = chosen_tone.get("tone", "professional")
    session["style"]        = chosen_style.get("label", "Professional")
    session["state"]        = "C4_CONTENT"
    _persist(session)
    return run_c4_content(session)


def run_c4_content(session: dict) -> dict:
    """C4: Generate full content for all slides/sheets."""
    ft         = session["file_type"]
    goal       = session["goal"]
    theme_id   = session["theme_id"]
    font_pair  = session["font_pair_id"]
    tone       = session["tone"]
    style      = session.get("style", "Simple")
    structure  = json.dumps(session.get("chosen_structure", {}), indent=2)

    if ft in ("pptx", "both"):
        pptx_content = _llm(
            CONTENT_SYSTEM,
            CONTENT_USER_PPTX.format(
                goal=goal, theme_id=theme_id, font_pair_id=font_pair,
                tone=tone, structure_json=structure,
            ),
            max_tokens=8000,
        )
        session["pptx_content"] = pptx_content

    if ft in ("xlsx", "both"):
        # For "both", adapt structure to XLSX
        if ft == "both":
            xlsx_structure = _llm(
                STRUCTURE_SYSTEM,
                STRUCTURE_USER_XLSX.format(goal=goal, domain=session.get("domain", "business")),
                max_tokens=4000,
            )
            xlsx_struct_json = json.dumps(xlsx_structure.get("options", [{}])[0], indent=2)
        else:
            xlsx_struct_json = structure

        xlsx_content = _llm(
            CONTENT_SYSTEM,
            CONTENT_USER_XLSX.format(
                goal=goal, theme_id=theme_id, style=style,
                tone=tone, structure_json=xlsx_struct_json,
            ),
            max_tokens=6000,
        )
        session["xlsx_content"] = xlsx_content

    session["state"] = "C4_CONTENT"
    _persist(session)

    preview = _build_content_preview(session, ft)

    return {
        "session": session,
        "checkpoint": 4,
        "checkpoint_name": "Content Generation",
        "message": preview,
        "options": [
            {"key": "approve", "label": "Approve", "description": "Generate the file(s) now"},
            {"key": "regenerate", "label": "Regenerate", "description": "Re-generate all content"},
            {"key": "modify", "label": "Modify", "description": "Describe what to change"},
        ],
    }


def _build_content_preview(session: dict, ft: str) -> str:
    lines = ["**Content preview:**\n"]
    if ft in ("pptx", "both"):
        slides = session.get("pptx_content", {}).get("slides", [])
        lines.append(f"📊 **PPTX** — {len(slides)} slides:")
        for s in slides[:6]:
            lines.append(f"  • Slide {s.get('slide_number','?')}: {s.get('title','...')} [{s.get('layout_id','')}]")
        if len(slides) > 6:
            lines.append(f"  ... +{len(slides)-6} more")
    if ft in ("xlsx", "both"):
        sheets = session.get("xlsx_content", {}).get("sheets", [])
        lines.append(f"\n📋 **XLSX** — {len(sheets)} sheets:")
        for s in sheets:
            cols = [c.get("name","") for c in s.get("columns",[])]
            lines.append(f"  • {s.get('sheet_name','?')}: {', '.join(cols[:5])}")
    lines.append("\nApprove to generate files, or modify:")
    return "\n".join(lines)


def confirm_c4(session: dict, choice: str, extra: str = "") -> dict:
    c = choice.lower()
    if c == "regenerate":
        return run_c4_content(session)
    elif c == "modify" and extra:
        return run_c4_modify(session, extra)
    else:
        session["state"] = "C5_FILE"
        _persist(session)
        return run_c5_generate(session)


def run_c4_modify(session: dict, instruction: str) -> dict:
    """Apply a modification instruction to current content."""
    ft = session["file_type"]
    if ft in ("pptx", "both"):
        modified = _llm(
            REFINE_SYSTEM,
            REFINE_USER.format(
                file_type="pptx",
                goal=session["goal"],
                current_content_json=json.dumps(session.get("pptx_content", {}), indent=2),
                user_message=instruction,
            ),
            max_tokens=8000,
        )
        session["pptx_content"] = modified

    if ft in ("xlsx", "both"):
        modified = _llm(
            REFINE_SYSTEM,
            REFINE_USER.format(
                file_type="xlsx",
                goal=session["goal"],
                current_content_json=json.dumps(session.get("xlsx_content", {}), indent=2),
                user_message=instruction,
            ),
            max_tokens=6000,
        )
        session["xlsx_content"] = modified

    _persist(session)
    preview = _build_content_preview(session, ft)

    return {
        "session": session,
        "checkpoint": 4,
        "checkpoint_name": "Content Modified",
        "message": f"✅ Applied: *{instruction}*\n\n" + preview,
        "options": [
            {"key": "approve", "label": "Approve", "description": "Generate files"},
            {"key": "modify", "label": "Modify Again", "description": "More changes"},
        ],
    }


def run_c5_generate(session: dict) -> dict:
    """C5: Build actual files on disk. Parallelised for 'both'."""
    ft       = session["file_type"]
    title    = session.get("suggested_title", "output").replace(" ", "_")
    sid      = session["session_id"]
    out_dir  = os.path.join(OUTPUT_DIR, sid)
    os.makedirs(out_dir, exist_ok=True)

    files = []

    def _gen_pptx():
        path = os.path.join(out_dir, f"{title}.pptx")
        generate_pptx(session["pptx_content"], path)
        return {"filename": f"{title}.pptx", "download_url": f"/download/{sid}/{title}.pptx"}

    def _gen_xlsx():
        path = os.path.join(out_dir, f"{title}.xlsx")
        generate_xlsx(session["xlsx_content"], path)
        return {"filename": f"{title}.xlsx", "download_url": f"/download/{sid}/{title}.xlsx"}

    if ft == "both":
        # Parallel generation
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = []
            if session.get("pptx_content"):
                futures.append(ex.submit(_gen_pptx))
            if session.get("xlsx_content"):
                futures.append(ex.submit(_gen_xlsx))
            for f in futures:
                files.append(f.result())
    elif ft == "pptx":
        files.append(_gen_pptx())
    else:
        files.append(_gen_xlsx())

    session["generated_files"] = files
    session["state"] = "DONE"
    _persist(session)

    # Log to DB history
    if session.get("user_id"):
        for f in files:
            log_generation(
                user_id=session["user_id"],
                session_id=sid,
                file_type=ft,
                filename=f["filename"],
                goal=session.get("goal", ""),
                theme=session.get("theme_id", ""),
            )

    msg = "🎉 **Your files are ready!**\n\n"
    for f in files:
        msg += f"📥 [{f['filename']}]({f['download_url']})\n"
    msg += "\nYou can also chat with me to make changes — just describe what to adjust."

    return {
        "session": session,
        "checkpoint": 5,
        "checkpoint_name": "File Generated",
        "message": msg,
        "files": files,
        "done": True,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ITERATIVE CHAT REFINEMENT (post-generation)
# ══════════════════════════════════════════════════════════════════════════════

def refine_with_chat(session: dict, user_message: str) -> dict:
    """
    After files are generated, user can chat to refine.
    Regenerates and overwrites the files.
    """
    ft = session["file_type"]

    # Add to chat history
    session.setdefault("chat_history", []).append({
        "role": "user", "content": user_message
    })

    # Determine which content to modify
    if ft in ("pptx", "both") and session.get("pptx_content"):
        session["pptx_content"] = _llm(
            REFINE_SYSTEM,
            REFINE_USER.format(
                file_type="pptx",
                goal=session["goal"],
                current_content_json=json.dumps(session["pptx_content"], indent=2),
                user_message=user_message,
            ),
            max_tokens=8000,
        )

    if ft in ("xlsx", "both") and session.get("xlsx_content"):
        session["xlsx_content"] = _llm(
            REFINE_SYSTEM,
            REFINE_USER.format(
                file_type="xlsx",
                goal=session["goal"],
                current_content_json=json.dumps(session["xlsx_content"], indent=2),
                user_message=user_message,
            ),
            max_tokens=6000,
        )

    session["state"] = "C5_FILE"
    _persist(session)
    result = run_c5_generate(session)

    session["chat_history"].append({
        "role": "assistant",
        "content": f"Applied: {user_message}. Files regenerated."
    })
    _persist(session)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# REFERENCE FILE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def analyse_reference(session: dict, raw_structure: dict, ref_file_type: str) -> dict:
    """Analyse uploaded reference file and store design spec in session."""
    result = _llm(
        REFERENCE_ANALYSIS_SYSTEM,
        REFERENCE_ANALYSIS_USER.format(
            file_type=ref_file_type,
            raw_structure=json.dumps(raw_structure, indent=2)[:6000],
        ),
        max_tokens=3000,
    )
    session["reference_spec"] = result
    # Pre-set theme if detected
    if result.get("suggested_theme_id"):
        session["theme_id"] = result["suggested_theme_id"]
    if result.get("suggested_font_pair_id"):
        session["font_pair_id"] = result["suggested_font_pair_id"]
    _persist(session)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# MAIN AGENT DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

def start(goal: str, user_id: Optional[int] = None) -> dict:
    return run_c1_intent(goal, user_id)


def respond(session: dict, choice: str, extra: str = "") -> dict:
    state = session.get("state", "C1_INTENT")
    if state == "C1_INTENT":
        return confirm_c1(session, choice, extra)
    elif state == "C2_STRUCTURE":
        return confirm_c2(session, choice, extra)
    elif state == "C3_STYLE":
        return confirm_c3(session, choice, extra)
    elif state == "C4_CONTENT":
        return confirm_c4(session, choice, extra)
    elif state in ("C5_FILE", "DONE"):
        # treat any respond as a refinement
        return refine_with_chat(session, choice + (" " + extra if extra else ""))
    else:
        return {"error": f"Unknown state: {state}"}
