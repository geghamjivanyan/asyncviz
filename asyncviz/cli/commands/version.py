"""``asyncviz version`` — print the package + build identity."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from asyncviz.cli.exit_codes import ExitCode
from asyncviz.packaging import get_package_metadata


def run(args: argparse.Namespace, **_: object) -> int:
    metadata = get_package_metadata()
    if getattr(args, "emit_json", False):
        payload = {
            "name": metadata.name,
            "version": metadata.version,
            "summary": metadata.summary,
            "requires_python": metadata.requires_python,
            "is_editable": metadata.is_editable,
            "build_identity": asdict(metadata.build_identity),
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return int(ExitCode.OK)

    bi = metadata.build_identity
    print(f"asyncviz {metadata.version}")
    print(f"channel: {bi.channel}")
    if bi.commit:
        print(f"commit:  {bi.commit}")
    if bi.timestamp:
        print(f"built:   {bi.timestamp}")
    if bi.frontend_version:
        print(f"frontend: {bi.frontend_version}")
    return int(ExitCode.OK)
