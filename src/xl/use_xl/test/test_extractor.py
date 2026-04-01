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

import json
import io
import pathlib
from unittest.mock import patch
import sys

import pytest

try:
    from use_xl import extractor
except ImportError:
    pass

if sys.platform.startswith("linux"):
    pytest.skip("skipping non-linux tests", allow_module_level=True)


def test_extractor_current(the_book):
    result_stream = io.StringIO()
    extractor.parse_to_stream(the_book, result_stream)

    result_stream.seek(0)
    result = json.load(result_stream)

    expected = ["name", "inputs", "outputs"]
    for k in expected:
        assert k in result

    expected_inputs = ["timeframe", "safety", "slps", "workloads", "windows"]
    for k in expected_inputs:
        assert k in result["inputs"]


def test_extractor_parser_21(import_source_book):
    book = import_source_book["book"]
    nworkloads = import_source_book["nworkloads"]

    result_stream = io.StringIO()
    extractor.parse_to_stream(book, result_stream)

    result_stream.seek(0)
    result = json.load(result_stream)

    expected = ["name", "inputs", "outputs"]
    for k in expected:
        assert k in result

    expected_inputs = ["timeframe", "safety", "slps", "workloads", "windows"]
    for k in expected_inputs:
        assert k in result["inputs"]
    assert len(result["inputs"]["workloads"]) == nworkloads


def test_extractor_main():
    with patch("use_xl.extractor.parse_excel_files") as mock:
        extractor.main(["-o", "output-goes-here", "file1.xlsx", "file2.xlsx"])
        assert mock.called_with(
            [pathlib.Path("file1.xlsx"), pathlib.Path("file2.xlsx")],
            pathlib.Path("output-goes-here"),
        )

    with patch("use_xl.extractor.parse_excel_files") as mock:
        extractor.main(["file1.xlsx"])
        assert mock.called_with([pathlib.Path("file1.xlsx")], None)

    with pytest.raises(SystemExit):
        extractor.main(["file1.xlsx", "file2.xlsx"])
