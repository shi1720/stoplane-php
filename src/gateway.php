<?php
declare(strict_types=1);
// Research reference: loopback only; single-host, durable cancellation markers.
$root = getenv('STOPLANE_STATE');
if (!$root || !is_dir($root)) { http_response_code(500); exit; }
function event(string $id, string $kind, array $extra = []): void {
    global $root;
    file_put_contents("$root/$id.events", json_encode(['t'=>microtime(true),
        'event'=>$kind,'pid'=>getmypid()] + $extra)."\n", FILE_APPEND | LOCK_EX);
}
function stopped(string $id): bool {
    global $root;
    clearstatcache(true, "$root/$id.cancel");
    return is_file("$root/$id.cancel");
}
session_name('STOPLANE');
$action = $_GET['action'] ?? '';
$id = $_GET['id'] ?? '';
if ($action !== 'init' && !preg_match('/^[a-f0-9]{32}$/D', $id)) {
    http_response_code(400); exit;
}
if ($action !== 'init') event($id, 'handler_enter', ['action'=>$action]);
session_start(['cookie_httponly'=>true, 'cookie_samesite'=>'Strict']);
if ($action === 'init') {
    $_SESSION['actor'] ??= bin2hex(random_bytes(16));
    $_SESSION['csrf'] ??= bin2hex(random_bytes(32));
    $data = ['csrf'=>$_SESSION['csrf']];
    session_write_close();
    header('Content-Type: application/json'); echo json_encode($data); exit;
}
event($id, 'session_acquired', ['action'=>$action]);
$actor = $_SESSION['actor'] ?? '';
$csrf = $_SESSION['csrf'] ?? '';
if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !$actor || !$csrf ||
    !hash_equals($csrf, $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '')) {
    session_write_close(); http_response_code(403); exit;
}
if ($action === 'cancel') {
    session_write_close();
    $owner = @file_get_contents("$root/$id.owner");
    if ($owner === false || !hash_equals($owner, $actor)) {
        http_response_code(403); exit;
    }
    // An immutable marker makes repeat requests idempotent. IDs are never reused.
    $f = @fopen("$root/$id.cancel", 'x');
    if ($f !== false) { fwrite($f, 'cancel'); fclose($f); }
    clearstatcache(true, "$root/$id.cancel");
    if (!is_file("$root/$id.cancel")) { http_response_code(503); exit; }
    event($id, 'cancel_published');
    header('Content-Type: application/json'); echo '{"accepted":true}'; exit;
}
if ($action !== 'stream') { session_write_close(); http_response_code(400); exit; }
$released = ($_GET['release'] ?? '1') === '1';
$timer = ($_GET['timer'] ?? '1') === '1';
$poll = max(0.005, min(0.1, (float)($_GET['poll'] ?? '0.02')));
$shape = $_GET['shape'] ?? 'regular';
if (!in_array($shape, ['regular','silent','uncooperative'], true)) {
    session_write_close(); http_response_code(400); exit;
}
$f = @fopen("$root/$id.owner", 'x');
if ($f === false) { session_write_close(); http_response_code(409); exit; }
fwrite($f, $actor); fclose($f);
if ($released) session_write_close();
ignore_user_abort(true);
header('Content-Type: text/event-stream');
header('Cache-Control: no-store'); header('X-Accel-Buffering: no');
echo ": ready\n\n"; flush();
$ch = curl_init(getenv('STOPLANE_UPSTREAM').'?'.http_build_query(['id'=>$id,'shape'=>$shape]));
$seen = false; $bytes = 0; $checks = 0;
curl_setopt_array($ch, [CURLOPT_TIMEOUT_MS=>4000, CURLOPT_CONNECTTIMEOUT_MS=>1000,
    CURLOPT_WRITEFUNCTION=>function($ch, string $chunk) use ($id, &$seen, &$bytes, &$checks): int {
        ++$checks;
        if (stopped($id)) { $seen=true; event($id, 'cancel_observed', ['via'=>'callback']); return 0; }
        $bytes += strlen($chunk); echo $chunk; flush(); return strlen($chunk);
    }]);
event($id, 'upstream_open');
if ($timer) {
    $mh = curl_multi_init(); curl_multi_add_handle($mh, $ch);
    do {
        ++$checks;
        if (stopped($id)) { $seen=true; event($id, 'cancel_observed', ['via'=>'timer']); break; }
        do { $status = curl_multi_exec($mh, $running); } while ($status === CURLM_CALL_MULTI_PERFORM);
        if ($status !== CURLM_OK) { event($id, 'multi_error', ['code'=>$status]); break; }
        if ($seen || !$running) break;
        if (curl_multi_select($mh, $poll) === -1) usleep((int)($poll * 1000000));
    } while (true);
    curl_multi_remove_handle($mh, $ch); curl_multi_close($mh);
} else { curl_exec($ch); }
$errno = curl_errno($ch);
curl_close($ch); unset($ch); // Removing/closing releases the local transport.
event($id, 'gateway_end', ['cancelled'=>$seen,'bytes'=>$bytes,'checks'=>$checks,'curl_errno'=>$errno]);
if (session_status() === PHP_SESSION_ACTIVE) session_write_close();
