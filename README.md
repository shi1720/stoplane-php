# StopLane: PHP cancellation admission benchmark

A reproducible study of why an explicit stop request can fail to stop a PHP streaming gateway promptly. The artifact measures the interaction of native session locks, PHP-FPM worker admission and polling during upstream silence. It compares direct libcurl with an existing Symfony HttpClient implementation.

The mechanisms are established. The contribution is the composed deployment contract, capacity-matched factorial experiment, complete event traces and independent verification. This is a research reference bound to loopback, not a ready-to-expose production API.

**Paper:** `paper/manuscript.pdf` (Shivam Gupta, 14 October 2026).

## What is actually executed

Client HTTP -> nginx -> FastCGI -> PHP-FPM -> controlled HTTP/SSE provider. The provider executes a timed loop; no LLM or GPU is used. Its loop iterations are synthetic work ticks, never tokens or billable computation. Closing the gateway transport and ending provider work are measured separately.

- Shared dispatch: three FPM workers serving streams and cancellation.
- Isolated dispatch: two stream workers plus one cancellation worker.
- Both have three dispatch workers. The harness keeps both configurations resident under one master, but exercises one route at a time. It does not compare resident memory.
- Cancellation uses an authenticated native session, POST, CSRF token, owner binding and a generation-specific monotone marker.
- Browser stream stays open during explicit cancellation; this is not a browser-disconnect benchmark.

## Reproduce

Requirements: Python >=3.9, PHP >=8.4 with curl, PHP-FPM and nginx. Exact recorded versions are in `results/environment.json`. No globally registered service is started. The runner chooses loopback ports, creates private temporary state and stops its own processes on normal exit or interruption.

On macOS, binaries can be installed with `brew install php@8.4 nginx`; the runner finds standard Homebrew paths. On other systems use explicit paths:

```sh
export PHP_BIN=/path/to/php
export FPM_BIN=/path/to/php-fpm
export NGINX_BIN=/path/to/nginx
python3 bench/run.py --repeats 10
python3 bench/verify.py
```

`run.py` replaces `results/raw.jsonl`; preserve the published file if comparing a rerun. The frozen primary implementation is Git commit `b685e41`. The main protocol in `PROTOCOL.md` was frozen locally before main collection, after exploratory pilot runs. It was not externally preregistered. The final gateway additionally returns HTTP 503 if marker publication fails; the successful-publication path used in measured trials is unchanged. An authorization test injects a publication failure and checks that it is not acknowledged.

The complete run has 320 factorial trials and 60 secondary controls. Run time is roughly 10-15 minutes, depending on the host. To smoke-test without replacing published data:

```sh
python3 bench/run.py --repeats 1 --out results/smoke.jsonl
```

For the pinned Symfony comparison, install the exact locked dependencies and run:

```sh
composer install --no-interaction
python3 bench/library.py
python3 bench/test_authorization.py
```

`composer.lock` pins Symfony HttpClient v8.1.9 and all transitive dependencies. The library extension is separate from primary collection. It runs forty new trials: ten each of fully enabled Symfony, Symfony without release, Symfony without reservation, and fully enabled direct cURL.

For figures and manuscript:

```sh
python3 -m pip install -r requirements-analysis.txt
python3 bench/analyze.py
python3 bench/report.py
cd paper
tectonic manuscript.tex
```

Analysis is offline. The paper macros and tables come from the retained raw data. `bench/verify.py` imports neither the runner nor the analysis code, independently reconstructs reported intervals and checks all cells. The CI workflow checks the retained corpus and PHP syntax; it does not rerun the live stack.

## Files

| Path | Purpose |
|---|---|
| `src/gateway.php` | Small native-session/cURL reference with three ablation controls |
| `src/symfony_gateway.php` | Same authentication and dispatch contract, existing Symfony client |
| `bench/provider.py` | Controlled regular, silent and noncooperative upstream |
| `bench/run.py` | Loopback stack management, randomized factorial, complete traces |
| `bench/library.py` | Pinned library replication |
| `bench/test_authorization.py` | Ownership, CSRF, repeat and generation-isolation tests |
| `bench/verify.py` | Independent raw-corpus and prediction consistency checks |
| `bench/analyze.py`, `bench/report.py` | Scientific figures, tables and exact manuscript macros |
| `results/` | Raw traces, environment, digests and checks |
| `paper/` | LaTeX manuscript, data-generated includes and rendered PDF |
| `figures/` | Vector scientific figures and readable PNG previews |
| `PROTOCOL.md` | Frozen primary design plus separately specified extension |
| `LITERATURE.md` | Primary sources, nearby research and novelty boundary |

## Deployment interpretation

Session release does not reserve a worker. Reserving a worker does not release a held session lock. Polling between chunks does not guarantee an observation opportunity during silence. The configured select timeout is not itself a hard wall-clock bound. Blocking callbacks, DNS, storage, control storms and scheduling can invalidate bounds on actual check intervals.

For Laravel, inspect middleware and optional route blocking: Laravel's documented default allows same-session concurrency. Native file-session results cannot be transferred to every framework.

Provider cooperation is required to interpret local transport teardown as reduced upstream work. No token billing, GPU memory, throughput, production p99, patentability or market-adoption claim is supported by this artifact. A distributed state store must preserve scope, monotonic markers, visibility and record retention; this implementation tests a private single-host directory.

## Licensing and citation

Reference code is MIT licensed. Use `CITATION.cff` to cite the artifact. Sources and prior techniques are credited in the manuscript. Paper copyright: Shivam Gupta, 2026.
