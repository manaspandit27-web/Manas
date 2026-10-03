"""Projector demo: a plain chat with Nemotron, before and after fine-tuning on examples the class labelled.

    from lab import core, demo
    model, tok = core.load_model()
    demo.launch(model, tok)            # in Colab: prints a link that opens the chat in a new tab

In the chat page: ask questions, press Fine-tune and add the labelled CSV files students sent back, watch the
training, switch to the fine-tuned model and ask the same questions again.

    python -m lab.demo --simulate      # rehearse on a laptop: no model, simulated answers
"""

import argparse
import csv
import dataclasses
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
from urllib.parse import parse_qs, urlparse

from . import core

MODES = ("base", "tuned")  # base = the model as downloaded, tuned = with the fine-tuned adapter switched on
MIN_EXAMPLES = 8
UI_FILE = Path(__file__).resolve().parent / "demo_ui.html"
DRY_RUN_CSV = core.ROOT / "instructor" / "dry-run-2026-10-03" / "nemotron_dry_run_results.csv"
# Minutes of training per 100 example-passes on a free Colab T4, measured in the instructor dry run.
T4_MINUTES_PER_100 = {"airline_complaints": 5.7, "claims_triage": 5.8, "expense_audit": 4.4, "invoice_intake": 6.4,
                      "lead_qualification": 4.7}


class Busy(Exception):
    """The model is already doing something."""


class _Cancelled(Exception):
    pass


# ---------------------------------------------------------------- backends ---

class ModelBackend:
    """The real model. Fine-tuning adds a LoRA adapter; serving the original model switches it off again."""

    kind = "model"

    def __init__(self, model, tok):
        self.model, self.tok = model, tok
        self.tuned = None  # details of the fine-tune that is loaded, or None

    def _adapter(self, mode):
        return nullcontext() if mode == "tuned" else core._base_model(self.model)

    def answer(self, scn, text, mode, on_text=None):
        with self._adapter(mode):
            return _generate_one(self.model, self.tok, core.build_messages(scn, text), on_text)

    def greet(self, scn, on_text=None):
        """What the original model says when it is given the instruction and no message yet."""
        with self._adapter("base"):
            return _generate_one(self.model, self.tok, _opening_chat(scn), on_text, max_new_tokens=60)

    def finetune(self, scn, rows, epochs, progress):
        """Train on exactly these labelled rows, starting from the original model."""
        from peft import PeftModel
        base = self.model.unload() if isinstance(self.model, PeftModel) else self.model
        self.model, self.tuned = base, None
        only = dataclasses.replace(scn, train=rows, train_noisy=rows)
        # if this is stopped part-way, train() takes the half-trained adapter off again and self.model stays as it is
        self.model, losses = core.train(base, self.tok, only, n_examples=len(rows), epochs=epochs, progress=progress)
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
        self.tuned = None
        self._rates = _measured_rates()

    def _p(self, scn, mode, field):
        """Chance that one field comes out right."""
        if mode == "base":
            return self._rates.get((scn.key, "prompt", ""), {}).get(field, 0.35)
        clean = self._rates.get((scn.key, "fine-tuned", "clean"), {}).get(field, 0.9)
        noisy = self._rates.get((scn.key, "fine-tuned", "noisy"), {}).get(field, 0.75)
        quality = (self.tuned.get("label_accuracy") or 100) / 100  # how good the labels were
        p = noisy + (clean - noisy) * max(0.0, min(1.0, (quality - 0.7) / 0.3))
        return max(0.05, min(0.995, 1 - (1 - p) * (100 / max(self.tuned["n"], 8)) ** 0.7))  # more examples help

    def answer(self, scn, text, mode, on_text=None):
        row = next((r for r in scn.test + scn.train if r["input"] == text), None)
        rng = random.Random(f"{scn.key}|{mode}|{self.tuned and self.tuned['n']}|{text}")
        out = {}
        for f in scn.fields:
            opts = scn.choices.get(f)
            if row is None:  # a message somebody made up: there is no expert answer to be near or far from
                out[f] = rng.choice(opts) if opts else "?"
            elif rng.random() < self._p(scn, mode, f):
                out[f] = row[f]
            elif opts:
                out[f] = rng.choice([o for o in opts if o != row[f]] or opts)
            else:
                out[f] = row[f].split()[0] if " " in row[f] else row[f][:-1] or "?"
        reply = json.dumps(out)
        if on_text:
            for i in range(0, len(reply), 4):
                time.sleep(0.03 * self.speed)
                on_text(reply[:i + 4])
        return reply

    def greet(self, scn, on_text=None):
        reply = "Understood. Send me the first message and I will reply with those fields."
        if on_text:
            for i in range(0, len(reply), 4):
                time.sleep(0.03 * self.speed)
                on_text(reply[:i + 4])
        return reply

    def finetune(self, scn, rows, epochs, progress):
        self.tuned = None
        total = math.ceil(len(rows) / 4) * epochs
        pause = min(0.15, 18 / total) * self.speed
        rng, losses = random.Random(len(rows)), []
        for step in range(1, total + 1):
            time.sleep(pause)
            losses.append(round(1.4 * math.exp(-6 * step / total) + 0.04 + rng.random() * 0.04, 4))
            progress(step, total, losses[-1], pause * (total - step))
        return losses


