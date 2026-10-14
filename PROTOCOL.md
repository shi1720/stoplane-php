# StopLane experiment protocol

Frozen before the main result collection, 14 October 2026. Pilot trials are exploratory and are not included in the paper's primary estimates.

## Questions

1. Does early session release suffice to admit cancellation when the ordinary FPM pool is saturated?
2. Does reserving cancellation capacity suffice when the target retains the native session lock?
3. Does callback-only cancellation remain responsive during an upstream silence?
4. Does gateway transport teardown establish provider work termination?

## Design

Full factorial: release native file-session lock (false/true), reserve cancellation worker (false/true), timer-driven polling (false/true), offered concurrent streams (2/3), upstream shape (regular/silent). Ten randomized blocks, each containing all 32 cells; Python RNG seed 1720406. Total primary trials: 320. No dropped or retried primary trials. A failed readiness barrier invalidates a run and is reported, not silently replaced.

Each route has three dispatch workers: shared = three general-purpose workers; isolated = two data workers plus one control worker. Both configurations are resident as idle pools under one FPM master; only one route configuration is exercised per trial. No memory comparison is made. Under three offered streams, the isolated route deliberately queues the third stream. This is the capacity cost of reservation.

The target starts before other streams. Cancellation is requested 120 ms after the expected number of upstream requests is active. IDs and native sessions are distinct across streams; cancel uses the target's authenticated session and CSRF token. The provider runs for 1.4 seconds. Regular output emits at roughly 20 ms intervals; silent output withholds body output for 900 ms. A 10 ms sleep loop models work opportunities; these iterations are synthetic work ticks, not tokens or GPU operations. Cooperative upstream checks socket closure each loop. Timed gateway polling uses a 20 ms curl_multi_select timeout, with a bounded sleep on -1.

## Outcomes

Primary: gateway cancellation-observed flag and request-to-gateway-end elapsed time. Secondary: request-to-cancel-publication, request-to-provider-end, synthetic tick count, forwarded bytes, poll/callback check count, and individual event traces. Natural completion is retained with cancelled=false; it is not classified as successful cancellation. All timestamps use the same host wall clock; negative intervals or event-order regressions fail verification. Run-local clock adjustment is a validity threat.

Report every cell, primary medians and ranges. For the saturated silent condition, paired bootstrap intervals for differences across randomized blocks are descriptive machine-repeat uncertainty; 10,000 resamples, seed 20406. They do not represent a user population or a production tail-latency guarantee. Do not compute p-values over provider ticks.

## Controls

Ten otherwise identical uncooperative-upstream trials: provider continues its 1.4-second loop after socket closure. Five timer waits (5, 10, 20, 50, 100 ms), ten trials each, under isolated, early-release, saturated, silent conditions. These 60 trials are secondary, outside the factorial. Keep all raw traces. Authorization tests cover cross-session cancellation, absent/wrong CSRF, malformed IDs, repeated cancellation, generation isolation, and duplicate generation IDs.

## Scope

Single host, loopback, native PHP file sessions, nginx/FPM and libcurl. No model-quality, GPU-memory, token billing, framework-prevalence, or automatic browser-disconnect claims. The conditional latency bound assumes bounded control admission, bounded lock waiting, bounded poll opportunities and cooperative upstream reaction. Saturation of the control pool or its backing store invalidates a bound that assumes bounded admission.

## Library extension (specified before extension collection)

Symfony HttpClient v8.1.9, exact dependencies in composer.lock. Forty new trials, ten randomized blocks: Symfony with all controls enabled; Symfony without session release; Symfony without control reservation; direct cURL with all controls enabled. Three offered streams, silent provider, 20 ms timed stream wait. Symfony consumes timeout chunks, restarts stream observation and calls response.cancel() when a marker is visible. Each block uses a fresh isolated stack; seed 271828. Measure the same events and outcomes. Do not pool these trials into the primary factorial. The extension tests whether the contract can be satisfied by an existing client, not whether a new client outperforms it.
