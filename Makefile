.PHONY: lint-check lint-apply lint-black-check lint-black-apply lint-isort-check lint-isort-apply

lint-check:
	./scripts/lint.sh

lint-apply:
	./scripts/lint.sh -a

lint-black-check:
	./scripts/lint.sh --only-black

lint-black-apply:
	./scripts/lint.sh --only-black -a

lint-isort-check:
	./scripts/lint.sh --only-isort

lint-isort-apply:
	./scripts/lint.sh --only-isort -a