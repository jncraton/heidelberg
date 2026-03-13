all: heidelberg.md

heidelberg.md: heidelberg.html
	# Proccessing inner html from https://www.crcna.org/welcome/beliefs/confessions/heidelberg-catechism
	pandoc $< --lua-filter=filters.lua -o $@
