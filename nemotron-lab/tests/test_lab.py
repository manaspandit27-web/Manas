"""Checks the datasets, the scoring, and the full train/evaluate loop on a tiny stand-in model (CPU, no download).

Run from nemotron-lab/:  python -m pytest -q tests
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lab import core  # noqa: E402

SCENARIOS = [s["scenario"] for s in core.list_scenarios()]


def test_five_scenarios():
    assert len(SCENARIOS) == 5


@pytest.mark.parametrize("key", SCENARIOS)
def test_scenario_data(key):
    scn = core.load_scenario(key)
    assert len(scn.train) == len(scn.train_noisy) == 600 and len(scn.test) == 100
    assert not {r["input"] for r in scn.train} & {r["input"] for r in scn.test}
    assert all(r["input"].strip() for r in scn.train + scn.test)
    changed = sum(a != b for a, b in zip(scn.train, scn.train_noisy))
    assert 0.2 < changed / 600 < 0.4
    assert scn.policy and scn.case
    # every fixed-choice field shows its options in the prompt
    prompt = core.system_prompt(scn)
    for f, opts in scn.choices.items():
        assert f'"{f}"' in prompt
        if opts:
            assert all(o in prompt for o in opts)
    assert "Apply this company policy" in core.system_prompt(scn, include_policy=True)


def test_parse_and_score():
    assert core.parse_output('<think></think>Sure: {"a": "x", "B": 2} trailing') == {"a": "x", "b": 2}
    assert core.parse_output("no json here") is None
    assert core.parse_output('{"a": {"nested": 1}}') == {"a": {"nested": 1}}
    scn = core.load_scenario("invoice_intake")
    row = scn.test[0]
    perfect = core.answer_json(scn, row).replace(row["amount_usd"], "$" + row["amount_usd"])
    res = core.score(scn, [row, row], [perfect, "garbage"], "x")
    assert res["summary"]["all fields correct %"] == 50
    assert res["summary"]["valid JSON %"] == 50


def _tiny_model_and_tokenizer():
    from tokenizers import Tokenizer, models, pre_tokenizers, trainers, decoders
    from transformers import LlamaConfig, LlamaForCausalLM, PreTrainedTokenizerFast

    scn = core.load_scenario("airline_complaints")
    special = ["<|begin_of_text|>", "<|start_header_id|>", "<|end_header_id|>", "<|eot_id|>", "<|pad|>"]
    tk = Tokenizer(models.BPE())
    tk.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tk.decoder = decoders.ByteLevel()
    corpus = [core.system_prompt(scn)] + [r["input"] + core.answer_json(scn, r) for r in scn.train]
    tk.train_from_iterator(corpus, trainers.BpeTrainer(vocab_size=800, special_tokens=special,
                                                       initial_alphabet=pre_tokenizers.ByteLevel.alphabet()))
    tok = PreTrainedTokenizerFast(tokenizer_object=tk, bos_token="<|begin_of_text|>", eos_token="<|eot_id|>",
                                  pad_token="<|pad|>")
    tok.chat_template = (
        "{{ bos_token }}{% for m in messages %}<|start_header_id|>{{ m['role'] }}<|end_header_id|>\n\n"
        "{{ m['content'] }}<|eot_id|>{% endfor %}"
        "{% if add_generation_prompt %}<|start_header_id|>assistant<|end_header_id|>\n\n{% endif %}")
    cfg = LlamaConfig(vocab_size=len(tok), hidden_size=64, intermediate_size=128, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=1024,
                      pad_token_id=tok.pad_token_id, bos_token_id=tok.bos_token_id, eos_token_id=tok.eos_token_id)
    return scn, LlamaForCausalLM(cfg), tok


def test_train_and_evaluate_smoke():
    scn, model, tok = _tiny_model_and_tokenizer()
    base = core.evaluate(model, tok, scn, "prompt", n=4, batch_size=2)
    assert base["summary"]["examples"] == 4
    model, losses = core.train(model, tok, scn, n_examples=16, epochs=3, learning_rate=3e-3, batch_size=4, lora_rank=4)
    assert len(losses) == 12 and losses[-1] < losses[0]
    ft = core.evaluate(model, tok, scn, "fine-tuned", n=4, batch_size=2)
    assert set(ft["summary"]) >= {"all fields correct %", "valid JSON %", "seconds"}
    core.compare(base, ft)
    # retraining starts from the original model rather than stacking adapters
    model, _ = core.train(model, tok, scn, n_examples=4, epochs=1, batch_size=4, lora_rank=4)
    assert sum("lora_A" in n for n, _ in model.named_parameters()) == 2 * 7
    assert isinstance(core.ask(model, tok, scn, "My bag is lost"), (dict, str))
