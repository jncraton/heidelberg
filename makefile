all: index.html

heidelberg.md: heidelberg.html
	# Proccessing inner html from https://www.crcna.org/welcome/beliefs/confessions/heidelberg-catechism
	pandoc $< --lua-filter=filters.lua -o $@

lint:
	uvx black@26.3.1 --check *.py

format:
	uvx black@26.3.1 *.py
	uvx uncomment .

test:
	python3 -m doctest *.py

index.html:
	uv run --with beautifulsoup4 --with markdown python3 build.py

heidelberg.epub: index.html
	pandoc $< -o $@

clean:
	rm -rf __pycache__
