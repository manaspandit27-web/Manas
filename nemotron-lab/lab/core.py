"""Everything the student notebook needs, kept out of the notebook so its cells stay short.

Three ways to bring company knowledge to a model are compared on the same test set:
  1. prompt      - the model only sees the task and the allowed answers
  2. prompt+docs - the company policy document is pasted into the prompt (what RAG automates)
  3. fine-tuned  - the model is trained on labeled examples (LoRA on a 4-bit Nemotron)
"""

import csv
import json
import math
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DIR = ROOT / "scenarios"
DEFAULT_MODEL = "nvidia/Llama-3.1-Nemotron-Nano-4B-v1.1"
MAX_CHOICES = 12  # a label column with this many distinct values or fewer is a fixed list of choices


# Starter edge cases for Step 7 of the notebook: each one mixes two rules from the policy.
SAMPLE_TESTS = {
    "airline_complaints": "I'm a Platinum member. My flight SK220 from Boston to Denver was delayed 3 hours "
                          "and then the gate agent was rude to me.",
    "invoice_intake": "Invoice INV-55120 attached for this week's salmon and shrimp plus a fryer repair, "
                      "total $9,980.00, Net 30. Thanks, Dana | Atlantic Catch Seafood",
    "claims_triage": "My Granite Shield policy started 3 weeks ago. Someone smashed my windshield last night, "
                     "about $600 to replace. Nobody was hurt.",
    "expense_audit": "Client dinner with Orbit Bank, 5 people including me, $640 total, plus a $90 bottle of wine "
                     "for the table. Receipt attached.",
    "lead_qualification": "Hi, I'm the CFO of a 2,500-person hospital network in Sydney. We're already a Lumen "
                          "customer in the US and want pricing for our Australian team.",
}


# ------------------------------------------------------------------ data ---

@dataclass
class Scenario:
    key: str
    title: str
    company: str
    task: str
    fields: dict   # field -> short description
    choices: dict  # field -> list of allowed values, or None for free text
    train: list
    train_noisy: list
    test: list
    policy: str = ""
    case: str = ""


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _infer_choices(fields, rows):
    choices = {}
    for f in fields:
        values = sorted({r[f] for r in rows})
        choices[f] = values if len(values) <= MAX_CHOICES else None
    return choices


def list_scenarios():
    out = []
    for d in sorted(SCENARIO_DIR.iterdir()):
        if (d / "scenario.json").exists():
            meta = json.loads((d / "scenario.json").read_text())
            out.append({"scenario": d.name, "title": meta["title"], "function": meta["function"]})
    return out


def load_scenario(key):
    d = SCENARIO_DIR / key
    if not d.exists():
        raise ValueError(f"Unknown scenario '{key}'. Choose one of: {[s['scenario'] for s in list_scenarios()]}")
    meta = json.loads((d / "scenario.json").read_text())
    train, test = _read_csv(d / "train.csv"), _read_csv(d / "test.csv")
    fields = {f: meta["fields"].get(f, f) for f in train[0] if f not in ("id", "input")}
    return Scenario(key=key, title=meta["title"], company=meta["company"], task=meta["task"], fields=fields,
                    choices=_infer_choices(fields, train + test), train=train,
                    train_noisy=_read_csv(d / "train_noisy.csv"), test=test,
                    policy=(d / "policy.md").read_text(), case=(d / "case.md").read_text())


def load_custom(csv_path, company, task, policy="", test_fraction=0.2, seed=0):
    """Bring your own process: a CSV with an `input` column plus one column per answer field."""
    rows = _read_csv(csv_path)
    if not rows or "input" not in rows[0]:
        raise ValueError("The CSV needs a column called 'input' plus one column for each answer field.")
    rows = [r for r in rows if r["input"].strip()]
    random.Random(seed).shuffle(rows)
    n_test = max(5, int(len(rows) * test_fraction))
    test, train = rows[:n_test], rows[n_test:]
    fields = {f: f for f in rows[0] if f not in ("id", "input")}
    return Scenario(key="custom", title=f"{company} - custom", company=company, task=task, fields=fields,
                    choices=_infer_choices(fields, rows), train=train, train_noisy=train, test=test, policy=policy)


# --------------------------------------------------------------- prompts ---

