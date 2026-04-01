#!/usr/bin/env python3

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

import sys
import json
import argparse
from pathlib import Path
from itertools import chain

INDENT_LENGTH = 4


def generate_filepaths(*path_strings):
    if not all((isinstance(p, str) for p in path_strings)):
        raise TypeError("expected all paths to be strings")
    paths = [Path(s) for s in path_strings]
    if not all(p.exists() for p in paths):
        raise FileNotFoundError("Path not found")
    globs = (p.glob("**/*.json") if p.is_dir() else [p] for p in paths)
    ret_obj = chain(*globs)
    return ret_obj


def print_json_error(path, error):
    print(file=sys.stderr)
    print(f"ERROR: {error.msg}", file=sys.stderr)
    print(f"File: {path}", file=sys.stderr)
    print(f"Location: line {error.lineno}, column {error.colno}", file=sys.stderr)
    print(file=sys.stderr)


def format_json(paths, check_only: bool = False):
    errors = {}
    for path in paths:
        try:
            with path.open("r") as file:
                orig_json = file.read()
            new_json = json.loads(orig_json)
            if json.dumps(new_json, indent=INDENT_LENGTH) != orig_json:
                print(f"{str(path)} does not match formatting rules")
                if not check_only:
                    with path.open("w") as file:
                        json.dump(new_json, file, indent=INDENT_LENGTH)
        except json.JSONDecodeError as e:
            errors[str(path)] = e
            print_json_error(path, e)
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "paths", nargs="+", help="paths with JSON files to be formatted"
    )
    parser.add_argument(
        "-c",
        "--check",
        action="store_true",
        help="Files will only be checked (read-only) if set",
    )
    args = parser.parse_args()

    errors = format_json(generate_filepaths(*args.paths), check_only=args.check)
    sys.exit(0 if not errors else 1)
