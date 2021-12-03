import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest

from lm_zoo.backends.python import DummyBackend
from lm_zoo.models import DummyModel


@pytest.fixture(scope="module")
def dummy_results():
    sentences = [
        "There is a house on the street .",
        "There is a street on the house .",
    ]

    ret = {}
    ret["tokenize"] = [s.split(" ") for s in sentences]
    ret["unkify"] = [[0 for tok in sentence] for sentence in ret["tokenize"]]
    return sentences, ret


@pytest.fixture(scope="function",
                params=[True, False])
def dummy_model_file(dummy_results, request):
    sentences, results = dummy_results
    lists_as_literals = request.param

    with TemporaryDirectory() as model_dir:
        model_json = {}

        for command, result in results.items():
            if isinstance(result, list):
                # token or unk list
                if lists_as_literals:
                    model_json[command] = result
                else:
                    command_result_path = Path(model_dir) / f"{command}.txt"
                    with command_result_path.open("w") as f:
                        f.write("\n".join(" ".join(str(x) for x in sent)
                                          for sent in result))
                    model_json[command] = str(command_result_path)
            else:
                # TODO
                pass

        model_json_path = Path(model_dir) / "model.json"
        with model_json_path.open("w") as model_f:
            json.dump(model_json, model_f)

        yield model_json_path


def test_dummy_model_file_backend(dummy_model_file, dummy_results):
    sentences, results = dummy_results
    model = DummyModel(dummy_model_file, sentences)
    backend = DummyBackend()

    for command, result in results.items():
        ret = getattr(backend, command)(model, sentences)
        if isinstance(ret, pd.DataFrame):
            pd.testing.assert_frame_equal(ret, result)
        else:
            assert ret == result


def test_dummy_no_unks(dummy_model_file, dummy_results):
    sentences, results = dummy_results
    model = DummyModel(dummy_model_file, sentences, no_unks=True)
    backend = DummyBackend()

    assert backend.unkify(model, sentences) == \
        [[0 for tok in sentence] for sentence in results["tokenize"]]