def system_prompt(scn, include_policy=False):
    lines = ["detailed thinking off", "", f"You work at {scn.company}. {scn.task}", "",
             "Reply with ONLY a JSON object with exactly these keys:"]
    for f, desc in scn.fields.items():
        opts = scn.choices.get(f)
        lines.append(f'- "{f}": {desc}' + (f". One of: {', '.join(opts)}" if opts else ""))
    if include_policy and scn.policy:
        lines += ["", "Apply this company policy:", scn.policy.strip()]
    return "\n".join(lines)


def answer_json(scn, row):
    return json.dumps({f: row[f] for f in scn.fields})


def build_messages(scn, text, include_policy=False, answer=None):
    msgs = [{"role": "system", "content": system_prompt(scn, include_policy)},
            {"role": "user", "content": text}]
    if answer is not None:
        msgs.append({"role": "assistant", "content": answer})
    return msgs


# --------------------------------------------------------------- scoring ---

def parse_output(text):
    """Pull the first JSON object out of a model reply. Returns a dict, or None if there isn't one."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
                return {str(k).strip().lower(): v for k, v in obj.items()} if isinstance(obj, dict) else None
    return None


def _norm(v):
    if isinstance(v, bool):
        return "yes" if v else "no"
    s = str(v).strip().lower().replace("$", "").replace(",", "")
    s = {"true": "yes", "false": "no"}.get(s, s)
    try:
        return f"{float(s):.2f}"
    except ValueError:
        return s


def wilson_range(k, n, z=1.96):
    """95% confidence range (in %) for k successes out of n. If two methods' ranges don't overlap,
    the difference is very unlikely to be luck."""
    if n == 0:
        return 0, 0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return round(100 * max(0.0, centre - half)), round(100 * min(1.0, centre + half))


def score(scn, rows, replies, label):
    """Compare model replies to the expert labels. Returns {'summary': {...}, 'rows': [...]}."""
    per_row, correct = [], {f: 0 for f in scn.fields}
    valid = all_right = 0
    for row, reply in zip(rows, replies):
        pred = parse_output(reply)
        rec = {"id": row["id"], "input": row["input"], "reply": reply.strip()}
        ok_all = pred is not None
        valid += pred is not None
        for f in scn.fields:
            got = pred.get(f, "") if pred else ""
            hit = pred is not None and _norm(got) == _norm(row[f])
            correct[f] += hit
            ok_all &= hit
            rec[f"{f} (expert)"] = row[f]
            rec[f"{f} (model)"] = got
        all_right += ok_all
        rec["all correct"] = ok_all
        per_row.append(rec)
    n = max(len(rows), 1)
    lo, hi = wilson_range(all_right, n)
    summary = {"method": label, "examples": len(rows), "valid JSON %": round(100 * valid / n),
               "all fields correct %": round(100 * all_right / n), "95% range": f"{lo}-{hi}%"}
    summary.update({f"{f} %": round(100 * c / n) for f, c in correct.items()})
    return {"summary": summary, "rows": per_row}


# ----------------------------------------------------------------- model ---

def load_model(model_id=DEFAULT_MODEL):
    """Load Nemotron in 4-bit on the GPU (about 3 GB of GPU memory)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    if not torch.cuda.is_available():
        raise RuntimeError("No GPU found. In Colab: Runtime > Change runtime type > T4 GPU, then re-run this cell.")
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    tok = AutoTokenizer.from_pretrained(model_id)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                               bnb_4bit_compute_dtype=dtype, bnb_4bit_use_double_quant=True)
    kwargs = dict(quantization_config=quant, device_map={"": 0})
    try:
        model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype, **kwargs)
    except TypeError:  # older transformers
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=dtype, **kwargs)
    model.eval()
    return model, tok


def _stop_ids(tok):
    ids = {tok.eos_token_id}
    for t in ("<|eot_id|>", "<|end_of_text|>"):
        i = tok.convert_tokens_to_ids(t)
        if isinstance(i, int) and i >= 0 and i != tok.unk_token_id:
            ids.add(i)
    return [i for i in ids if i is not None]


