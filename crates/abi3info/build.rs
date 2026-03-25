use std::io::Write as _;
use std::{collections::HashMap, env, path::Path};

#[derive(serde::Deserialize)]
struct StableAbi<'a> {
    #[serde(borrow, rename(deserialize = "function"))]
    functions: HashMap<&'a str, Function>,
    #[serde(borrow, rename(deserialize = "data"))]
    datas: HashMap<&'a str, Data>,
    // TODO(ww): Consider modeling consts (const) and structs (struct) as well.
}

#[derive(serde::Deserialize)]
struct Function {
    added: Version,
}

#[derive(serde::Deserialize)]
struct Data {
    added: Version,
}

struct Version {
    major: u8,
    minor: u8,
}

impl<'de> serde::Deserialize<'de> for Version {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        let parts = s.splitn(2, '.').collect::<Vec<_>>();
        if parts.len() != 2 {
            return Err(serde::de::Error::custom(format!(
                "invalid version string: {s}"
            )));
        }

        let major = parts[0]
            .parse::<u8>()
            .map_err(|e| serde::de::Error::custom(format!("invalid major version: {e}")))?;
        let minor = parts[1]
            .parse::<u8>()
            .map_err(|e| serde::de::Error::custom(format!("invalid minor version: {e}")))?;

        Ok(Version { major, minor })
    }
}

const FUNCTIONS_PROLOGUE: &str = "static FUNCTIONS: phf::Map<&'static str, FunctionInfo> = ";
const DATA_PROLOGUE: &str = "static DATAS: phf::Map<&'static str, DataInfo> = ";

fn main() {
    let manifest_dir = env::var("CARGO_MANIFEST_DIR").unwrap();

    let source = Path::new(&manifest_dir).join("data/stable_abi.toml");
    println!(
        "cargo::rerun-if-changed={source}",
        source = source.display()
    );

    let source = std::fs::read_to_string(&source).unwrap();

    let stable_abi = { toml::from_str::<StableAbi>(&source).unwrap() };

    // println!(
    //     "cargo:warning=loaded stable ABI data for {} functions and {} data items",
    //     stable_abi.functions.len(),
    //     stable_abi.datas.len()
    // );

    let path = Path::new(&env::var("OUT_DIR").unwrap()).join("codegen.rs");
    let mut output = std::fs::File::create(path).unwrap();

    {
        let mut builder = phf_codegen::Map::<&str>::new();
        for (name, function) in stable_abi.functions {
            builder.entry(
                &name,
                format!(
                    "FunctionInfo {{ added: Version {{ major: {}, minor: {} }} }}",
                    function.added.major, function.added.minor
                ),
            );
        }

        writeln!(output, "{}{};", FUNCTIONS_PROLOGUE, builder.build()).unwrap();
    }

    {
        let mut builder = phf_codegen::Map::<&str>::new();
        for (name, data) in stable_abi.datas {
            builder.entry(
                &name,
                format!(
                    "DataInfo {{ added: Version {{ major: {}, minor: {} }} }}",
                    data.added.major, data.added.minor
                ),
            );
        }

        writeln!(output, "{}{};", DATA_PROLOGUE, builder.build()).unwrap();
    }
}
