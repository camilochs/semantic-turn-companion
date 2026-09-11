// Algorithm 1 of the tutorial, in C++.
//
// This is a translation of search.py and llm.py, not a second design. It exists
// for two reasons. One, most metaheuristic code is written in C++, and a reader
// who works there should be able to lift the loop without reading Python. Two,
// it is the strongest check in the repository: cpp/tsp_transient.cpp is compared
// against the same frozen output as tsp_transient.py, so if the two languages
// disagree, the algorithm as written in the paper is under-specified.
//
// Header-only, C++17, no third-party libraries.
#ifndef SEMANTIC_TURN_HPP
#define SEMANTIC_TURN_HPP

#include <fstream>
#include <functional>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace semantic_turn {

// ── the model ───────────────────────────────────────────────────────────────
// Deterministic stand-in for an LLM: it ignores the prompt and returns the next
// completion from a fixed pool, round robin. No RNG anywhere, so C++ and Python
// cannot drift through a different generator.
class MockLLM {
 public:
  explicit MockLLM(std::vector<std::string> pool) : pool_(std::move(pool)) {
    if (pool_.empty()) throw std::invalid_argument("MockLLM needs a non-empty completion pool");
  }
  std::string sample(const std::string& /*prompt*/) { return pool_[i_++ % pool_.size()]; }

 private:
  std::vector<std::string> pool_;
  std::size_t i_ = 0;
};

// Reads fixtures/<name>: the same file the Python demos read, so both languages
// sample exactly the same completions. Envelopes are separated by a line `---`.
inline std::vector<std::string> load_pool(const std::string& name) {
  const std::string candidates[] = {"fixtures/" + name, "../fixtures/" + name, name};
  std::ifstream in;
  for (const auto& path : candidates) {
    in.open(path);
    if (in.is_open()) break;
    in.clear();
  }
  if (!in.is_open()) throw std::runtime_error("cannot find fixtures/" + name);
  std::stringstream buf;
  buf << in.rdbuf();
  const std::string raw = buf.str();

  std::vector<std::string> pool;
  const std::string sep = "\n---\n";
  std::size_t start = 0;
  while (start <= raw.size()) {
    const std::size_t hit = raw.find(sep, start);
    std::string part = raw.substr(start, hit == std::string::npos ? std::string::npos : hit - start);
    const std::size_t b = part.find_first_not_of(" \t\r\n");
    const std::size_t e = part.find_last_not_of(" \t\r\n");
    if (b != std::string::npos) pool.push_back(part.substr(b, e - b + 1));
    if (hit == std::string::npos) break;
    start = hit + sep.size();
  }
  if (pool.empty()) throw std::runtime_error("no completions in fixtures/" + name);
  return pool;
}

// ── printing, so both languages produce the same bytes ──────────────────────
// Fixed precision, the counterpart of Python's f"{x:.3f}".
inline std::string fixed3(double x) {
  std::ostringstream os;
  os << std::fixed << std::setprecision(3) << x;
  return os.str();
}

// The counterpart of printing Python's round(x, 3): three decimals at most, one
// at least, trailing zeros dropped. 8.0 prints as "8.0", not as "8.000".
inline std::string rounded3(double x) {
  std::string s = fixed3(x);
  while (s.size() > 1 && s.back() == '0' && s[s.size() - 2] != '.') s.pop_back();
  return s;
}

// The counterpart of printing a Python list of ints: "[0, 1, 2]".
inline std::string as_list(const std::vector<int>& v) {
  std::ostringstream os;
  os << '[';
  for (std::size_t i = 0; i < v.size(); ++i) os << (i ? ", " : "") << v[i];
  os << ']';
  return os.str();
}

// ── the loop ────────────────────────────────────────────────────────────────
enum class Event { Accepted, Rejected, Invalid };

struct LogEntry {
  int step;
  Event kind;
  double score;        // meaningful for Accepted / Rejected
  std::string error;   // meaningful for Invalid
};

// A problem is plugged in through Spec, the same four functions as in Python:
// render, parse, feasible, repair_prompt. parse and feasible report a rejection
// by throwing std::invalid_argument, which is this language's version of the
// ValueError the Python validator raises.
template <class Artifact>
struct Spec {
  std::function<std::string(const Artifact&, double, const std::vector<LogEntry>&)> render;
  std::function<Artifact(const std::string&)> parse;
  std::function<void(const Artifact&)> feasible;
  std::function<std::string(const std::string&, const std::string&, const std::string&)> repair_prompt;
};

template <class Artifact>
struct Result {
  Artifact best;
  double best_score;
  std::vector<LogEntry> log;
};

// Keeps the incumbent the search walks (cur) apart from the best artifact ever
// seen (best), so the loop stays correct under an acceptance rule that may take
// a worsening move.
template <class Artifact>
Result<Artifact> build_and_validate(
    MockLLM& llm,
    const std::function<double(const Artifact&)>& evaluator,
    const std::function<bool(const Artifact&, double, const Artifact&, double)>& accept,
    const Artifact& incumbent, const Spec<Artifact>& spec,
    int budget, int retries, bool minimize = true) {
  Artifact cur = incumbent, best = incumbent;
  double best_score = evaluator(incumbent);
  std::vector<LogEntry> feedback, log;

  for (int t = 0; t < budget; ++t) {
    std::string prompt = spec.render(cur, evaluator(cur), feedback);
    bool ok = false;
    Artifact cand = cur;
    std::string err;

    for (int k = 0; k <= retries; ++k) {
      const std::string text = llm.sample(prompt);
      try {
        cand = spec.parse(text);   // schema and syntax
        spec.feasible(cand);       // domain feasibility
        ok = true;
        break;
      } catch (const std::invalid_argument& e) {
        err = e.what();
        prompt = spec.repair_prompt(prompt, text, err);
      }
    }
    if (!ok) {
      log.push_back({t, Event::Invalid, 0.0, err});
      feedback.push_back(log.back());
      continue;
    }

    const double score_c = evaluator(cand);
    if (accept(cand, score_c, cur, evaluator(cur))) {
      cur = cand;
      const bool better = minimize ? score_c < best_score : score_c > best_score;
      if (better) { best = cand; best_score = score_c; }
      log.push_back({t, Event::Accepted, score_c, ""});
    } else {
      log.push_back({t, Event::Rejected, score_c, ""});
    }
    feedback.push_back(log.back());
  }
  return {best, best_score, log};
}

}  // namespace semantic_turn

#endif  // SEMANTIC_TURN_HPP