def generate(model, tok, conversations, max_new_tokens=120, batch_size=16, progress=None):
    """Greedy (deterministic) generation for a list of chat conversations."""
    import torch

    prompts = [tok.apply_chat_template(c, tokenize=False, add_generation_prompt=True) for c in conversations]
    order = sorted(range(len(prompts)), key=lambda i: len(prompts[i]))  # similar lengths batch together
    replies = [None] * len(prompts)
    tok.padding_side = "left"
    device = next(model.parameters()).device
    for start in range(0, len(order), batch_size):
        idx = order[start:start + batch_size]
        enc = tok([prompts[i] for i in idx], return_tensors="pt", padding=True, add_special_tokens=False).to(device)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False,
                                 pad_token_id=tok.pad_token_id, eos_token_id=_stop_ids(tok))
        for j, i in enumerate(idx):
            replies[i] = tok.decode(out[j, enc["input_ids"].shape[1]:], skip_special_tokens=True)
        if progress:
            progress(min(start + batch_size, len(order)), len(order))
    return replies


def evaluate(model, tok, scn, method="prompt", n=60, batch_size=16):
    """method: 'prompt', 'prompt+docs' (policy pasted into the prompt) or 'fine-tuned'."""
    rows = scn.test[:n]
    convs = [build_messages(scn, r["input"], include_policy=(method == "prompt+docs")) for r in rows]
    t0 = time.time()
    bar = _bar(len(rows), f"Testing ({method})")
    replies = generate(model, tok, convs, batch_size=batch_size, progress=lambda d, t: bar(d))
    bar(len(rows), finished=True)
    res = score(scn, rows, replies, method)
    res["summary"]["seconds"] = round(time.time() - t0)
    sample = [tok.apply_chat_template(c, tokenize=False, add_generation_prompt=True) for c in convs[:10]]
    res["summary"]["prompt tokens / request"] = round(
        sum(len(tok(p, add_special_tokens=False)["input_ids"]) for p in sample) / max(len(sample), 1))
    return res


def ask(model, tok, scn, text, include_policy=False):
    """Run the model on one piece of text you write yourself."""
    reply = generate(model, tok, [build_messages(scn, text, include_policy)], batch_size=1)[0]
    return parse_output(reply) or reply


# -------------------------------------------------------------- training ---

def _encode(tok, scn, row, max_len):
    msgs = build_messages(scn, row["input"], answer=answer_json(scn, row))
    prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
    full = tok.apply_chat_template(msgs, tokenize=False)
    if not full.startswith(prompt):
        full = prompt + msgs[-1]["content"] + (tok.eos_token or "")
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    a_ids = tok(full[len(prompt):], add_special_tokens=False)["input_ids"]
    ids = (p_ids + a_ids)[:max_len]
    labels = ([-100] * len(p_ids) + a_ids)[:max_len]  # only the answer is learned, not the prompt
    return ids, labels


def pick_training_rows(scn, n):
    """Indices of n training rows that cover every answer value at least a few times (rare rules such as
    "business class on a short flight" would otherwise barely appear in a small sample). Selection uses the
    clean labels, so clean and noisy runs train on exactly the same messages."""
    n = min(n, len(scn.train))
    floor = 5 if n >= 100 else 3 if n >= 50 else 1
    groups = {}
    for i, row in enumerate(scn.train):
        for f, opts in scn.choices.items():
            if opts:
                groups.setdefault((f, row[f]), []).append(i)
    chosen = []
    for _, idx in sorted(groups.items(), key=lambda kv: len(kv[1])):  # rarest values first
        have = sum(i in chosen for i in idx)
        for i in idx:
            if have >= floor or len(chosen) >= n:
                break
            if i not in chosen:
                chosen.append(i)
                have += 1
    chosen += [i for i in range(len(scn.train)) if i not in chosen][:n - len(chosen)]
    return sorted(chosen)


