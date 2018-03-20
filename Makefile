publish: README.rst setup.py
	python3 setup.py sdist
	twine upload dist/*

clear:
	rm -rf dist
	rm -rf QuLab.egg-info

README.rst: README.md
	pandoc -f markdown -t rst README.md -o README.rst
