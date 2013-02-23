all: home.png

clean:
	rm -f home.png

%.png: %.dot
	dot -T png -o $@ $<

%.dot: ../config/%.dfa
	./dfa.py dot $<