def train(model, tok, scn, n_examples=100, data="clean", epochs=2, learning_rate=2e-4, batch_size=4,
          lora_rank=16, max_len=768, seed=0, progress=None):
    """LoRA fine-tuning. Returns (model_with_adapter, list_of_losses).

    data: 'clean' (expert labels) or 'noisy' (30% of rows have one wrong label).
    Calling train() again starts over from the original model.
    progress: optional callback(step, total_steps, loss, seconds_left), called after every step. If it raises,
    training stops and the original model is left without an adapter.
    """
    import torch
    from peft import LoraConfig, PeftModel, get_peft_model

    if isinstance(model, PeftModel):
        model = model.unload()  # drop the previous adapter, keep the original weights
    pool = scn.train if data == "clean" else scn.train_noisy
    rows = [pool[i] for i in pick_training_rows(scn, n_examples)]  # same rows for clean and noisy
    rng = random.Random(seed)
    torch.manual_seed(seed)

    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model.config.use_cache = False
    lora = LoraConfig(r=lora_rank, lora_alpha=2 * lora_rank, lora_dropout=0.05, task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lora)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())

    encoded = [_encode(tok, scn, r, max_len) for r in rows]
    steps_per_epoch = math.ceil(len(encoded) / batch_size)
    total_steps = steps_per_epoch * epochs
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=learning_rate, weight_decay=0.0)
    warmup = max(1, total_steps // 10)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: (s + 1) / warmup if s < warmup else max(0.05, 0.5 * (1 + math.cos(math.pi * (s - warmup) / max(1, total_steps - warmup)))))

    device = next(model.parameters()).device
    use_amp = device.type == "cuda"
    amp_dtype = torch.bfloat16 if use_amp and torch.cuda.is_bf16_supported() else torch.float16
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp and amp_dtype == torch.float16)
    pad = tok.pad_token_id

    print(f"Training {trainable / 1e6:.1f}M of {total / 1e9:.1f}B parameters ({100 * trainable / total:.2f}%) "
          f"on {len(rows)} {data} examples for {epochs} epoch(s) = {total_steps} steps")
    model.train()
    losses, step, t0 = [], 0, time.time()
    bar = _bar(total_steps, "Fine-tuning")
    try:
        for _ in range(epochs):
            rng.shuffle(encoded)
            for b in range(0, len(encoded), batch_size):
                batch = encoded[b:b + batch_size]
                width = max(len(ids) for ids, _ in batch)
                input_ids = torch.tensor([ids + [pad] * (width - len(ids)) for ids, _ in batch], device=device)
                labels = torch.tensor([lab + [-100] * (width - len(lab)) for _, lab in batch], device=device)
                mask = torch.tensor([[1] * len(ids) + [0] * (width - len(ids)) for ids, _ in batch], device=device)
                with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=use_amp):
                    loss = model(input_ids=input_ids, attention_mask=mask, labels=labels).loss
                scaler.scale(loss).backward()
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                scaler.step(opt)
                scaler.update()
                opt.zero_grad(set_to_none=True)
                sched.step()
                losses.append(loss.item())
                step += 1
                eta = (time.time() - t0) / step * (total_steps - step)
                bar(step, extra=f"loss {loss.item():.3f} | ~{eta / 60:.1f} min left")
                if progress:
                    progress(step, total_steps, losses[-1], eta)
    except BaseException:  # stopped part-way: take the half-trained adapter off again
        base = model.unload()
        base.eval()
        base.config.use_cache = True
        raise
    bar(total_steps, finished=True, extra=f"done in {(time.time() - t0) / 60:.1f} min")
    model.eval()
    model.config.use_cache = True
    return model, losses


# ----------------------------------------------------- instructor dry run ---

# (examples, data, epochs). The student settings cards A-E plus two extra points for the learning curve.
CARDS = {"A": (25, "clean", 2), "B": (100, "clean", 2), "C": (300, "clean", 1), "D": (100, "noisy", 2),
         "E": (300, "noisy", 1)}
QUICK_SWEEP = [CARDS["B"], CARDS["D"]]
FULL_SWEEP = [CARDS["A"], (50, "clean", 2), CARDS["B"], (200, "clean", 2), CARDS["C"], CARDS["D"], CARDS["E"]]
SWEEP_COLUMNS = ["scenario", "method", "examples", "data", "epochs", "all_correct", "range_low", "range_high",
                 "valid_json", "prompt_tokens", "train_minutes", "eval_seconds", "final_loss", "per_field"]


def _base_model(model):
    """Context manager that switches any trained adapter off (the original model)."""
    from contextlib import nullcontext
    from peft import PeftModel
    return model.disable_adapter() if isinstance(model, PeftModel) else nullcontext()


