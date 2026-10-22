#!/usr/bin/env python3
"""graphic-adventure-remasterer — standalone app (Claude Agent SDK) for the HD remaster of 2D adventures.

Runs the same plugin used in Claude (skills, subagents, tools) from a terminal on your PC,
where the GPU, ComfyUI, ScummVM builds and the game files are.

    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=...            # or log in with the Claude Code CLI
    export ELEVENLABS_API_KEY=...           # only for the dubbing
    python remaster_studio.py --project ~/remaster/mio-gioco "Titolo del gioco"
"""
import argparse
import asyncio
import os
import sys

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, PermissionResultAllow,
                              PermissionResultDeny, ResultMessage, TextBlock, ToolUseBlock)

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APPEND = """
Sei graphic-adventure-remasterer, una suite per il remaster HD di avventure grafiche 2D d'epoca.
All'inizio carica la skill `remaster-orchestrator` e seguila. Rispondi in italiano.
Gli strumenti della pipeline sono in {tools}: usa `python3 {tools}/rstool.py ...`.
Lavori nella cartella del progetto {project}: i file originali del gioco non si modificano mai.
Fai le domande all'utente con lo strumento AskUserQuestion, raggruppate e solo quando servono:
all'avvio titolo, file e lingua; dopo l'analisi solo le parti a pagamento, con il costo stimato.
Esegui il piano approvato a pacchetti in sotto-sessioni in background e resta libero per l'utente.
"""

# tools that never change anything: no confirmation
READ_ONLY = {"Read", "Glob", "Grep", "WebSearch", "WebFetch", "TodoWrite", "Skill", "Task", "Agent"}


def ask_in_terminal(questions):
    """Render AskUserQuestion questions in the terminal, return the answers mapping."""
    answers = {}
    for q in questions:
        print(f"\n\033[1m{q['question']}\033[0m")
        opts = q.get("options", [])
        for i, o in enumerate(opts, 1):
            desc = f" — {o['description']}" if o.get("description") else ""
            print(f"  {i}. {o['label']}{desc}")
        print(f"  {len(opts) + 1}. Altro (scrivi tu)")
        multi = q.get("multiSelect")
        while True:
            raw = input("Scelta" + (" (es. 1,3)" if multi else "") + ": ").strip()
            picks = [p.strip() for p in raw.split(",") if p.strip()] if multi else [raw]
            labels = []
            ok = True
            for p in picks:
                if p.isdigit() and 1 <= int(p) <= len(opts):
                    labels.append(opts[int(p) - 1]["label"])
                elif p.isdigit() and int(p) == len(opts) + 1:
                    labels.append(input("Risposta: ").strip())
                elif p:
                    labels.append(p)
                else:
                    ok = False
            if ok and labels:
                answers[q["question"]] = ", ".join(labels)
                break
    return answers


def make_permission_handler(auto_yes):
    async def can_use_tool(tool_name, tool_input, context):
        if tool_name == "AskUserQuestion":
            answers = await asyncio.to_thread(ask_in_terminal, tool_input.get("questions", []))
            return PermissionResultAllow(updated_input={**tool_input, "answers": answers})
        if auto_yes or tool_name in READ_ONLY:
            return PermissionResultAllow()
        detail = tool_input.get("command") or tool_input.get("file_path") or ""
        print(f"\n\033[33m{tool_name}\033[0m {detail[:300]}")
        ans = (await asyncio.to_thread(input, "Consentire? [S/n] ")).strip().lower()
        if ans in ("", "s", "si", "sì", "y", "yes"):
            return PermissionResultAllow()
        return PermissionResultDeny(message="L'utente ha rifiutato questa azione.")
    return can_use_tool


def build_options(project, model, auto_yes):
    tools = os.path.join(PLUGIN_ROOT, "tools")
    env = {}
    if os.environ.get("ELEVENLABS_API_KEY"):
        env["ELEVENLABS_API_KEY"] = os.environ["ELEVENLABS_API_KEY"]
    return ClaudeAgentOptions(
        cwd=project,
        model=model,
        plugins=[{"type": "local", "path": PLUGIN_ROOT}],
        skills="all",
        system_prompt={"type": "preset", "preset": "claude_code",
                       "append": APPEND.format(tools=tools, project=project)},
        can_use_tool=make_permission_handler(auto_yes),
        permission_mode="default",
        env=env,
    )


async def run(args):
    os.makedirs(args.project, exist_ok=True)
    project = os.path.abspath(args.project)
    options = build_options(project, args.model, args.yes)
    first = ("Riprendi il remaster in corso." if os.path.exists(os.path.join(project, "remaster.json"))
             else f"/remaster {args.title}".strip())
    async with ClaudeSDKClient(options=options) as client:
        prompt = first
        while True:
            await client.query(prompt)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock) and msg.parent_tool_use_id is None:
                            print(block.text)
                        elif isinstance(block, ToolUseBlock) and args.verbose:
                            print(f"\033[2m· {block.name}\033[0m")
                elif isinstance(msg, ResultMessage) and args.verbose:
                    cost = getattr(msg, "total_cost_usd", None)
                    print(f"\033[2m[{msg.num_turns} turni" + (f", ${cost:.2f}" if cost else "") + "]\033[0m")
            try:
                prompt = (await asyncio.to_thread(input, "\n\033[1mTu>\033[0m ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if prompt.lower() in ("esci", "exit", "quit"):
                return 0
            if not prompt:
                prompt = "Continua."


def main():
    p = argparse.ArgumentParser(description="graphic-adventure-remasterer — remaster HD di avventure grafiche 2D")
    p.add_argument("title", nargs="?", default="", help="titolo del gioco (opzionale)")
    p.add_argument("--project", default="./remaster-progetto", help="cartella di lavoro del progetto")
    p.add_argument("--model", default=None, help="modello Claude (default: quello del CLI)")
    p.add_argument("--yes", action="store_true", help="non chiedere conferma per comandi e modifiche ai file")
    p.add_argument("--verbose", action="store_true", help="mostra gli strumenti usati e i costi")
    args = p.parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
