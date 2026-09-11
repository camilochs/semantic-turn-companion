// The traced iteration of the tutorial, in C++: a transient, numeric-conditioned
// operator that proposes a TSP tour directly.
//
// Line-for-line counterpart of tsp_transient.py, reading the same completions
// from fixtures/tsp_pool.txt and printing the same text. Both are compared
// against expected/tsp_transient.txt.
//
// Build and run:  make && ./bin/tsp_transient
#include <cmath>
#include <iostream>
#include <regex>
#include <string>
#include <vector>

#include "semantic_turn.hpp"

using semantic_turn::as_list;
using semantic_turn::Event;
using semantic_turn::fixed3;
using semantic_turn::LogEntry;
using semantic_turn::MockLLM;
using semantic_turn::rounded3;
using semantic_turn::Spec;
using Tour = std::vector<int>;

namespace {

// A vector, not a map: iteration order has to be the same in both languages, and
// an unordered container is the classic way to lose that without noticing.
const std::vector<std::pair<double, double>> kCoords = {{0, 0}, {1, 0}, {2, 0}, {2, 2}, {0, 2}};
const int kN = static_cast<int>(kCoords.size());

double tour_len(const Tour& t) {
  double total = 0.0;
  for (std::size_t i = 0; i < t.size(); ++i) {
    const auto& a = kCoords[t[i]];
    const auto& b = kCoords[t[(i + 1) % t.size()]];
    total += std::hypot(a.first - b.first, a.second - b.second);
  }
  return total;
}

// Layer 1 and 2 of Algorithm 2: the envelope, then the payload syntax.
Tour parse(const std::string& text) {
  std::smatch m;
  if (!std::regex_search(text, m, std::regex(R"(CANDIDATE([\s\S]*?)END_CANDIDATE)")))
    throw std::invalid_argument("schema error: no CANDIDATE envelope");
  const std::string body = m[1].str();
  std::smatch pm;
  if (!std::regex_search(body, pm, std::regex(R"(payload:\s*(\[[^\]]*\]))")))
    throw std::invalid_argument("syntax error: no payload list");
  std::string inner = pm[1].str();
  inner = inner.substr(1, inner.size() - 2);

  Tour tour;
  std::string tok;
  std::istringstream fields(inner);
  while (std::getline(fields, tok, ',')) {
    const std::size_t b = tok.find_first_not_of(" \t");
    if (b == std::string::npos) continue;
    try {
      tour.push_back(std::stoi(tok.substr(b)));
    } catch (const std::exception&) {
      throw std::invalid_argument("syntax error: payload is not a list of integers");
    }
  }
  return tour;
}

// Layer 3: domain feasibility. The diagnostic names the offending cities, because
// that text is what the repair prompt hands back to the model.
void feasible(const Tour& perm) {
  std::vector<int> sorted = perm;
  std::sort(sorted.begin(), sorted.end());
  std::vector<int> identity(kN);
  for (int i = 0; i < kN; ++i) identity[i] = i;
  if (sorted == identity) return;

  std::vector<int> missing, dup;
  for (int c = 0; c < kN; ++c) {
    const long count = std::count(perm.begin(), perm.end(), c);
    if (count == 0) missing.push_back(c);
    if (count > 1) dup.push_back(c);
  }
  throw std::invalid_argument("feasibility: city " + as_list(dup) + " duplicated, city " +
                              as_list(missing) + " missing");
}

Spec<Tour> make_spec() {
  Spec<Tour> spec;
  spec.render = [](const Tour& cur, double score, const std::vector<LogEntry>&) {
    std::vector<int> identity(kN);
    for (int i = 0; i < kN; ++i) identity[i] = i;
    return "[context] TSP toy instance; minimize Euclidean closed-tour length.\n"
           "[conditioning] R = permutation of " + as_list(identity) + " starting at 0; "
           "incumbent " + as_list(cur) + ", score " + fixed3(score) + ".\n"
           "[instruction] Emit one lower-length tour if possible.\n"
           "[format] Use the CANDIDATE envelope.";
  };
  spec.parse = parse;
  spec.feasible = feasible;
  spec.repair_prompt = [](const std::string& prompt, const std::string&, const std::string& err) {
    return prompt + "\n[repair] previous payload failed validation: " + err +
           ". Emit a corrected CANDIDATE.";
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

int main() {
  const Tour incumbent = {0, 2, 3, 4, 1};
  MockLLM llm(semantic_turn::load_pool("tsp_pool.txt"));

  const std::function<double(const Tour&)> evaluator = tour_len;
  const std::function<bool(const Tour&, double, const Tour&, double)> accept =
      [](const Tour&, double sc, const Tour&, double scur) { return sc < scur; };

  const auto out = semantic_turn::build_and_validate<Tour>(
      llm, evaluator, accept, incumbent, make_spec(), /*budget=*/3, /*retries=*/1);

  std::cout << "incumbent " << as_list(incumbent) << "  length " << fixed3(tour_len(incumbent))
            << "\n";
  for (const auto& e : out.log) {
    std::string kind = label(e.kind);
    kind.resize(8, ' ');  // the f"{kind:8s}" of the Python demo
    std::cout << "  step " << e.step << ": " << kind << " "
              << (e.kind == Event::Invalid ? e.error : rounded3(e.score)) << "\n";
  }
  std::cout << "best " << as_list(out.best) << "  length " << fixed3(out.best_score) << "\n";
  return 0;
}