def _sweep_row(scn, res, method, examples="", data="", epochs="", train_minutes="", final_loss=""):
    s = res["summary"]
    lo, hi = s["95% range"].rstrip("%").split("-")
    return {"scenario": scn.key, "method": method, "examples": examples, "data": data, "epochs": epochs,
            "all_correct": s["all fields correct %"], "range_low": int(lo), "range_high": int(hi),
            "valid_json": s["valid JSON %"], "prompt_tokens": s["prompt tokens / request"],
            "train_minutes": train_minutes, "eval_seconds": s["seconds"], "final_loss": final_loss,
            "per_field": json.dumps({k[:-2]: v for k, v in s.items() if k.endswith(" %") and k not in
                                     ("valid JSON %", "all fields correct %")})}


def sweep(model, tok, scenario_keys, settings, n_test=100, out_csv="dry_run_results.csv"):
    """Run baselines and fine-tuning settings for each scenario, appending one row per run to out_csv.
    Re-running skips anything already in the file, so a Colab disconnect loses at most one run."""
    out = Path(out_csv)
    done = []
    if out.exists():
        done = _read_csv(out)
    seen = {(r["scenario"], r["method"], str(r["examples"]), r["data"], str(r["epochs"])) for r in done}

    def save(row):
        new = not out.exists()
        with open(out, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=SWEEP_COLUMNS)
            if new:
                w.writeheader()
            w.writerow(row)
        done.append({k: str(v) for k, v in row.items()})
        seen.add((row["scenario"], row["method"], str(row["examples"]), row["data"], str(row["epochs"])))

    for key in scenario_keys:
        scn = load_scenario(key)
        for method in ("prompt", "prompt+docs"):
            if (key, method, "", "", "") in seen:
                continue
            print(f"\n=== {key}: {method}")
            with _base_model(model):
                res = evaluate(model, tok, scn, method, n=n_test)
            save(_sweep_row(scn, res, method))
        for n, data, epochs in settings:
            if (key, "fine-tuned", str(n), data, str(epochs)) in seen:
                continue
            print(f"\n=== {key}: fine-tune on {n} {data} examples x {epochs} epoch(s)")
            t0 = time.time()
            model, losses = train(model, tok, scn, n_examples=n, data=data, epochs=epochs)
            minutes = round((time.time() - t0) / 60, 1)
            res = evaluate(model, tok, scn, "fine-tuned", n=n_test)
            tail = losses[-5:]
            save(_sweep_row(scn, res, "fine-tuned", n, data, epochs, minutes, round(sum(tail) / len(tail), 4)))
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
    return model, done


