all: heidelberg.md

heidelberg.md: heidelberg.html
	# Proccessing inner html from https://www.crcna.org/welcome/beliefs/confessions/heidelberg-catechism
	pandoc $< --lua-filter=filters.lua -o $@

format:
	uvx black@26.3.1 *.py
	uvx uncomment .

clean:
	rm -rf __pycache__
