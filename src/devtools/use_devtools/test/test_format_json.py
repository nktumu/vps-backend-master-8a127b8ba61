# VERITAS: Copyright (c) 2022 Veritas Technologies LLC. All rights reserved.
#
# THIS SOFTWARE CONTAINS CONFIDENTIAL INFORMATION AND TRADE SECRETS OF VERITAS
# TECHNOLOGIES LLC.  USE, DISCLOSURE OR REPRODUCTION IS PROHIBITED WITHOUT THE
# PRIOR EXPRESS WRITTEN PERMISSION OF VERITAS TECHNOLOGIES LLC.
#
# The Licensed Software and Documentation are deemed to be commercial computer
# software as defined in FAR 12.212 and subject to restricted rights as defined
# in FAR Section 52.227-19 "Commercial Computer Software - Restricted Rights"
# and DFARS 227.7202, Rights in "Commercial Computer Software or Commercial
# Computer Software Documentation," as applicable, and any successor
# regulations, whether delivered by Veritas as on premises or hosted services.
# Any use, modification, reproduction release, performance, display or
# disclosure of the Licensed Software and Documentation by the U.S. Government
# shall be solely in accordance with the terms of this Agreement.
# Product version __version__

import json
import pathlib
import runpy
from sys import modules

import pytest

from use_devtools.format_json import format_json, generate_filepaths


NUM_GOOD_JSONS = 3
NUM_BAD_JSONS = 3


@pytest.fixture
def good_jsons():
    return (
        "{}",
        '{"valid":"json"}',
        '{"nested":\n{"dict":        "json",      "with":"whitespace"}}',
    )


@pytest.fixture
def expected_jsons():
    return (
        "{}",
        '{\n    "valid": "json"\n}',
        '{\n    "nested": {\n        "dict": "json",\n        "with": "whitespace"\n    }\n}',
    )


@pytest.fixture
def bad_jsons():
    return (
        "{/}",
        '{"invalid":}',
        '{"nested":\n{"dict":        "json",      "with":"errors"}',
    )


@pytest.fixture
def json_directory(tmp_path, good_jsons, bad_jsons):
    for dir, jsons, count in (
        ("good", good_jsons, NUM_GOOD_JSONS),
        ("bad", bad_jsons, NUM_BAD_JSONS),
    ):
        (tmp_path / dir).mkdir()
        for i in range(count):
            filepath = tmp_path / f"{dir}/{i}.json"
            filepath.write_text(jsons[i])
    return tmp_path


@pytest.fixture
def run_command_line(monkeypatch):
    def _run_command_line(args: list = []):
        module_name = "use_devtools.format_json"
        if module_name in modules:
            del modules[module_name]  # required for namespace warning

        monkeypatch.setattr("sys.argv", [module_name] + args)
        with pytest.raises(SystemExit) as exit:
            runpy.run_module(module_name, run_name="__main__")
        return exit.value.code

    return _run_command_line


def test_generate_filepaths_dir(tmp_path):
    paths = generate_filepaths("./json_data/", str(tmp_path))
    for p in paths:
        assert isinstance(p, pathlib.Path)


def test_generate_filepaths_file(tmp_path):
    file = tmp_path / "file.json"
    file.write_text("{}")
    paths = [*generate_filepaths(str(file))]
    assert len(paths) == 1


def test_generate_filepaths_negative(tmp_path):
    file = tmp_path / "missing_path"
    with pytest.raises(FileNotFoundError):
        generate_filepaths(str(file))


@pytest.mark.parametrize("index", range(NUM_GOOD_JSONS))
def test_valid_json(good_jsons, expected_jsons, index):
    loaded_json = json.loads(good_jsons[index])
    dumped_json = json.dumps(loaded_json, indent=4)
    assert isinstance(dumped_json, str)
    assert dumped_json == expected_jsons[index]


@pytest.mark.parametrize("index", range(NUM_BAD_JSONS))
def test_invalid_json(bad_jsons, index):
    with pytest.raises(json.JSONDecodeError):
        _ = json.loads(bad_jsons[index])


@pytest.mark.parametrize("check_only_str", ["check_only", ""])
def test_format_json_directory(
    json_directory, check_only_str, good_jsons, expected_jsons, bad_jsons
):
    check_only = True if check_only_str == "check_only" else False
    errors = format_json(generate_filepaths(str(json_directory)), check_only=check_only)
    for dir, jsons in (
        ("good", good_jsons if check_only else expected_jsons),
        ("bad", bad_jsons),
    ):
        for i, json_file in enumerate(jsons):
            filepath = json_directory / f"{dir}/{i}.json"
            with filepath.open("r") as file:
                assert file.read() == json_file
    assert len(errors) == len(bad_jsons)


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_main_help(run_command_line, capsys, flag):
    code = run_command_line([flag])
    assert code == 0
    captured_out = capsys.readouterr()
    assert captured_out.out.index("usage:") == 0
    assert captured_out.err == ""


def test_main_good_exit(run_command_line, capsys, json_directory):
    code = run_command_line([str(json_directory / "good")])
    assert code == 0
    assert capsys.readouterr().err == ""


def test_main_bad_exit(run_command_line, capsys, json_directory):
    code = run_command_line([str(json_directory / "bad")])
    assert code == 1
    assert capsys.readouterr().err.index("ERROR:")
