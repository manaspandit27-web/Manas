"""Checks the projector chat: asking, reading the class's labelled files, fine-tuning on them, and the web server.

Run from nemotron-lab/:  python -m pytest -q tests
"""

import csv
import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lab import core, demo  # noqa: E402
from test_lab import _tiny_model_and_tokenizer  # noqa: E402


def _labelled(scn, n=24, wrong=()):
    """The blank examples file, filled in the way a student would (correctly, unless the row number is in `wrong`)."""
    truth = {r["id"]: r for r in scn.train}
    rows = list(csv.DictReader(io.StringIO(demo.blank_examples(scn, n))))
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0]))
    w.writeheader()
    for i, r in enumerate(rows):
        r.update({f: truth[r["id"]][f] for f in scn.fields})
        if i in wrong:
            r["priority"] = "P1" if r["priority"] != "P1" else "P3"
        w.writerow(r)
    return out.getvalue()


def _turns(engine):
    return [t for t in engine.state()["thread"] if t["kind"] == "turn"]


def test_ask_then_finetune_on_class_labels_then_ask_again(tmp_path):
    e = demo.Engine(demo.SimulatedBackend(speed=0))
    scn = e.scn()
    e.ask(scn.test[0]["input"])
    e.wait()
    e.ask("My bag is lost and I am a Gold member")
    e.wait()
    first, typed = _turns(e)
    assert first["status"] == "done" and first["mode"] == "base" and [f["name"] for f in first["fields"]] == list(scn.fields)

    opening = e.state()["scenario"]["opening"]  # the chat starts with the lab's own instruction, word for word
    assert core.system_prompt(scn).endswith(opening) and opening.startswith("You work at Skyward Airways.")
    e.clear()  # a fresh chat: the original model acknowledges the instruction, then the questions follow
    e.wait()
    hello = e.state()["thread"][0]
    assert hello["kind"] == "hello" and hello["status"] == "done" and hello["reply"]
    e.ask(first["text"])
    e.wait()
    e.ask(typed["text"])
    e.wait()

    with pytest.raises(ValueError):
        e.serve_model("tuned")  # nothing has been fine-tuned yet
    with pytest.raises(ValueError):
        e.finetune("class")     # and no labelled examples have been added

    e.add_examples([("anna.csv", _labelled(scn)), ("ben.csv", _labelled(scn))])
    assert e.state()["examples"] == {"count": 24, "files": 2, "skipped": 0, "problems": [], "min": demo.MIN_EXAMPLES}
    e.finetune("class", epochs=1)
    e.wait()
    assert e.error is None and e.training["status"] == "done"
    assert e.tuned()["n"] == 24 and e.tuned()["label_accuracy"] == 100
    assert e.serving == "base"  # switching the model is a separate step

    e.serve_model("tuned")
    e.ask_again()
    e.wait()
    turns = _turns(e)
    assert [t["mode"] for t in turns] == ["base", "base", "tuned", "tuned"]
    assert [t["text"] for t in turns[2:]] == [first["text"], typed["text"]]
    with pytest.raises(ValueError):
        e.ask_again()  # the fine-tuned model has now answered everything


def test_reading_the_files_students_send_back():
    scn = core.load_scenario("airline_complaints")
    good = _labelled(scn, 24)
    careless = _labelled(scn, 24, wrong={0})
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


def test_one_job_at_a_time_and_stopping():
    e = demo.Engine(demo.SimulatedBackend(speed=0.3))
    e.finetune("lab", n=100)
    with pytest.raises(demo.Busy):
        e.ask("hello")
    time.sleep(0.2)
    e.cancel()
    e.wait()
    assert e.training["status"] == "stopped" and e.tuned() is None and e.job is None
    e.backend.speed = 0
    e.ask("hello")
    e.wait()
    assert _turns(e)[0]["status"] == "done"


def test_real_backend_on_a_tiny_model():
    scn, model, tok = _tiny_model_and_tokenizer()
    e = demo.Engine(demo.ModelBackend(model, tok))
    e.greet()  # whatever the model says to the instruction alone is shown, unless it is empty or a JSON answer
    e.wait()
    assert e.error is None and all(x["status"] == "done" for x in e.state()["thread"])
    e.ask(scn.test[0]["input"])
    e.wait()
    assert e.error is None and _turns(e)[0]["status"] == "done"

    e.add_examples([("class.csv", _labelled(scn, 24))])
    e.finetune("class", epochs=1)
    e.wait()
    assert e.error is None and e.tuned()["n"] == 24 and len(e.training["losses"]) == 6
    assert sum("lora_A" in n for n, _ in e.backend.model.named_parameters()) == 2 * 7

    e.serve_model("tuned")
    e.ask_again()
    e.wait()
    assert e.error is None and [t["mode"] for t in _turns(e)] == ["base", "tuned"]
    e.serve_model("base")  # the original model still answers, with the adapter switched off
    e.ask("One more question")
    e.wait()
    assert e.error is None and _turns(e)[-1]["mode"] == "base"

    # stopping a fine-tune part-way leaves the original model, with no adapter on it
    e.finetune("lab", n=24, epochs=1)
    while not e.training.get("losses"):
        time.sleep(0.01)
    e.cancel()
    e.wait()
    assert e.training["status"] == "stopped" and e.tuned() is None and e.serving == "base"
    assert not any("lora" in n for n, _ in e.backend.model.named_parameters())
    e.ask("Still there?")
    e.wait()
    assert e.error is None and _turns(e)[-1]["status"] == "done"


def _call(port, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def test_web_server():
    e = demo.Engine(demo.SimulatedBackend(speed=0))
    server = demo.serve(e, port=0)
    port = server.server_address[1]
    try:
        status, page = _call(port, "/")
        assert status == 200 and b"Nemotron" in page
        status, blank = _call(port, "/examples.csv?n=24")
        assert status == 200 and len(list(csv.DictReader(io.StringIO(blank.decode())))) == 24

        assert _call(port, "/api/ask", {"text": "My bag is lost"})[0] == 200
        e.wait()
        assert _call(port, "/api/ask", {"text": "  "})[0] == 400
        assert _call(port, "/api/finetune", {"source": "class"})[0] == 400  # no examples yet
        status, body = _call(port, "/api/examples", {"files": [{"name": "class.csv", "text": _labelled(e.scn())}]})
        assert status == 200 and json.loads(body)["examples"]["count"] == 24
        assert _call(port, "/api/finetune", {"source": "class", "epochs": 1})[0] == 200
        e.wait()
        assert _call(port, "/api/serve", {"mode": "tuned"})[0] == 200
        state = json.loads(_call(port, "/api/state")[1])
        assert state["serving"] == "tuned" and state["tuned"]["n"] == 24 and state["thread"][0]["status"] == "done"
        assert _call(port, "/api/nothing", {})[0] == 404
    finally:
        server.shutdown()