def sweep_report(csv_path="dry_run_results.csv", plot=True):
    """Tables, learning curves and a recommended number of training examples per scenario."""
    import pandas as pd
    df = pd.read_csv(csv_path)
    df["setting"] = df.apply(lambda r: r["method"] if r["method"] != "fine-tuned"
                             else f"FT {int(r['examples'])} {r['data']} x{int(r['epochs'])}", axis=1)
    df["result"] = df.apply(lambda r: f"{r['all_correct']}% ({r['range_low']}-{r['range_high']})", axis=1)
    table = df.pivot_table(index="scenario", columns="setting", values="result", aggfunc="last")
    order = df.assign(_m=df.method.map({"prompt": 0, "prompt+docs": 1}).fillna(2), _d=(df.data == "noisy"),
                      _n=pd.to_numeric(df.examples, errors="coerce").fillna(0))
    order = order.sort_values(["_m", "_d", "_n"]).setting.drop_duplicates()
    table = table[[c for c in order if c in table.columns]]

    recs = []
    for key, g in df.groupby("scenario"):
        base, docs = g[g.method == "prompt"], g[g.method == "prompt+docs"]
        ft = g[(g.method == "fine-tuned") & (g.data == "clean")].sort_values("examples")
        base_hi = int(base.range_high.iloc[-1]) if len(base) else 100
        docs_hi = int(docs.range_high.iloc[-1]) if len(docs) else 100
        clear = ft[ft.range_low > base_hi]
        beats = ft[ft.range_low > docs_hi]
        recs.append({
            "scenario": key,
            "prompt": f"{base.all_correct.iloc[-1]}%" if len(base) else "-",
            "prompt+docs": f"{docs.all_correct.iloc[-1]}%" if len(docs) else "-",
            "fewest examples: clearly beats prompt": int(clear.examples.iloc[0]) if len(clear) else "not reached",
            "fewest examples: clearly beats prompt+docs": int(beats.examples.iloc[0]) if len(beats) else "not reached",
            "train minutes per 100 example-passes": round(
                (ft.train_minutes / (ft.examples * ft.epochs) * 100).median(), 1) if len(ft) else "-",
        })
    recs = pd.DataFrame(recs).set_index("scenario")

    if plot and len(df):
        import matplotlib.pyplot as plt
        keys = sorted(df.scenario.unique())
        fig, axes = plt.subplots(1, len(keys), figsize=(4 * len(keys), 3.4), squeeze=False, sharey=True)
        for ax, key in zip(axes[0], keys):
            g = df[df.scenario == key]
            for method, color in (("prompt", "#9aa5b1"), ("prompt+docs", "#5b8def")):
                m = g[g.method == method]
                if len(m):
                    ax.axhline(m.all_correct.iloc[-1], color=color, ls="--", label=method)
            for data, color in (("clean", "#1f9d55"), ("noisy", "#e07a2f")):
                m = g[(g.method == "fine-tuned") & (g.data == data)].sort_values("examples")
                if len(m):
                    ax.errorbar(m.examples, m.all_correct, yerr=[m.all_correct - m.range_low, m.range_high - m.all_correct],
                                color=color, marker="o", capsize=3, label=f"fine-tuned ({data})")
            ax.set_title(key, fontsize=10)
            ax.set_xscale("log")
            ax.minorticks_off()
            ax.set_xticks([25, 50, 100, 200, 300], ["25", "50", "100", "200", "300"])
            ax.set_xlabel("training examples")
            ax.set_ylim(0, 105)
            ax.spines[["top", "right"]].set_visible(False)
        axes[0][0].set_ylabel("all fields correct (%)")
        axes[0][-1].legend(fontsize=8, loc="lower right")
        plt.tight_layout()
        plt.show()
    return table, recs


# --------------------------------------------------------------- display ---

def _bar(total, label):
    """A one-line text progress bar that works in Colab and in a terminal."""
    def update(n, extra="", finished=False):
        filled = int(30 * n / max(total, 1))
        print(f"\r{label}: [{'#' * filled}{'.' * (30 - filled)}] {n}/{total} {extra}   ",
              end="\n" if finished else "", flush=True)
    return update


def compare(*results):
    """Side-by-side table of evaluation summaries."""
    import pandas as pd
    return pd.DataFrame([r["summary"] for r in results]).set_index("method")


def plot_compare(*results, title=""):
    import matplotlib.pyplot as plt
    labels = [r["summary"]["method"] for r in results]
    values = [r["summary"]["all fields correct %"] for r in results]
    fig, ax = plt.subplots(figsize=(6, 3.2))
    bars = ax.bar(labels, values, color=["#9aa5b1", "#5b8def", "#1f9d55", "#e07a2f"][:len(values)])
    ax.bar_label(bars, labels=[f"{v}%" for v in values])
    ax.set_ylim(0, 105)
    ax.set_ylabel("All fields correct (%)")
    ax.set_title(title or "Bringing company knowledge to the model")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.show()


def plot_loss(losses):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 2.8))
    ax.plot(losses, color="#1f9d55")
    ax.set_xlabel("training step")
    ax.set_ylabel("loss (lower = closer to the experts)")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.show()


def mistakes(result, k=5):
    """The first k test examples the model got wrong, with expert vs model answers."""
    import pandas as pd
    wrong = [r for r in result["rows"] if not r["all correct"]][:k]
    return pd.DataFrame(wrong).drop(columns=["id", "all correct"], errors="ignore")


def show_examples(rows, k=5):
    import pandas as pd
    return pd.DataFrame(rows[:k]).drop(columns=["id"], errors="ignore")


def scorecard(team, scn, settings, *results):
    """One line to paste into the class leaderboard."""
    parts = [f"team={team}", f"scenario={scn.key}"] + [f"{k}={v}" for k, v in settings.items()]
    parts += [f"{r['summary']['method']}={r['summary']['all fields correct %']}%" for r in results]
    line = " | ".join(parts)
    print(line)
    return line
