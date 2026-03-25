//! Routines for extracting symbol information from shared objects.

use std::vec;

use goblin::mach::symbols;

use crate::object::types::{Symbol, Visibility};

#[derive(thiserror::Error, Debug)]
pub enum ExtractError {
    #[error("Failed to parse object file")]
    Malformed(#[from] goblin::error::Error),

    #[error("Unsupported object file format: not an ELF, PE, or Mach-O file")]
    UnknownFormat,
}

fn extract_elf(elf: goblin::elf::Elf<'_>) -> Result<Vec<Symbol>, ExtractError> {
    fn visibility(sym: &goblin::elf::sym::Sym) -> Visibility {
        match sym.st_bind() {
            goblin::elf::sym::STB_LOCAL => Visibility::Local,
            goblin::elf::sym::STB_GLOBAL => Visibility::Global,
            goblin::elf::sym::STB_WEAK => Visibility::Weak,
            _ => Visibility::Unknown,
        }
    }

    // The dynamic linker on Linux uses .dynsym, not .symtab, for
    // link editing and relocation. However, an extension that was
    // compiled as non-abi3 might have CPython functions inlined into
    // it, and we'd like to detect those. As such, we scan both symbol
    // tables.
    Ok(elf
        .syms
        .iter()
        .filter_map(|sym| match sym.st_type() {
            goblin::elf::sym::STT_FUNC | goblin::elf::sym::STT_OBJECT => {
                let Some(name) = elf.strtab.get_at(sym.st_name) else {
                    // A symbol might not have a name, in which case there's no
                    // meaningful audit to perform on it (since all abi3 symbols are named).
                    // TODO(ww): Trace logging here?
                    return None;
                };

                Some(Symbol {
                    name: name.to_string(),
                    visibility: visibility(&sym),
                })
            }
            _ => None,
        })
        .chain(elf.dynsyms.iter().filter_map(|sym| {
            match sym.st_type() {
                goblin::elf::sym::STT_FUNC | goblin::elf::sym::STT_OBJECT => {
                    let Some(name) = elf.dynstrtab.get_at(sym.st_name) else {
                        // A symbol might not have a name, in which case there's no
                        // meaningful audit to perform on it (since all abi3 symbols are named).
                        // TODO(ww): Trace logging here?
                        return None;
                    };

                    Some(Symbol {
                        name: name.to_string(),
                        visibility: visibility(&sym),
                    })
                }
                _ => None,
            }
        }))
        .collect())
}

fn extract_pe(pe: goblin::pe::PE<'_>) -> Result<Vec<Symbol>, ExtractError> {
    Ok(pe
        .imports
        .iter()
        .map(|import| Symbol {
            name: import.name.to_string(),
            visibility: Visibility::Global,
        })
        .collect())
}

fn extract_macho(mach: goblin::mach::Mach<'_>) -> Result<Vec<Symbol>, ExtractError> {
    // Our top-level "Mach-O" file might actually be a fat binary containing multiple Mach-Os.
    let mut machos = vec![];
    match mach {
        goblin::mach::Mach::Binary(macho) => machos.push(macho),
        goblin::mach::Mach::Fat(fat) => {
            for arch in fat.into_iter() {
                let arch = arch?;
                if let goblin::mach::SingleArch::MachO(macho) = arch {
                    machos.push(macho);
                }
            }
        }
    };

    let mut symbols = vec![];
    for macho in machos {
        for sym in macho.symbols() {
            let (name, nlist) = sym?;

            // TODO(ww): Is this right?
            let visibility = if nlist.is_global() {
                Visibility::Global
            } else {
                Visibility::Local
            };

            symbols.push(Symbol {
                name: name.to_string(),
                visibility,
            });
        }
    }

    Ok(symbols)
}

pub fn extract(data: &[u8]) -> Result<Vec<Symbol>, ExtractError> {
    match goblin::Object::parse(data)? {
        goblin::Object::Elf(elf) => extract_elf(elf),
        goblin::Object::PE(pe) => extract_pe(pe),
        goblin::Object::Mach(mach) => extract_macho(mach),
        _ => Err(ExtractError::UnknownFormat),
    }
}
