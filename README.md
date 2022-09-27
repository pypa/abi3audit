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

```console
$ pip install abi3audit
```

## Usage

You can run `abi3audit` as a standalone program, or via `python -m abi3audit`:

```console
abi3audit --help
python -m abi3audit --help
```

Top-level:

<!-- @begin-abi3audit-help@ -->
```
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

## Licensing

abi3audit is licensed under the MIT license.

abi3audit includes ASN.1 and Mach-O parsers generated from
definitions provided by the [Kaitai Struct](https://kaitai.io/) project.
These vendored parsers are licensed by the Kaitai Struct authors under the MIT
license.
