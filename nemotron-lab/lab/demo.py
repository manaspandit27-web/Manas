"""Projector demo: a plain chat with Nemotron. The fine-tuning itself happens in the notebook, in front of the class.

    from lab import core, demo
    model, tok = core.load_model()
    chat = demo.launch(model, tok, scenario="airline_complaints")   # prints the chat's address

    labelled = chat.read_labelled(files.upload())   # the examples file the class filled in
    losses = chat.finetune(labelled, epochs=2)      # trains here, in the notebook cell
    chat.serve("fine-tuned")                        # the chat now answers with the fine-tuned model

The file to hand to students is scenarios/<name>/examples_to_label.csv.

    python -m lab.demo --simulate        # rehearse on a laptop: no model, simulated answers
    python -m lab.demo --write-examples  # rebuild the examples_to_label.csv files
"""

import argparse
import csv
import io
import json
import math
import random
import threading
import time
import traceback
from collections import Counter
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import core

MIN_EXAMPLES = 8
EXAMPLES_FILE = "examples_to_label.csv"
UI_FILE = Path(__file__).resolve().parent / "demo_ui.html"
DRY_RUN_CSV = core.ROOT / "instructor" / "dry-run-2026-10-03" / "nemotron_dry_run_results.csv"
SWITCHES = "detailed thinking off"  # Nemotron's own setting line, which the lab puts above the instruction


class Busy(Exception):
    """The model is already doing something."""


def opening_message(scn):
    """The first message in the chat: the lab's instruction, word for word (without Nemotron's setting line).
    The model is sent this same instruction with every message."""
    prompt = core.system_prompt(scn)
    return prompt[len(SWITCHES):].strip() if prompt.startswith(SWITCHES) else prompt


# ---------------------------------------------------------------- backends ---

class ModelBackend:
    """The real model. Fine-tuning adds a LoRA adapter; the original model is the same one with it switched off."""

    kind = "model"

    def __init__(self, model, tok):
        self.model, self.tok = model, tok

    def _adapter(self, tuned):
        return nullcontext() if tuned else core._base_model(self.model)

    def answer(self, scn, text, tuned, on_text=None):
        with self._adapter(tuned):
            return _generate_one(self.model, self.tok, core.build_messages(scn, text), on_text)

    def greet(self, scn, on_text=None):
        """What the original model says when it is given the instruction and no message yet."""
        chat = [{"role": "system", "content": SWITCHES}, {"role": "user", "content": opening_message(scn)}]
        with self._adapter(False):
            return _generate_one(self.model, self.tok, chat, on_text, max_new_tokens=60)

    def finetune(self, scn, rows, epochs):
        """Train on exactly these labelled rows, starting from the original model. Prints its progress."""
        from peft import PeftModel
        base = self.model.unload() if isinstance(self.model, PeftModel) else self.model
        self.model = base  # if training is interrupted, train() takes the half-trained adapter off again
        self.model, losses = core.train(base, self.tok, scn, epochs=epochs, rows=rows)
        return losses


def _generate_one(model, tok, messages, on_text=None, max_new_tokens=120):
    """Greedy generation for one conversation, reporting the text as it is produced."""
    import torch
    from transformers.generation.streamers import BaseStreamer

    prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    enc = tok([prompt], return_tensors="pt", add_special_tokens=False).to(next(model.parameters()).device)

    class Stream(BaseStreamer):
        def __init__(self):
            self.ids, self.prompt_seen = [], False

        def put(self, value):
            if not self.prompt_seen:  # the first call hands back the prompt itself
                self.prompt_seen = True
                return
            self.ids.extend(value.reshape(-1).tolist())
            on_text(tok.decode(self.ids, skip_special_tokens=True))

        def end(self):
            pass

    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False, pad_token_id=tok.pad_token_id,
                             eos_token_id=core._stop_ids(tok), streamer=Stream() if on_text else None)
    return tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True)


