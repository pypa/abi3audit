.PHONY: all
all:
	@echo "Run my targets individually"

.PHONY: update-abi3info
update-abi3info:
	curl -o crates/abi3info/data/stable_abi.toml https://raw.githubusercontent.com/python/cpython/main/Misc/stable_abi.toml
