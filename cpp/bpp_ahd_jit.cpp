// The amortized operator, with C++ as the emitted artifact.
//
// bpp_amortized.py emits Python and executes it. Here the operator emits C++,
// and the loop compiles it. That is the whole reason this file exists: when the
// artifact is compiled code, the middle layer of Algorithm 2 stops being a
// parser and becomes the compiler, and the diagnostic the repair prompt feeds
// back is a compiler error. For a reader who writes metaheuristics in C++, this
// is the realistic shape of automatic heuristic design.
//
// Three layers, same as everywhere else in the tutorial:
//   1. envelope and payload  — is there a candidate in this text?
//   2. compilation           — does it build, with the required signature?
//   3. a probe run           — does it return one score per bin?
//
// The candidate is compiled to a separate executable and invoked, rather than
// loaded into this process. A generated program that crashes or hangs then takes
// its own process down instead of this one, and that process boundary is the
// only isolation on offer here. It is thin: do not point a live model at this
// demo outside a container or a virtual machine.
//
// Build and run:  make jit && ./bin/bpp_ahd_jit
#include <array>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "semantic_turn.hpp"

using semantic_turn::Event;
using semantic_turn::LogEntry;
using semantic_turn::MockLLM;
using semantic_turn::Spec;

namespace {

bool g_show_diagnostics = false;

// The program each candidate is compiled into. The instances are the same three
// the Python demo uses, so the bin counts are comparable across the two.
const char* kHarness = R"CPP(
#include <cstdio>
#include <cstddef>
#include <vector>

%%PRIORITY%%

namespace {
const int kCap = 10;
const std::vector<std::vector<int>> kInstances = {
    {6, 8, 5, 2, 8, 2, 4, 5, 7, 7, 2, 2, 7},
    {5, 7, 3, 4, 5, 6, 7, 5, 2, 3, 7, 3},
    {2, 7, 8, 5, 5, 5, 7, 6, 3, 5, 4}};

int pack(const std::vector<int>& items) {
  std::vector<int> bins;  // remaining capacity of each open bin
  for (int item : items) {
    std::vector<std::size_t> feasible;
    std::vector<int> caps;
    for (std::size_t i = 0; i < bins.size(); ++i)
      if (bins[i] >= item) { feasible.push_back(i); caps.push_back(bins[i]); }
    if (feasible.empty()) { bins.push_back(kCap - item); continue; }
    std::vector<double> scores = priority(item, caps);
    // first maximum wins, written out rather than left to whatever the library
    // does, because the Python demo resolves the tie the same way
    std::size_t arg = 0;
    for (std::size_t k = 1; k < scores.size(); ++k)
      if (scores[k] > scores[arg]) arg = k;
    bins[feasible[arg]] -= item;
  }
  return static_cast<int>(bins.size());
}
}  // namespace

int main() {
  std::vector<double> probe = priority(3, std::vector<int>{7, 4});
  if (probe.size() != 2) { std::printf("INFEASIBLE\n"); return 1; }
  int total = 0;
  for (const auto& inst : kInstances) total += pack(inst);
  std::printf("%d\n", total);
  return 0;
}
)CPP";

std::string replace_once(std::string text, const std::string& what, const std::string& with) {
  const std::size_t at = text.find(what);
  if (at != std::string::npos) text.replace(at, what.size(), with);
  return text;
}

std::string run_capture(const std::string& cmd) {
  std::string out;
  std::array<char, 256> buf{};
  FILE* pipe = popen(cmd.c_str(), "r");
  if (!pipe) return out;
  while (std::fgets(buf.data(), static_cast<int>(buf.size()), pipe)) out += buf.data();
  pclose(pipe);
  return out;
}

std::string first_line(const std::string& text) {
  const std::size_t nl = text.find('\n');
  return nl == std::string::npos ? text : text.substr(0, nl);
}

// Layer 1: pull the payload out of the envelope.
std::string payload_of(const std::string& text) {
  const std::size_t open = text.find("CANDIDATE");
  const std::size_t close = text.find("END_CANDIDATE");
  if (open == std::string::npos || close == std::string::npos)
    throw std::invalid_argument("schema error: no CANDIDATE envelope");
  const std::size_t tag = text.find("payload:", open);
  if (tag == std::string::npos || tag > close)
    throw std::invalid_argument("syntax error: no payload");
  std::string code = text.substr(tag + 8, close - (tag + 8));
  const std::size_t b = code.find_first_not_of(" \t\r\n");
  const std::size_t e = code.find_last_not_of(" \t\r\n");
  if (b == std::string::npos) throw std::invalid_argument("syntax error: empty payload");
  return code.substr(b, e - b + 1);
}

