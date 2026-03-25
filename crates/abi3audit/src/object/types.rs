use std::path::PathBuf;

use abi3info::Version;

/// Represents an abi3-compatible shared object, i.e. a CPython extension module.
pub struct Object {
    /// The "source" of this shared object, i.e. the path of the wheel it came from.
    ///
    /// This will be `None` for shared objects that are loaded/analyzed directly.
    pub origin: Option<PathBuf>,

    /// The name of this shared object, i.e. its filename.
    ///
    /// This may or may not be a real path on the filesystem, depending on how this object was loaded.
    pub name: String,

    /// The minimum version of the stable ABI that this object is compatible with, as a CPython version.
    pub abi3_version: Version,

    /// The symbols referenced by this shared object.
    pub symbols: Vec<Symbol>,
}

/// Represents a symbol referenced by a shared object.
pub struct Symbol {
    /// The symbol's name.
    ///
    /// NOTE: This may not be the exact name as it appears in the object,
    /// due to platform-specific normalization. For example, on macOS,
    /// the symbol `Foo` will appear in the object as `_Foo`, but we represent
    /// it as `Foo` here for consistency with CPython's own ABI information.
    pub name: String,
    /// The symbol's visibility.
    pub visibility: Visibility,
}

/// A rough approximation of symbol visibility across different object file formats.
pub enum Visibility {
    Local,
    Global,
    Weak,
    Unknown,
}
