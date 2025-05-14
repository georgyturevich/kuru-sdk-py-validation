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

# Pip commands
pip-install-local-kuru:
	pip install ../kuru-sdk-py --no-cache-dir

pip-uninstall-kuru:
	pip uninstall kuru-sdk kuru-sdk-fork -y

pip-install-requirements:
	pip install -r requirements.txt --no-cache-dir

# Declare phony targets
.PHONY: lint-check lint-apply lint-black-check lint-black-apply lint-isort-check lint-isort-apply pip-install-local-kuru pip-uninstall-kuru pip-install-requirements