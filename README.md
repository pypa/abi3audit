abi3audit
========

[![CI](https://github.com/woodruffw/abi3audit/actions/workflows/ci.yml/badge.svg)](https://github.com/woodruffw/abi3audit/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/abi3audit.svg)](https://pypi.org/project/abi3audit)
[![Packaging status](https://repology.org/badge/tiny-repos/python:abi3audit.svg)](https://repology.org/project/python:abi3audit/versions)

abi3audit scans Python wheels (and unpackaged native extensions) for
`abi3` violations and inconsistencies.

⚠️ This project is not ready for general-purpose use! ⚠️

## Installation

abi3audit is available via `pip`:

```console
$ pip install abi3audit
```

## Usage

### Examples

## Licensing

abi3audit is licensed under the MIT license.

abi3audit includes ASN.1 and Mach-O parsers generated from
definitions provided by the [Kaitai Struct](https://kaitai.io/) project.
These vendored parsers are licensed by the Kaitai Struct authors under the MIT
license.
