"""Checks the projector chat and the notebook steps around it: the examples file, reading the class's labels,
fine-tuning on them, switching model, and the web server.

Run from nemotron-lab/:  python -m pytest -q tests
"""

import csv
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lab import core, demo  # noqa: E402
from test_lab import _tiny_model_and_tokenizer  # noqa: E402

SCENARIOS = [s["scenario"] for s in core.list_scenarios()]


def _fill_in(scn, text, wrong=()):
    """An examples file, filled in the way a student would (correctly, unless the row number is in `wrong`)."""
    truth = {r["id"]: r for r in scn.train}
    rows = list(csv.DictReader(io.StringIO(text)))
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0]))
    w.writeheader()
    for i, r in enumerate(rows):
        r.update({f: truth[r["id"]][f] for f in scn.fields})
        if i in wrong:
            r["priority"] = "P1" if r["priority"] != "P1" else "P3"
        w.writerow(r)
    return out.getvalue()


def _turns(chat):
    return [t for t in chat.state()["thread"] if t["kind"] == "turn"]


@pytest.mark.parametrize("key", SCENARIOS)
def test_examples_file_to_hand_out(key):
    scn = core.load_scenario(key)
    path = core.SCENARIO_DIR / key / demo.EXAMPLES_FILE
    assert path.read_text(encoding="utf-8") == demo.blank_examples(scn)  # rebuild with: python -m lab.demo --write-examples
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
    assert len(rows) == 100 and list(rows[0]) == ["id", "input", *scn.fields]
    assert all(r["input"] and not any(r[f] for f in scn.fields) for r in rows)  # the messages, with nothing filled in
    assert not {r["input"] for r in rows} & {r["input"] for r in scn.test}       # none of them is a test question


def test_ask_then_finetune_in_the_notebook_then_ask_again(tmp_path, capsys):
    chat = demo.Chat(demo.SimulatedBackend(speed=0), "airline_complaints")
    scn = chat.scn
    opening = chat.state()["opening"]  # the chat starts with the lab's own instruction, word for word
    assert core.system_prompt(scn).endswith(opening) and opening.startswith("You work at Skyward Airways.")
    chat.greet()  # the original model acknowledges it
    chat.wait()
    hello = chat.state()["thread"][0]
    assert hello["kind"] == "hello" and hello["status"] == "done" and hello["reply"]

    chat.ask(scn.test[0]["input"])
    chat.wait()
    chat.ask("My bag is lost and I am a Gold member")
    chat.wait()
    first, typed = _turns(chat)
    assert first["status"] == "done" and first["model"] == "original"
    assert [f["name"] for f in first["fields"]] == list(scn.fields)

    with pytest.raises(ValueError):
        chat.serve("fine-tuned")  # nothing has been fine-tuned yet

    # the notebook's three steps: read the file the class filled in, fine-tune, switch model
    sent_back = tmp_path / "class_labels.csv"
    sent_back.write_text(_fill_in(scn, (core.SCENARIO_DIR / scn.key / demo.EXAMPLES_FILE).read_text()), encoding="utf-8")
    labelled = chat.read_labelled([sent_back])
    assert len(labelled) == 100 and "100 labelled examples from 1 file(s)" in capsys.readouterr().out
    losses = chat.finetune(labelled, epochs=1)
    assert len(losses) == 25 and chat.tuned["examples"] == 100 and chat.busy is None
    assert chat.serving == "original"  # switching the model is a separate step
    chat.serve("fine-tuned")
    assert "fine-tuned model" in capsys.readouterr().out and chat.state()["serving"] == "fine-tuned"

    chat.ask_again()
    chat.wait()
    turns = _turns(chat)
    assert [t["model"] for t in turns] == ["original", "original", "fine-tuned", "fine-tuned"]
    assert [t["text"] for t in turns[2:]] == [first["text"], typed["text"]]
    with pytest.raises(ValueError):
        chat.ask_again()  # the fine-tuned model has now answered everything
    with pytest.raises(ValueError):
        chat.finetune(labelled[:3])  # too few examples to train on


