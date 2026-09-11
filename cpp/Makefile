# Build the C++ demos. No third-party libraries, no build system beyond this file.
#
# The flags are part of the reproduction claim, not a preference: -ffast-math,
# -Ofast and -march=native all let the compiler contract floating-point
# operations, and then the tour length printed here stops matching the one
# printed by Python. Do not add them.
CXX ?= g++
CXXFLAGS = -std=c++17 -O2 -Wall -Wextra
BIN = bin

.PHONY: all clean jit

all: $(BIN)/tsp_transient

jit: $(BIN)/bpp_ahd_jit

$(BIN):
	mkdir -p $(BIN)

$(BIN)/tsp_transient: tsp_transient.cpp semantic_turn.hpp | $(BIN)
	$(CXX) $(CXXFLAGS) tsp_transient.cpp -o $@

$(BIN)/bpp_ahd_jit: bpp_ahd_jit.cpp semantic_turn.hpp | $(BIN)
	$(CXX) $(CXXFLAGS) bpp_ahd_jit.cpp -o $@

clean:
	rm -rf $(BIN)
