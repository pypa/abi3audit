//! Precomputed information about CPython's limited API and stable ABI.
//!
//! This crate exposes a subset of the information available in [stable_abi.toml] as Rust data structures.
//!
//! [stable_abi.toml]: https://github.com/python/cpython/blob/main/Misc/stable_abi.toml

/// Represents a CPython version, e.g. `3.10`.
///
/// Only the major and minor versions are represented.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Version {
    major: u8,
    minor: u8,
}

/// Represents the stable ABI information for a function.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FunctionInfo {
    /// When this function was added to the stable ABI, as a CPython version.
    added: Version,
}

/// Represents the stable ABI information for an exported object.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DataInfo {
    /// When this data item was added to the stable ABI, as a CPython version.
    added: Version,
}

include!(concat!(env!("OUT_DIR"), "/codegen.rs"));

/// Returns the stable ABI information for the function with the given name, if it exists.
pub fn function(name: &str) -> Option<&'static FunctionInfo> {
    FUNCTIONS.get(name)
}

/// Returns the stable ABI information for the data item with the given name, if it exists.
pub fn data(name: &str) -> Option<&'static DataInfo> {
    DATAS.get(name)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Test that we code-generated FUNCTIONS as expected.
    #[test]
    fn test_functions() {
        let Some(func) = FUNCTIONS.get("PyLong_AsInt") else {
            panic!("PyLong_AsInt not found in FUNCTIONS");
        };

        assert_eq!(
            func.added,
            Version {
                major: 3,
                minor: 13
            }
        )
    }

    /// Test that we code-generated DATAS as expected.
    #[test]
    fn test_datas() {
        let Some(data) = DATAS.get("PyBool_Type") else {
            panic!("PyBool_Type not found in DATAS");
        };

        assert_eq!(data.added, Version { major: 3, minor: 2 })
    }

    /// Test that function() and data() work as expected.
    #[test]
    fn test_lookups() {
        for key in FUNCTIONS.keys() {
            assert!(function(key).is_some(), "function({key}) should be Some");
        }

        for key in DATAS.keys() {
            assert!(data(key).is_some(), "data({key}) should be Some");
        }
    }
}
