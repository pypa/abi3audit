# abi3audit

<!--- @begin-badges@ --->
[![Tests](https://github.com/pypa/abi3audit/actions/workflows/tests.yml/badge.svg)](https://github.com/pypa/abi3audit/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/abi3audit.svg)](https://pypi.org/project/abi3audit)
[![Packaging status](https://repology.org/badge/tiny-repos/python:abi3audit.svg)](https://repology.org/project/python:abi3audit/versions)
<!--- @end-badges@ --->

*[Read the Trail of Bits blog post about how we find bugs with `abi3audit`!](https://blog.trailofbits.com/2022/11/15/python-wheels-abi-abi3audit/)*

`abi3audit` scans Python extensions for `abi3` violations and inconsistencies.

It can scan individual (unpackaged) shared objects, packaged wheels, or entire
package version histories.

![An animated demonstration of abi3audit in action](https://user-images.githubusercontent.com/3059210/194171233-a61a81d2-f2ed-4078-8988-903f996ba2e3.gif)

This project is maintained in part by [Trail of Bits](https://trailofbits.com).
This is not an official Trail of Bits product.

## Index

* [Motivation](#motivation)
* [Installation](#installation)
* [Usage](#usage)
  * [Examples](#examples)
* [Limitations](#limitations)
* [Licensing](#licensing)

## Motivation

CPython (the reference implementation of Python) defines a stable API and corresponding
ABI ("`abi3`"). In principle, any CPython extension can be built against this
API/ABI and will remain forward compatible with future minor versions of CPython.
In other words: if you build against the stable ABI for Python 3.5, your
extension should work without modification on Python 3.9.

The stable ABI simplifies packaging of CPython extensions, since the packager
only needs to build one `abi3` wheel that targets the minimum supported Python
version.

To signal that a Python wheel contains `abi3`-compatible extensions,
the Python packaging ecosystem uses the `abi3` wheel tag, e.g.:

```text
pyrage-1.0.1-cp37-abi3-manylinux_2_5_x86_64.manylinux1_x86_64.whl
```

Unfortunately, there is **no actual enforcement** of `abi3` compliance
in Python extensions at install or runtime: a wheel (or independent
shared object) that is tagged as `abi3` is assumed to be `abi3`, but
is not validated in any way.

To make matters worse, there is **no formal connection** between the flag
([`--py-limited-api`](https://setuptools.pypa.io/en/latest/userguide/ext_modules.html#setuptools.Extension))
that controls wheel tagging and the build macros
([`Py_LIMITED_API`](https://docs.python.org/3/c-api/stable.html#c.Py_LIMITED_API))
that actually lock a Python extension into a specific `abi3` version.

As a result: it is very easy to compile a Python extension for the wrong `abi3`
version, or to tag a Python wheel as `abi3` without actually compiling it
as `abi3`-compatible.

This has serious security and reliability implications: non-stable parts
of the CPython ABI can change between minor versions, resulting in crashes,
unpredictable behavior, or potentially exploitable memory corruption when
a Python extension incorrectly assumes the parameters of a function
or layout of a structure.

## Installation

`abi3audit` is available via `pip`:

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
usage: abi3audit [-h] [--debug] [-v] [-R] [-o OUTPUT] [-s] [-S]
                 [--assume-minimum-abi3 ASSUME_MINIMUM_ABI3]
                 SPEC [SPEC ...]

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
  -s, --summary         always output a summary even if there are no
                        violations/ABI version mismatches
  -S, --strict          fail the entire audit if an individual audit step
                        fails
  --assume-minimum-abi3 ASSUME_MINIMUM_ABI3
                        assumed abi3 version (3.x, with x>=2) if it cannot be
                        detected
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

## Limitations

`abi3audit` is a *best-effort* tool, with some of the same limitations as
[`auditwheel`](https://github.com/pypa/auditwheel). In particular:

* `abi3audit` cannot check for *dynamic* abi3 violations, such as an extension
  that calls [`dlsym(3)`](https://man7.org/linux/man-pages/man3/dlsym.3.html)
  to invoke a non-abi3 function at runtime.

* `abi3audit` can confirm the presence of abi3-compatible symbols, but does
  not have an exhaustive list of abi3-*incompatible* symbols. Instead, it looks
  for violations by looking for symbols that start with `Py_` or `_Py_` that
  are not in the abi3 compatibility list. This is *unlikely* to result in false
  positives, but *could* if an extension incorrectly uses those reserved
  prefixes.

* When auditing a "bare" shared object (e.g. `foo.abi3.so`), `abi3audit` cannot
  assume anything about the minimum *intended* abi3 version. Instead, it
  defaults to the lowest known abi3 version (`abi3-cp32`) and warns on any
  version mismatches (e.g., a symbol that was only stabilized in 3.6).
  This can result in false positives, so users are encouraged to audit entire
  wheels or packages instead (since they contain the sufficient metadata).

* `abi3audit` considers the abi3 version when a symbol was *stabilized*,
  not *introduced*. In other words: `abi3audit` will produce a warning
  when an `abi3-cp36` extension contains a function stabilized in 3.7, even
  if that function was introduced in 3.6. This is *not* a false positive
  (it is an ABI version mismatch), but it's *generally* not a source of bugs.

* `abi3audit` checks both the "local" and "external" symbols for each extension,
  for formats that support both. It does this to catch symbols that have been
  inlined, such as `_Py_DECREF`. However, if the extension's symbol table
  has been stripped, these may be missed.

## Licensing

`abi3audit` is licensed under the MIT license.

`abi3audit` includes ASN.1 and Mach-O parsers generated from
definitions provided by the [Kaitai Struct](https://kaitai.io/) project.
These vendored parsers are licensed by the Kaitai Struct authors under the MIT
license.
