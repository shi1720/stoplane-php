# Literature and positioning record

Search and source inspection: 14 October 2026. This is a focused engineering literature review, not an exhaustive systematic review or proof of patent novelty.

Queries covered `PHP LLM streaming cancellation connection_aborted nginx buffering`, `PHP streaming cancellation session lock curl_multi`, `cancellation PHP-FPM session`, `cancellation FPM pool`, `streaming cancel session_write_close`, `LLM inference abandoned requests cancellation`, and `request cancellation inference paper`.

## Primary evidence and close work

| Source | Established fact / scope | Relationship to StopLane |
|---|---|---|
| [PHP session_write_close](https://www.php.net/manual/en/function.session-write-close.php) | Native sessions serialize access; early closure ends the active session | Early release is existing technique, not novelty |
| [FPM configuration](https://www.php.net/manual/en/install.fpm.configuration.php) | max_children limits simultaneous served requests | Worker capacity can delay control admission independently of locks |
| [PHP connection handling](https://www.php.net/manual/en/features.connection-handling.php) | Disconnect detection depends on output attempts | Browser abort and explicit control request need separate tests |
| [nginx FastCGI module](https://nginx.org/en/docs/http/ngx_http_fastcgi_module.html) | Buffering and client-abort directives | Main experiment disables buffering and keeps client stream open |
| [Azure bulkhead pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead) | Resource isolation contains interference, with cost | Control reservation is a bulkhead application |
| [libcurl multi interface](https://curl.se/libcurl/c/libcurl-multi.html) | Application-controlled asynchronous progression | Existing primitive for idle-time observation |
| [PHP curl_multi_select](https://www.php.net/manual/en/function.curl-multi-select.php) | Selectable wait with timeout and return semantics | Configuration timeout is not a wall-clock execution proof |
| [Symfony HTTP client](https://symfony.com/doc/current/http_client.html) | stream timeouts, timeout chunks and response.cancel() | Actual pinned comparison implements the same contract using mature library APIs |
| [Amp cancellation](https://amphp.org/amp) | Cooperative cancellation is a supported PHP abstraction | StopLane does not invent a cancellation abstraction |
| [Laravel session blocking](https://laravel.com/framework/docs/12.x/session) | Same-session concurrency is default; route blocking is optional | Native-session results cannot be called universal Laravel defects |
| [Triton request cancellation](https://github.com/triton-inference-server/server/blob/21ff65dc97b806b1107b54f3c342b89e7d377b26/docs/user_guide/request_cancellation.md) | Server/backend cancellation is distinct from client intent | Need evidence of provider termination |
| [vLLM AsyncLLMEngine](https://docs.vllm.ai/en/latest/api/vllm/engine/async_llm_engine/) | Abort API for inference request lifecycle | Illustrates provider-side control, not executed in this experiment |
| [PipeInfer](https://arxiv.org/abs/2407.11798), Butler et al., 2024 | Early cancellation of invalidated speculative inference | Different locus from PHP application control admission |
| [Request cancellation overhead benchmark](https://github.com/JohnScheuer/request-cancellation-overhead-bench/tree/f59bf97a283e7e74c793a62445a70896ddf9d101), De Souza, 2026 | Discrete-event cancellation strategies, resource recovery | Closely related motivation; StopLane executes the web stack and measures before publication |

## Contribution boundary

A composition of session release, worker isolation and timed observation cannot honestly be sold as an undiscovered primitive. The inspected sources did not contain this exact capacity-matched factorial PHP experiment, authenticated reference, raw-trace verification and Symfony replication. That is the contribution being proposed. No assertion that the entire topic is absent from prior work is made.

## Prior-paper separation

All top-level PDFs in the user's research directory were text-inspected for titles and abstracts, with closer reading of nearby streaming and cancellation work. In particular:

- PrefixCommit concerns irreversible action commit after streamed JSON previews; StopLane concerns scheduling and observation of explicit cancellation.
- TraceMask concerns literal redaction release frontiers; no redaction algorithm is proposed here.
- Winner Logs concerns counterfactual information lost by first-response cancellation; no counterfactual audit allocation is proposed here.
- UndoScope concerns effect-scoped compensation of committed changes; StopLane does not implement rollback or compensation.
- Before the Validator concerns numeric wire fidelity; no numeric-schema transport claim is reused.

## Practical and commercial positioning

The existing ecosystem already contains cancellation-capable clients and server abort APIs. The possible product opportunity is an integration test and observability layer for PHP gateways, rather than a replacement HTTP client. Chat stop buttons, report aborts, retrieval cancellation and abandoned remote calls are concrete uses. The tested resource is gateway occupancy and controlled provider duration; real GPU costs and customer willingness to pay would require further evidence. No market-size estimate or patentability claim is inferred.

## Venue fit

[PHP Tek 2027 CFP](https://sessionize.com/php-tek-2027/) asks for presentation ideas, developer level and prerequisites. It is a practitioner speaker call, not a peer-reviewed paper track. The form provides PHP, JS, AI, Laravel, DevOps and Other tracks; standard talks are 50 minutes and tutorials three hours. The paper is a supporting research artifact. Two practical proposals can teach the failure and the reproducible test procedure without claiming publication acceptance.
