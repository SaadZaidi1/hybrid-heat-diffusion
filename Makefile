.PHONY: all test clean
all:
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
	cmake --build build -j
test: all
	ctest --test-dir build --output-on-failure
	python3 scripts/verify.py --binary build/heat
clean:
	cmake -E rm -rf build
