.PHONY: help install dev test clean build upload

help:
	@echo "MCN Development Commands:"
	@echo "  install     Install MCN for production use"
	@echo "  dev         Install MCN for development"
	@echo "  test        Run tests"
	@echo "  clean       Clean build artifacts"
	@echo "  build       Build distribution packages"
	@echo "  upload      Upload to PyPI"
	@echo "  run         Run MCN example"

install:
	pip install -e .

dev:
	pip install -e ".[dev]"
	pip install -r requirements.txt

test:
	python -m pytest test/ -v
	python run_mcn.py run examples/hello.mcn
	python run_mcn.py run examples/business.mcn

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

upload: build
	python -m twine upload dist/*

run:
	python run_mcn.py run examples/hello.mcn