class SimulatedBackend:
    """No model: made-up answers, right about as often as the real model was in the dry run. For rehearsing only."""

    kind = "simulation"

    def __init__(self, speed=1.0):
        self.speed = speed  # 0 = no waiting (tests)
        self.trained_on = 0
        self._rates = {}
        if DRY_RUN_CSV.exists():
            with open(DRY_RUN_CSV, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    self._rates[(r["scenario"], r["method"], r["data"])] = {
                        k: v / 100 for k, v in json.loads(r["per_field"]).items()}

    def _type(self, reply, on_text):
        if on_text:
            for i in range(0, len(reply), 4):
                time.sleep(0.03 * self.speed)
                on_text(reply[:i + 4])
        return reply

    def answer(self, scn, text, tuned, on_text=None):
        row = next((r for r in scn.test + scn.train if r["input"] == text), None)
        key = (scn.key, "fine-tuned", "clean") if tuned else (scn.key, "prompt", "")
        rng = random.Random(f"{scn.key}|{tuned}|{self.trained_on}|{text}")
        out = {}
        for f in scn.fields:
            opts = scn.choices.get(f)
            if row is None:  # a message somebody made up: there is no expert answer to be near or far from
                out[f] = rng.choice(opts) if opts else "?"
            elif rng.random() < self._rates.get(key, {}).get(f, 0.9 if tuned else 0.35):
                out[f] = row[f]
            elif opts:
                out[f] = rng.choice([o for o in opts if o != row[f]] or opts)
            else:
                out[f] = row[f].split()[0] if " " in row[f] else row[f][:-1] or "?"
        return self._type(json.dumps(out), on_text)

    def greet(self, scn, on_text=None):
        return self._type("Understood. Send me the first message and I will reply with those fields.", on_text)

    def finetune(self, scn, rows, epochs):
        total = math.ceil(len(rows) / 4) * epochs
        print(f"(Simulated) training on {len(rows)} labelled examples for {epochs} epoch(s) = {total} steps")
        bar, rng, losses = core._bar(total, "Fine-tuning"), random.Random(len(rows)), []
        for step in range(1, total + 1):
            time.sleep(min(0.15, 18 / total) * self.speed)
            losses.append(round(1.4 * math.exp(-6 * step / total) + 0.04 + rng.random() * 0.04, 4))
            bar(step, extra=f"loss {losses[-1]:.3f}")
        bar(total, finished=True, extra="done")
        self.trained_on = len(rows)
        return losses


# ------------------------------------------------------- labelled examples ---

def blank_examples(scn, n=100):
    """The CSV to hand to students: n messages with empty label columns."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["id", "input", *scn.fields])
    for i in core.pick_training_rows(scn, n):
        w.writerow([scn.train[i]["id"], scn.train[i]["input"], *[""] * len(scn.fields)])
    return out.getvalue()


def write_examples():
    """Write scenarios/<name>/examples_to_label.csv for every company."""
    for s in core.list_scenarios():
        scn = core.load_scenario(s["scenario"])
        path = core.SCENARIO_DIR / scn.key / EXAMPLES_FILE
        path.write_text(blank_examples(scn), encoding="utf-8")
        print("wrote", path)


def _loose(value):
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def read_labelled(scn, files):
    """Turn the CSV files students sent back into training rows.

    files: list of (name, text). Each file needs an `input` (or `id`) column and one column per answer field.
    Rows with a missing or unknown label are skipped. When several students labelled the same message, the most
    common label wins. Returns (rows, skipped, problems)."""
    by_id = {r["id"]: r for r in scn.train}
    votes, skipped, problems = {}, 0, []
    for name, text in files:
        text = text.lstrip("﻿")
        try:
            dialect = csv.Sniffer().sniff(text[:4000], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
        cols = {_loose(c): c for c in (rows[0].keys() if rows else []) if c}
        missing = [f for f in scn.fields if _loose(f) not in cols]
        if not rows or missing or not ({"input", "id"} & set(cols)):
            problems.append(f"{name}: needs an input column and a column for each of {', '.join(scn.fields)}.")
            continue
        for r in rows:
            message = (r.get(cols.get("input", "")) or "").strip()
            if not message and r.get(cols.get("id", "")) in by_id:  # the message column was deleted, but the id is there
                message = by_id[r[cols["id"]]]["input"]
            labels = {}
            for f in scn.fields:
                v, opts = (r.get(cols[_loose(f)]) or "").strip(), scn.choices.get(f)
                if opts:  # forgive capitals, spaces and hyphens: "Baggage services" means baggage_services
                    v = next((o for o in opts if _loose(o) == _loose(v)), "")
                if v:
                    labels[f] = v
            if not message or len(labels) < len(scn.fields):
                skipped += bool(labels) or any((r.get(cols[_loose(f)]) or "").strip() for f in scn.fields)
                continue  # rows nobody started are not counted as skipped
            votes.setdefault(message, []).append(labels)
    out = []
    for message, vs in votes.items():
        row = {"id": f"class-{len(out):04d}", "input": message}
        for f in scn.fields:
            row[f] = Counter(v[f] for v in vs).most_common(1)[0][0]
        out.append(row)
    return out, skipped, problems


# -------------------------------------------------------------------- chat ---

class Chat:
    """The chat page's state, plus the three things the notebook does: read the labels, fine-tune, switch model."""

    def __init__(self, backend, scenario=None):
        self.backend = backend
        self.scn = core.load_scenario(scenario or core.list_scenarios()[0]["scenario"])
        self.lock = threading.RLock()
        self.serving = "original"   # which model answers: "original" or "fine-tuned"
        self.tuned = None           # details of the fine-tune, once there is one
        self.thread = []            # the conversation: questions with their answers, and the odd note
        self.busy = None            # "answering" or "fine-tuning": the model does one thing at a time
        self.error = None
        self.version = 0
        self._ids = 0
        self._worker = None

    # -- helpers --
    def _set(self, target, key, value):
        """Change something the page shows. The lock keeps a page refresh from reading it half-changed."""
        with self.lock:
            target[key] = value
            self.version += 1

    def _free(self):
        with self.lock:
            self.busy = None
            self.version += 1

    def _next_id(self):
        self._ids += 1
        return self._ids

    def _note(self, text):
        with self.lock:
            self.thread.append({"kind": "note", "id": self._next_id(), "text": text})
            self.version += 1

    def _start(self, work):
        """Answer in the background, so the page stays responsive."""
        with self.lock:
            if self.busy:
                raise Busy("The model is busy fine-tuning in the notebook." if self.busy == "fine-tuning"
                           else "Wait for the answer to finish.")
            self.busy, self.error = "answering", None
            self.version += 1

        def run():
            try:
                work()
            except Exception as exc:  # shown on the page; the full trace goes to the notebook output
                traceback.print_exc()
                self.error = f"Something went wrong: {exc}"
            finally:
                self._free()

        self._worker = threading.Thread(target=run, daemon=True)
        self._worker.start()

    def wait(self, timeout=None):
        """Block until the answer in progress has finished."""
        if self._worker:
            self._worker.join(timeout)

    # -- the conversation --
    def greet(self):
        """Open the chat: the original model answers the instruction, the way a chat assistant acknowledges one."""
        with self.lock:
            hello = {"kind": "hello", "id": self._next_id(), "status": "running", "reply": ""}

            def work():
                reply = ""
                try:
                    reply = self.backend.greet(self.scn, lambda text: self._set(hello, "reply", text)).strip()
                finally:
                    with self.lock:
                        # an answer to a message that was never sent (a JSON object) is not a greeting: leave it out
                        if not reply or core.parse_output(reply) is not None:
                            self.thread.remove(hello)
                        else:
                            hello.update(status="done", reply=reply)
                        self.version += 1

            self._start(work)
            self.thread.append(hello)

    def clear(self):
        with self.lock:
            if self.busy:
                raise Busy("Wait for the model to finish before clearing the chat.")
            self.thread = []
            self.greet()

    def _turn(self, text):
        return {"kind": "turn", "id": self._next_id(), "text": text, "model": self.serving, "status": "waiting",
                "reply": "", "fields": None}

    def ask(self, text):
        """Add a message to the chat and let the model that is being served answer it."""
        text = (text or "").strip()[:2000]
        if not text:
            raise ValueError("Type a message first.")
        with self.lock:
            turn = self._turn(text)
            self._start(lambda: self._answer(turn))
            self.thread.append(turn)

    def ask_again(self):
        """Put every earlier question to the model that is being served now."""
        with self.lock:
            turns = [t for t in self.thread if t["kind"] == "turn"]
            done = {t["text"] for t in turns if t["model"] == self.serving}
            todo = list(dict.fromkeys(t["text"] for t in turns if t["text"] not in done))
            if not todo:
                raise ValueError("This model has already answered every question in the chat.")
            new = [self._turn(text) for text in todo]

            def work():
                for turn in new:
                    self._answer(turn)

            self._start(work)
            self.thread.extend(new)

    def _answer(self, turn):
        self._set(turn, "status", "running")
        try:
            reply = self.backend.answer(self.scn, turn["text"], turn["model"] == "fine-tuned",
                                        lambda text: self._set(turn, "reply", text))
        except BaseException:
            self._set(turn, "status", "failed")
            raise
        parsed = core.parse_output(reply)
        with self.lock:
            turn.update(status="done", reply=reply.strip(),
                        fields=[{"name": f, "value": str(parsed.get(f, ""))} for f in self.scn.fields] if parsed else None)
            self.version += 1

    # -- run from the notebook, in front of the class --
    def read_labelled(self, files):
        """Read the examples file (or files) the class filled in and return them as training rows.

        files: what Colab's files.upload() returns, or a list of file paths."""
        if isinstance(files, dict):
            named = [(name, data.decode("utf-8-sig") if isinstance(data, bytes) else data) for name, data in files.items()]
        else:
            named = [(Path(p).name, Path(p).read_text(encoding="utf-8-sig")) for p in ([files] if isinstance(files, (str, Path)) else files)]
        rows, skipped, problems = read_labelled(self.scn, named)
        for problem in problems:
            print("Could not use", problem)
        print(f"{len(rows)} labelled examples from {len(named) - len(problems)} file(s)"
              + (f", {skipped} row(s) skipped because a label was missing or not one of the allowed values" if skipped else ""))
        return rows

    def lab_examples(self, n=100):
        """The lab's own labelled examples, for trying the notebook without a class."""
        return [self.scn.train[i] for i in core.pick_training_rows(self.scn, n)]

    def finetune(self, rows, epochs=2):
        """Fine-tune the model on these labelled examples. Runs here, in the notebook cell, and prints its progress.
        The chat keeps answering with the original model until serve("fine-tuned")."""
        rows = list(rows)
        if len(rows) < MIN_EXAMPLES:
            raise ValueError(f"Only {len(rows)} labelled examples. At least {MIN_EXAMPLES} are needed.")
        self.wait()
        with self.lock:
            if self.busy:
                raise Busy("The chat is in the middle of an answer. Run this cell again in a moment.")
            self.busy, self.serving, self.tuned = "fine-tuning", "original", None
            self.version += 1
        t0 = time.time()
        try:
            losses = self.backend.finetune(self.scn, rows, epochs)
            minutes = round((time.time() - t0) / 60, 1)
            with self.lock:
                self.tuned = {"examples": len(rows), "epochs": epochs, "minutes": minutes}
            self._note(f"Fine-tuned on {len(rows)} labelled examples in {minutes} minutes.")
        finally:
            self._free()
        return losses

    def serve(self, which):
        """Choose the model the chat answers with: "original" or "fine-tuned"."""
        if which not in ("original", "fine-tuned"):
            raise ValueError('Choose "original" or "fine-tuned".')
        if which == "fine-tuned" and not self.tuned:
            raise ValueError("There is no fine-tuned model yet. Run the fine-tuning cell first.")
        self.wait()
        with self.lock:
            changed, self.serving = which != self.serving, which
        if changed:
            self._note(f"Now talking to the {which} model.")
        print(f"The chat now answers with the {which} model.")

    # -- what the page shows --
    def state(self):
        with self.lock:
            return json.loads(json.dumps({
                "version": self.version,
                "simulated": self.backend.kind == "simulation",
                "company": self.scn.company,
                "opening": opening_message(self.scn),
                "starters": [r["input"] for r in self.scn.test[:3]],
                "serving": self.serving,
                "thread": self.thread,
                "busy": self.busy,
                "error": self.error,
            }))


# ------------------------------------------------------------------ server ---

def _handler(chat):
    actions = {"ask": lambda b: chat.ask(b.get("text")), "again": lambda b: chat.ask_again(), "clear": lambda b: chat.clear()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, kind="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._send(200, UI_FILE.read_bytes(), "text/html")
            elif path == "/api/state":
                self._send(200, chat.state())
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            name = urlparse(self.path).path.rsplit("/", 1)[-1]
            if not self.path.startswith("/api/") or name not in actions:
                return self._send(404, {"error": "not found"})
            try:
                length = min(int(self.headers.get("Content-Length") or 0), 100_000)
                actions[name](json.loads(self.rfile.read(length) or b"{}") if length else {})
            except Busy as exc:
                return self._send(409, {"error": str(exc)})
            except (ValueError, KeyError, TypeError) as exc:
                return self._send(400, {"error": str(exc)})
            self._send(200, chat.state())

    return Handler


def serve(chat, port=8765):
    """Start the web server in the background. Returns the server (server.shutdown() stops it)."""
    server = ThreadingHTTPServer(("127.0.0.1", port), _handler(chat))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def launch(model=None, tok=None, *, scenario=None, simulate=False, port=8765):
    """Start the chat page for one company. Pass the model and tokenizer from core.load_model(), or simulate=True
    to rehearse without a model. Returns the Chat, which the notebook uses to fine-tune and switch model."""
    if simulate:
        backend = SimulatedBackend()
    elif model is not None:
        backend = ModelBackend(model, tok)
    else:
        raise ValueError("Pass model and tok from core.load_model(), or simulate=True.")
    chat = Chat(backend, scenario)
    chat.greet()
    chat.server = serve(chat, port)
    try:  # in Colab the page is reached through Colab's own private address for the port
        from google.colab.output import eval_js
        chat.url = eval_js(f"google.colab.kernel.proxyPort({port})")
    except ImportError:
        chat.url = f"http://127.0.0.1:{port}"
    print("Nemotron chat:", chat.url)
    return chat


def main():
    ap = argparse.ArgumentParser(description="Rehearse the projector chat without a model, or rebuild the examples files.")
    ap.add_argument("--simulate", action="store_true", help="simulated answers, for rehearsing the flow")
    ap.add_argument("--scenario", help="which company (default: the first one)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--write-examples", action="store_true", help=f"write scenarios/<name>/{EXAMPLES_FILE}")
    args = ap.parse_args()
    if args.write_examples:
        return write_examples()
    if not args.simulate:
        ap.error("the real model runs from the notebook; here use --simulate")
    chat = launch(simulate=True, scenario=args.scenario, port=args.port)
    try:  # stands in for the notebook's fine-tuning cells
        input("Ask a few questions in the chat. Then press Enter here to fine-tune (simulated) and switch model. ")
        chat.finetune(chat.lab_examples(100))
        chat.serve("fine-tuned")
        input("Now ask the same questions again in the chat. Press Enter to quit. ")
    except EOFError:  # no terminal to press Enter in: just keep the page up
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    chat.server.shutdown()


if __name__ == "__main__":
    main()
