abi3audit
========

<!--- @begin-badges@ --->
[![CI](https://github.com/trailofbits/abi3audit/actions/workflows/ci.yml/badge.svg)](https://github.com/trailofbits/abi3audit/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/abi3audit.svg)](https://pypi.org/project/abi3audit)
[![Packaging status](https://repology.org/badge/tiny-repos/python:abi3audit.svg)](https://repology.org/project/python:abi3audit/versions)
<!--- @end-badges@ --->

abi3audit scans Python extensions for `abi3` violations and inconsistencies.

It can scan individual (unpackaged) shared objects, packaged wheels, or entire
package version histories.

⚠️ This project is not ready for general-purpose use! ⚠️

## Installation

abi3audit is available via `pip`:

```bash
pip install abi3audit
```

## Usage

You can run `abi3audit` as a standalone program, or via `python -m abi3audit`:

```bash
abi3audit --help
python -m abi3audit --help
```

Top-level:

<!-- @begin-abi3audit-help@ -->
```console
usage: abi3audit [-h] [--debug] [-v] [-R] [-o OUTPUT] SPEC [SPEC ...]

Scans Python extensions for abi3 violations and inconsistencies

positional arguments:
  SPEC                  the files or other dependency specs to scan

options:
  -h, --help            show this help message and exit
  --debug               emit debug statements; this setting also overrides
                        `ABI3AUDIT_LOGLEVEL` and is equivalent to setting it
                        to `debug`
  -v, --verbose         give more output, including pretty-printed results for
                        each audit step
  -R, --report          generate a JSON report; uses --output
  -o OUTPUT, --output OUTPUT
                        the path to write the JSON report to (default: stdout)
```
<!-- @end-abi3audit-help@ -->

### Examples

Audit a single shared object, wheel, or PyPI package:

```bash
# audit a local copy of an abi3 extension
abi3audit procmaps.abi3.so

# audit a local copy of an abi3 wheel
abi3audit procmaps-0.5.0-cp36-abi3-manylinux2010_x86_64.whl

# audit every abi3 wheel for the package 'procmaps' on PyPI
abi3audit procmaps
```

Show additional detail (pretty tables and individual violations) while auditing:

```bash
abi3audit procmaps --verbose
```

yields:

```console
[17:59:46] 👎 procmaps:
           procmaps-0.5.0-cp36-abi3-manylinux2010_x86_64.whl: procmaps.abi3.so
           uses the Python 3.10 ABI, but is tagged for the Python 3.6 ABI
           ┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
           ┃ Symbol                  ┃ Version ┃
           ┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
           │ PyUnicode_AsUTF8AndSize │ 3.10    │
           └─────────────────────────┴─────────┘
[17:59:47] 💁 procmaps: 2 extensions scanned; 1 ABI version mismatches and 0
           ABI violations found
```

Generate a JSON report for each input:

```bash
abi3audit procmaps --report | python -m json.tool
```

yields:

```json
{
  "specs": {
    "procmaps": {
      "kind": "package",
      "package": {
        "procmaps-0.5.0-cp36-abi3-manylinux2010_x86_64.whl": [
          {
            "name": "procmaps.abi3.so",
            "result": {
              "is_abi3": true,
              "is_abi3_baseline_compatible": false,
              "baseline": "3.6",
              "computed": "3.10",
              "non_abi3_symbols": [],
              "future_abi3_objects": {
                "PyUnicode_AsUTF8AndSize": "3.10"
              }
            }
          }
        ],
        "procmaps-0.6.1-cp37-abi3-manylinux_2_5_x86_64.manylinux1_x86_64.whl": [
          {
            "name": "procmaps.abi3.so",
            "result": {
              "is_abi3": true,
              "is_abi3_baseline_compatible": true,
              "baseline": "3.7",
              "computed": "3.7",
              "non_abi3_symbols": [],
              "future_abi3_objects": {}
            }
          }
        ]
      }
    }
  }
}
```

## Licensing

abi3audit is licensed under the MIT license.

abi3audit includes ASN.1 and Mach-O parsers generated from
definitions provided by the [Kaitai Struct](https://kaitai.io/) project.
These vendored parsers are licensed by the Kaitai Struct authors under the MIT
license.