def _measured_rates():
    """Per-field accuracy from the instructor dry run, used to make simulated answers look realistic."""
    rates = {}
    if DRY_RUN_CSV.exists():
        with open(DRY_RUN_CSV, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rates[(r["scenario"], r["method"], r["data"])] = {k: v / 100 for k, v in json.loads(r["per_field"]).items()}
    return rates


SWITCHES = "detailed thinking off"  # Nemotron's own setting line, which the lab puts above the instruction


def opening_message(scn):
    """The first message in the chat: the lab's instruction, word for word (without Nemotron's setting line).
    The model is sent this same instruction with every message."""
    prompt = core.system_prompt(scn)
    return prompt[len(SWITCHES):].strip() if prompt.startswith(SWITCHES) else prompt


def _opening_chat(scn):
    """The instruction on its own, as the first thing said to the model."""
    return [{"role": "system", "content": SWITCHES}, {"role": "user", "content": opening_message(scn)}]


# ------------------------------------------------------- labelled examples ---

def blank_examples(scn, n=100):
    """A CSV to hand to students: n messages with empty label columns."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "input", *scn.fields])
    for i in core.pick_training_rows(scn, n):
        w.writerow([scn.train[i]["id"], scn.train[i]["input"], *[""] * len(scn.fields)])
    return out.getvalue()


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


# ------------------------------------------------------------------ engine ---

class Engine:
    """What the chat page shows, and the one background job that is allowed to use the model at a time."""

    def __init__(self, backend):
        self.backend = backend
        self.lock = threading.RLock()
        self.scenarios = core.list_scenarios()
        self._scn = {}
        self.scenario = self.scenarios[0]["scenario"]
        self.serving = "base"
        self.thread = []       # the chat: questions with their answers, and the odd note
        self.examples = {"rows": [], "files": 0, "skipped": 0, "problems": []}
        self.training = {"status": "idle"}
        self.job = None
        self.error = None
        self.version = 0
        self._ids = 0
        self._worker = None

    # -- helpers --
    def scn(self):
        if self.scenario not in self._scn:
            self._scn[self.scenario] = core.load_scenario(self.scenario)
        return self._scn[self.scenario]

    def _set(self, target, key, value):
        """Change something the page shows. The lock keeps a page refresh from reading it half-changed."""
        with self.lock:
            target[key] = value
            self.version += 1

    def _next_id(self):
        self._ids += 1
        return self._ids

    def _note(self, text):
        self.thread.append({"kind": "note", "id": self._next_id(), "text": text})

    def tuned(self):
        """Details of the fine-tune that is loaded, if it was trained for the company on screen."""
        t = self.backend.tuned
        return t if t and t["scenario"] == self.scenario else None

    def _check(self):
        if self.job and self.job.get("cancel"):
            raise _Cancelled()

    def _start(self, kind, label, work):
        with self.lock:
            if self.job:
                raise Busy(f"Still busy {self.job['label']}.")
            self.job = {"type": kind, "label": label, "cancel": False}
            self.error = None
            self.version += 1

        def run():
            try:
                work()
            except _Cancelled:
                pass
            except Exception as exc:  # shown on the page; the full trace goes to the notebook output
                traceback.print_exc()
                with self.lock:
                    self.error = f"Something went wrong while {label}: {exc}"
            finally:
                with self.lock:
                    self.job = None
                    self.version += 1

        self._worker = threading.Thread(target=run, daemon=True)
        self._worker.start()

    def wait(self, timeout=None):
        """Block until the current job has finished (used by tests)."""
        if self._worker:
            self._worker.join(timeout)

    # -- the chat --
    def greet(self):
        """Open the chat: the original model answers the instruction, the way a chat assistant acknowledges one."""
        with self.lock:
            hello = {"kind": "hello", "id": self._next_id(), "status": "running", "reply": ""}

            def work():
                try:
                    reply = self.backend.greet(self.scn(), lambda text: self._set(hello, "reply", text)).strip()
                except BaseException:
                    reply = ""
                    raise
                finally:
                    with self.lock:
                        # an answer to a message that was never sent (a JSON object) is not a greeting: leave it out
                        if not reply or core.parse_output(reply) is not None:
                            self.thread.remove(hello)
                        else:
                            hello.update(status="done", reply=reply)
                        self.version += 1

            self._start("ask", "answering", work)
            self.thread.append(hello)

    def set_scenario(self, key):
        with self.lock:
            if self.job:
                raise Busy("Wait for the model to finish before switching company.")
            if key not in [s["scenario"] for s in self.scenarios]:
                raise ValueError(f"Unknown scenario {key!r}")
            self.scenario, self.thread, self.serving = key, [], "base"
            self.examples = {"rows": [], "files": 0, "skipped": 0, "problems": []}
            self.training = {"status": "idle"}
            self.greet()

    def clear(self):
        with self.lock:
            if self.job:
                raise Busy("Wait for the model to finish before clearing the chat.")
            self.thread = []
            self.greet()

    def serve_model(self, mode):
        """Choose which model answers from now on: 'base' or 'tuned'."""
        with self.lock:
            if self.job:
                raise Busy("Wait for the model to finish before switching.")
            if mode not in MODES or (mode == "tuned" and not self.tuned()):
                raise ValueError("There is no fine-tuned model yet.")
            if mode != self.serving:
                self.serving = mode
                self._note("Now talking to the fine-tuned model." if mode == "tuned" else "Now talking to the original model.")
            self.version += 1

    def _turn(self, text):
        return {"kind": "turn", "id": self._next_id(), "text": text, "mode": self.serving, "status": "waiting",
                "reply": "", "fields": None}

    def ask(self, text):
        """Add a message to the chat and let the model that is being served answer it."""
        text = (text or "").strip()[:2000]
        if not text:
            raise ValueError("Type a message first.")
        with self.lock:
            turn = self._turn(text)
            self._start("ask", "answering", lambda: self._answer(turn))
            self.thread.append(turn)

    def ask_again(self):
        """Put every earlier question to the model that is being served now."""
        with self.lock:
            turns = [t for t in self.thread if t["kind"] == "turn"]
            done = {t["text"] for t in turns if t["mode"] == self.serving}
            todo = list(dict.fromkeys(t["text"] for t in turns if t["text"] not in done))
            if not todo:
                raise ValueError("This model has already answered every question in the chat.")
            new = [self._turn(text) for text in todo]

            def work():
                for turn in new:
                    self._check()
                    self._answer(turn)

            self._start("ask", "answering", work)
            self.thread.extend(new)

    def _answer(self, turn):
        scn = self.scn()
        self._set(turn, "status", "running")
        try:
            reply = self.backend.answer(scn, turn["text"], turn["mode"], lambda text: self._set(turn, "reply", text))
        except BaseException:
            self._set(turn, "status", "failed")
            raise
        parsed = core.parse_output(reply)
        with self.lock:
            turn.update(status="done", reply=reply.strip(),
                        fields=[{"name": f, "value": str(parsed.get(f, ""))} for f in scn.fields] if parsed else None)
            self.version += 1

    # -- fine-tuning --
    def add_examples(self, files):
        """Read the labelled CSV files students sent back. Replaces whatever was added before."""
        with self.lock:
            if self.job:
                raise Busy("Wait for the model to finish first.")
            rows, skipped, problems = read_labelled(self.scn(), files)
            self.examples = {"rows": rows, "files": len(files) - len(problems), "skipped": skipped, "problems": problems}
            self.version += 1

    def _label_accuracy(self, rows):
        """How many of the class's labels agree with the lab's own answers, for messages that came from the lab."""
        scn = self.scn()
        truth = {r["input"]: r for r in scn.train}
        cells = [core._norm(r[f]) == core._norm(truth[r["input"]][f]) for r in rows if r["input"] in truth for f in scn.fields]
        return round(100 * sum(cells) / len(cells)) if cells else None

    def finetune(self, source="class", epochs=2, n=100):
        """Fine-tune on the class's labelled examples (source='class') or on n of the lab's own (source='lab')."""
        scn, epochs = self.scn(), int(epochs)
        if epochs not in (1, 2, 3):
            raise ValueError("Unsupported number of passes.")
        if source == "class":
            rows = list(self.examples["rows"])
            if len(rows) < MIN_EXAMPLES:
                raise ValueError(f"Add at least {MIN_EXAMPLES} labelled examples first.")
        else:
            rows = [scn.train[i] for i in core.pick_training_rows(scn, max(MIN_EXAMPLES, min(int(n), 300)))]
        info = {"scenario": scn.key, "source": source, "n": len(rows), "epochs": epochs,
                "label_accuracy": self._label_accuracy(rows)}

        def work():
            t = dict(info, status="running", step=0, total=math.ceil(len(rows) / 4) * epochs, loss=None, eta=None,
                     losses=[])
            with self.lock:  # the old fine-tune is dropped as training starts, so the original model answers again
                self.training, self.serving, self.backend.tuned = t, "base", None
                self.version += 1

            def progress(step, total, loss, eta):
                with self.lock:
                    t.update(step=step, total=total, loss=round(loss, 4), eta=round(eta))
                    t["losses"].append(round(loss, 4))
                    self.version += 1
                self._check()

            t0 = time.time()
            try:
                self.backend.finetune(scn, rows, epochs, progress)
            except _Cancelled:
                self._set(t, "status", "stopped")
                raise
            except Exception:
                self._set(t, "status", "failed")
                raise
            minutes = round((time.time() - t0) / 60, 1)
            with self.lock:
                self.backend.tuned = dict(info, minutes=minutes)
                t.update(status="done", minutes=minutes)
                self._note(f"Fine-tuned on {len(rows)} labelled examples in {minutes} minutes.")
                self.version += 1

        self._start("finetune", "fine-tuning", work)

    def cancel(self):
        with self.lock:
            if self.job:
                self.job["cancel"] = True
                self.version += 1

    # -- what the page shows --
    def state(self):
        with self.lock:
            scn = self.scn()
            ex = self.examples
            return json.loads(json.dumps({
                "version": self.version,
                "simulated": self.backend.kind == "simulation",
                "scenarios": self.scenarios,
                "scenario": {"key": scn.key, "opening": opening_message(scn),
                             "starters": [r["input"] for r in scn.test[:3]]},
                "serving": self.serving,
                "thread": self.thread,
                "examples": {"count": len(ex["rows"]), "files": ex["files"], "skipped": ex["skipped"],
                             "problems": ex["problems"], "min": MIN_EXAMPLES},
                "tuned": self.tuned(),
                "training": self.training,
                "t4_minutes_per_100": T4_MINUTES_PER_100.get(scn.key, 5.5),
                "busy": self.job["type"] if self.job else None,
                "error": self.error,
            }))


# ------------------------------------------------------------------ server ---

def _handler(engine):
    actions = {
        "scenario": lambda b: engine.set_scenario(b["key"]),
        "ask": lambda b: engine.ask(b.get("text")),
        "again": lambda b: engine.ask_again(),
        "serve": lambda b: engine.serve_model(b["mode"]),
        "examples": lambda b: engine.add_examples([(f["name"], f["text"]) for f in b["files"]]),
        "finetune": lambda b: engine.finetune(b.get("source", "class"), b.get("epochs", 2), b.get("n", 100)),
        "cancel": lambda b: engine.cancel(),
        "clear": lambda b: engine.clear(),
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, kind="application/json", headers=()):
            data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for k, v in headers:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                self._send(200, UI_FILE.read_bytes(), "text/html")
            elif url.path == "/api/state":
                self._send(200, engine.state())
            elif url.path == "/examples.csv":
                n = int((parse_qs(url.query).get("n") or ["100"])[0])
                name = f"{engine.scenario}_examples_to_label.csv"
                self._send(200, blank_examples(engine.scn(), max(MIN_EXAMPLES, min(n, 300))).encode("utf-8"), "text/csv",
                           [("Content-Disposition", f'attachment; filename="{name}"')])
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            name = urlparse(self.path).path.rsplit("/", 1)[-1]
            if not self.path.startswith("/api/") or name not in actions:
                return self._send(404, {"error": "not found"})
            try:
                length = min(int(self.headers.get("Content-Length") or 0), 20_000_000)
                actions[name](json.loads(self.rfile.read(length) or b"{}") if length else {})
            except Busy as exc:
                return self._send(409, {"error": str(exc)})
            except (ValueError, KeyError, TypeError) as exc:
                return self._send(400, {"error": str(exc)})
            self._send(200, engine.state())

    return Handler


def serve(engine, port=8765):
    """Start the web server in the background. Returns the server (server.shutdown() stops it)."""
    server = ThreadingHTTPServer(("127.0.0.1", port), _handler(engine))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def launch(model=None, tok=None, *, simulate=False, port=8765):
    """Start the chat page. Pass the model and tokenizer from core.load_model(), or simulate=True to rehearse
    without a model. Returns the Engine."""
    if simulate:
        backend = SimulatedBackend()
    elif model is not None:
        backend = ModelBackend(model, tok)
    else:
        raise ValueError("Pass model and tok from core.load_model(), or simulate=True.")
    engine = Engine(backend)
    engine.greet()
    engine.server = serve(engine, port)
    try:  # in Colab the page is reached through Colab's own private link to the port
        from google.colab import output
        output.serve_kernel_port_as_window(port, anchor_text="Open the Nemotron chat in a new tab")
    except ImportError:
        print(f"Nemotron chat: http://127.0.0.1:{port}")
    return engine


def keep_running(engine, every=30):
    """Run this in the notebook's last cell: it keeps the Colab session busy while the chat page is in use."""
    try:
        while True:
            model = "fine-tuned" if engine.serving == "tuned" else "original"
            print(f"\r{time.strftime('%H:%M:%S')}  chat is running, talking to the {model} model, "
                  f"{engine.job['label'] if engine.job else 'idle'}      ", end="", flush=True)
            time.sleep(every)
    except KeyboardInterrupt:
        print("\nStopped. The chat page keeps working until the runtime is disconnected.")


def main():
    ap = argparse.ArgumentParser(description="Rehearse the projector chat without a model (answers are simulated).")
    ap.add_argument("--simulate", action="store_true", help="simulated answers, for rehearsing the flow")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    if not args.simulate:
        ap.error("the real model runs from the notebook; here use --simulate")
    engine = launch(simulate=True, port=args.port)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        engine.server.shutdown()


if __name__ == "__main__":
    main()
