#!/usr/bin/env python3
"""Focused negative tests for the validation guards.

The guards exist because a stale literal already shifted every result once. A
guard that has only been observed to pass is not evidence. Each test here breaks
one input on purpose and requires the validator to refuse it.

Run:
  ~/data/venvs/sgk-mini/bin/python validation/test_guards.py
"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_annulus as va  # noqa: E402

CASE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "openfoam", "annulus_cyclic")
BENCH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "output", "hollow-cylinder.physical-case.json")

failures = []


def make_case(tmp):
    """Copy only the files the input guard reads."""
    os.makedirs(os.path.join(tmp, "system"))
    os.makedirs(os.path.join(tmp, "constant"))
    for rel in ("system/blockMeshDict", "constant/transportProperties",
                "constant/fvOptions", "case.json"):
        shutil.copy(os.path.join(CASE, rel), os.path.join(tmp, rel))
    return tmp


def replace(path, old, new):
    with open(path) as f:
        text = f.read()
    if old not in text:
        raise RuntimeError(f"test setup failed: {old!r} not found in {path}")
    with open(path, "w") as f:
        f.write(text.replace(old, new, 1))


def expect_rejected(name, mutate):
    tmp = tempfile.mkdtemp(prefix="sgk-guard-")
    try:
        make_case(tmp)
        mutate(tmp)
        try:
            va.check_inputs(tmp, BENCH, verbose=False)
        except SystemExit as exc:
            detail = str(exc).strip().splitlines()[0]
            print(f"PASS  {name}: {detail}")
            return
        failures.append(f"{name}: guard accepted the broken case")
        print(f"FAIL  {name}: guard accepted the broken case")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    if not os.path.isfile(BENCH):
        raise SystemExit(f"benchmark missing: {BENCH}")

    expect_rejected(
        "wrong Ri",
        lambda tmp: replace(os.path.join(tmp, "system", "blockMeshDict"),
                            "Ri          0.007999341770415122;",
                            "Ri          0.0081;"),
    )
    expect_rejected(
        "wrong length",
        lambda tmp: replace(os.path.join(tmp, "system", "blockMeshDict"),
                            "L           0.05;", "L           0.06;"),
    )
    expect_rejected(
        "wrong axial Ubar",
        lambda tmp: replace(os.path.join(tmp, "constant", "fvOptions"),
                            "Ubar            (0.00883932269380431 0 0);",
                            "Ubar            (0.009 0 0);"),
    )
    expect_rejected(
        "transverse Ubar component",
        lambda tmp: replace(os.path.join(tmp, "constant", "fvOptions"),
                            "Ubar            (0.00883932269380431 0 0);",
                            "Ubar            (0.00883932269380431 0.001 0);"),
    )
    expect_rejected(
        "wrong kinematic viscosity",
        lambda tmp: replace(os.path.join(tmp, "constant", "transportProperties"),
                            "nu              1e-06;", "nu              1.2e-06;"),
    )
    expect_rejected(
        "swapped case identity",
        lambda tmp: replace(os.path.join(tmp, "case.json"),
                            '"CaseId": "hollow-cylinder"',
                            '"CaseId": "some-other-case"'),
    )

    # Non-finite fields must not reach the tolerances.
    tmp = tempfile.mkdtemp(prefix="sgk-guard-")
    try:
        path = os.path.join(tmp, "U")
        with open(path, "w") as f:
            f.write(
                "FoamFile { class volVectorField; }\n"
                "internalField nonuniform List<vector> 2\n(\n(1 0 0)\n(nan 0 0)\n)\n;\n"
            )
        try:
            va.read_field(path)
        except SystemExit as exc:
            print(f"PASS  non-finite field: {str(exc).strip().splitlines()[0]}")
        else:
            failures.append("non-finite field: reader accepted NaN")
            print("FAIL  non-finite field: reader accepted NaN")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # Missing artifacts must be reported, not silently replaced.
    tmp = tempfile.mkdtemp(prefix="sgk-guard-")
    try:
        try:
            va.field_volumes(tmp, "1000")
        except SystemExit as exc:
            print(f"PASS  missing cell volumes: {str(exc).strip().splitlines()[0]}")
        else:
            failures.append("missing cell volumes: accepted")
            print("FAIL  missing cell volumes: accepted")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # A field left over from another mesh must be rejected. This is the stale
    # artifact case: the latest time directory is not evidence that it belongs
    # to the case in the dictionaries.
    tmp = tempfile.mkdtemp(prefix="sgk-guard-")
    try:
        os.makedirs(os.path.join(tmp, "1000"))
        with open(os.path.join(tmp, "1000", "C"), "w") as f:
            f.write(
                "FoamFile { class volVectorField; }\n"
                "internalField nonuniform List<vector> 2\n(\n(0 0 0.009)\n(0 0 0.0095)\n)\n;\n"
            )
        with open(os.path.join(tmp, "1000", "U"), "w") as f:
            f.write(
                "FoamFile { class volVectorField; }\n"
                "internalField nonuniform List<vector> 2\n(\n(1 0 0)\n(1 0 0)\n)\n;\n"
            )
        with open(os.path.join(tmp, "1000", "p"), "w") as f:
            f.write(
                "FoamFile { class volScalarField; }\n"
                "internalField nonuniform List<scalar> 2\n(\n0\n0\n)\n;\n"
            )
        meta, _ = va.check_inputs(CASE, BENCH, verbose=False)
        try:
            va.extract_profile(tmp, "1000", meta)
        except SystemExit as exc:
            print(f"PASS  stale field with the wrong cell count: "
                  f"{str(exc).strip().splitlines()[0]}")
        else:
            failures.append("stale field: accepted a field from another mesh")
            print("FAIL  stale field: accepted a field from another mesh")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} guard test(s) failed")
        return 1

    print("\nAll guard tests passed: every broken input was rejected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