def test_reading_the_files_students_send_back():
    scn = core.load_scenario("airline_complaints")
    blank = demo.blank_examples(scn, 24)
    good, careless = _fill_in(scn, blank), _fill_in(scn, blank, wrong={0})
    rows, skipped, problems = demo.read_labelled(scn, [("a.csv", good), ("b.csv", good), ("c.csv", careless)])
    truth = {r["input"]: r for r in scn.train}
    assert len(rows) == 24 and not skipped and not problems
    assert all(r[f] == truth[r["input"]][f] for r in rows for f in scn.fields)  # two careful students outvote one

    # a spreadsheet export: semicolons, a byte-order mark, capitals and spaces, no message column, some gaps
    lines = list(csv.DictReader(io.StringIO(good)))
    sloppy = "﻿ID;Category;Priority;Route_To;Compensation\n"
    sloppy += f"{lines[0]['id']};{lines[0]['category'].upper()};{lines[0]['priority'].lower()};" \
              f"{lines[0]['route_to'].replace('_', ' ')};{lines[0]['compensation']}\n"
    sloppy += f"{lines[1]['id']};{lines[1]['category']};urgent;{lines[1]['route_to']};{lines[1]['compensation']}\n"  # not a real priority
    sloppy += f"{lines[2]['id']};;;;\n"  # never started: not counted as skipped
    rows, skipped, problems = demo.read_labelled(scn, [("sheet.csv", sloppy), ("notes.csv", "name,comment\nx,y\n")])
    assert len(rows) == 1 and rows[0]["input"] == lines[0]["input"] and rows[0]["route_to"] == lines[0]["route_to"]
    assert skipped == 1 and len(problems) == 1 and problems[0].startswith("notes.csv")

    chat = demo.Chat(demo.SimulatedBackend(speed=0), "airline_complaints")
    assert len(chat.read_labelled({"upload.csv": good.encode("utf-8")})) == 24  # what Colab's files.upload() returns


def test_real_backend_on_a_tiny_model():
    scn, model, tok = _tiny_model_and_tokenizer()
    chat = demo.Chat(demo.ModelBackend(model, tok), scn.key)
    chat.greet()  # whatever the model says to the instruction alone is shown, unless it is empty or a JSON answer
    chat.wait()
    assert chat.error is None and all(x["status"] == "done" for x in chat.state()["thread"])
    chat.ask(scn.test[0]["input"])
    chat.wait()
    assert chat.error is None and _turns(chat)[0]["status"] == "done"

    labelled = chat.read_labelled({"class.csv": _fill_in(scn, demo.blank_examples(scn, 24))})
    losses = chat.finetune(labelled, epochs=1)
    assert len(losses) == 6 and chat.tuned["examples"] == 24
    assert sum("lora_A" in n for n, _ in chat.backend.model.named_parameters()) == 2 * 7

    chat.serve("fine-tuned")
    chat.ask_again()
    chat.wait()
    assert chat.error is None and [t["model"] for t in _turns(chat)] == ["original", "fine-tuned"]
    chat.serve("original")  # the original model still answers, with the adapter switched off
    chat.ask("One more question")
    chat.wait()
    assert chat.error is None and _turns(chat)[-1]["model"] == "original" and _turns(chat)[-1]["status"] == "done"

    # fine-tuning again starts from the original model rather than stacking adapters
    chat.finetune(chat.lab_examples(8), epochs=1)
    assert chat.serving == "original" and chat.tuned["examples"] == 8
    assert sum("lora_A" in n for n, _ in chat.backend.model.named_parameters()) == 2 * 7

    # interrupting a fine-tune part-way leaves the original model, with no adapter on it
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt()
    real_bar, core._bar = core._bar, lambda total, label: interrupted
    try:
        with pytest.raises(KeyboardInterrupt):
            chat.finetune(chat.lab_examples(8), epochs=1)
    finally:
        core._bar = real_bar
    assert chat.busy is None and chat.tuned is None and chat.serving == "original"
    assert not any("lora" in n for n, _ in chat.backend.model.named_parameters())
    chat.ask("Still there?")
    chat.wait()
    assert chat.error is None and _turns(chat)[-1]["status"] == "done"


def _call(port, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def test_web_server():
    chat = demo.Chat(demo.SimulatedBackend(speed=0), "airline_complaints")
    server = demo.serve(chat, port=0)
    port = server.server_address[1]
    try:
        status, page = _call(port, "/")
        assert status == 200 and b"Nemotron" in page
        assert _call(port, "/api/ask", {"text": "My bag is lost"})[0] == 200
        chat.wait()
        assert _call(port, "/api/ask", {"text": "  "})[0] == 400
        chat.busy = "fine-tuning"  # while the notebook is training, the page cannot ask
        assert _call(port, "/api/ask", {"text": "Hello?"})[0] == 409
        chat.busy = None
        chat.finetune(chat.lab_examples(8), epochs=1)
        chat.serve("fine-tuned")
        assert _call(port, "/api/again", {})[0] == 200
        chat.wait()
        state = json.loads(_call(port, "/api/state")[1])
        assert state["serving"] == "fine-tuned" and [t["model"] for t in state["thread"] if t["kind"] == "turn"] == ["original", "fine-tuned"]
        assert _call(port, "/api/finetune", {})[0] == 404  # fine-tuning is not something the page can do
    finally:
        server.shutdown()
