//! Audits Python extensions for abi3 violations and inconsistencies.
//!
//! This crate provides the core APIs for auditing Python extensions.

pub mod audit;
pub mod object;

#[cfg(test)]
mod tests {
    use super::*;
}