// Layers 2 and 3: compile the candidate, then run its probe. Returns the path of
// the executable; throws with the compiler's own words when the build fails.
std::string compile_candidate(const std::string& code) {
  // One executable per candidate. Compiling every candidate to the same path
  // would leave each artifact pointing at whatever was built last, so the
  // incumbent would be re-evaluated as the newest program instead of its own.
  static int nth = 0;
  const std::string stem = "/tmp/semantic_turn_candidate_" + std::to_string(nth++);
  const std::string src = stem + ".cpp";
  const std::string bin = stem + ".bin";
  {
    std::ofstream out(src);
    if (!out) throw std::invalid_argument("syntax error: cannot write the candidate to disk");
    out << replace_once(kHarness, "%%PRIORITY%%", code);
  }
  const char* cxx = std::getenv("CXX");
  const std::string compiler = cxx && *cxx ? cxx : "c++";
  const std::string log = stem + ".log";
  const std::string cmd = compiler + " -std=c++17 -O2 -o " + bin + " " + src + " 2> " + log;
  if (std::system(cmd.c_str()) != 0) {
    std::ifstream in(log);
    std::string diagnostic((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    if (g_show_diagnostics) std::cerr << diagnostic;
    // the compiler's text is the diagnostic the repair prompt carries back; only
    // the fact that it failed is reproducible across compilers, so only that is
    // printed in the trace
    throw std::invalid_argument("compile error: " + first_line(diagnostic));
  }
  return bin;
}

int run_candidate(const std::string& bin) {
  const std::string out = run_capture(bin);
  if (out.rfind("INFEASIBLE", 0) == 0)
    throw std::invalid_argument("feasibility: priority must return one score per bin");
  return std::atoi(out.c_str());
}

int lower_bound_total() {
  const std::vector<std::vector<int>> instances = {
      {6, 8, 5, 2, 8, 2, 4, 5, 7, 7, 2, 2, 7},
      {5, 7, 3, 4, 5, 6, 7, 5, 2, 3, 7, 3},
      {2, 7, 8, 5, 5, 5, 7, 6, 3, 5, 4}};
  int total = 0;
  for (const auto& inst : instances) {
    int sum = 0;
    for (int x : inst) sum += x;
    total += (sum + 9) / 10;  // ceil(sum / capacity)
  }
  return total;
}

// The artifact travelling through the loop is the compiled program: its source,
// so it can be reported, and the path of the executable that evaluates it.
struct Heuristic {
  std::string source;
  std::string binary;
};

Spec<Heuristic> make_spec() {
  Spec<Heuristic> spec;
  spec.render = [](const Heuristic&, double score, const std::vector<LogEntry>&) {
    return "[context] online bin packing, capacity 10; artifact: a C++ "
           "std::vector<double> priority(int item, const std::vector<int>& bins).\n"
           "[conditioning] current best total bins = " + std::to_string(static_cast<int>(score)) +
           ".\n[instruction] Emit one improved priority function.\n"
           "[format] CANDIDATE envelope with code in the payload.";
  };
  spec.parse = [](const std::string& text) {
    const std::string code = payload_of(text);
    return Heuristic{code, compile_candidate(code)};
  };
  spec.feasible = [](const Heuristic& h) { run_candidate(h.binary); };
  spec.repair_prompt = [](const std::string& prompt, const std::string&, const std::string& err) {
    return prompt + "\n[repair] the previous program failed validation: " + err;
  };
  return spec;
}

const char* label(Event e) {
  switch (e) {
    case Event::Accepted: return "accepted";
    case Event::Rejected: return "rejected";
    default: return "invalid";
  }
}

}  // namespace

int main(int argc, char** argv) {
  for (int i = 1; i < argc; ++i)
    if (std::string(argv[i]) == "--show-diagnostics") g_show_diagnostics = true;

  const auto spec = make_spec();
  const std::string incumbent_text = semantic_turn::load_pool("bpp_cpp_incumbent.txt")[0];
  const Heuristic incumbent = spec.parse(incumbent_text);
  MockLLM llm(semantic_turn::load_pool("bpp_cpp_pool.txt"));

  const std::function<double(const Heuristic&)> evaluator = [](const Heuristic& h) {
    return static_cast<double>(run_candidate(h.binary));
  };
  const std::function<bool(const Heuristic&, double, const Heuristic&, double)> accept =
      [](const Heuristic&, double sc, const Heuristic&, double scur) { return sc < scur; };

  const int lb = lower_bound_total();
  const int start = static_cast<int>(evaluator(incumbent));
  std::printf("lower bound (total bins) = %d\n", lb);
  std::printf("first-fit start: total bins = %d  (gap %.1f%%)\n", start,
              100.0 * (start - lb) / lb);

  const auto out = semantic_turn::build_and_validate<Heuristic>(
      llm, evaluator, accept, incumbent, spec, /*budget=*/4, /*retries=*/1);

  for (const auto& e : out.log) {
    std::string kind = label(e.kind);
    kind.resize(8, ' ');
    if (e.kind == Event::Invalid)
      std::printf("  step %d: %s rejected by the compiler\n", e.step, kind.c_str());
    else
      std::printf("  step %d: %s %d\n", e.step, kind.c_str(), static_cast<int>(e.score));
  }
  std::printf("best heuristic: total bins = %d  (gap %.1f%%)\n", static_cast<int>(out.best_score),
              100.0 * (out.best_score - lb) / lb);
  return 0;
}
