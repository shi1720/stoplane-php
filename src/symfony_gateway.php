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
require_once __DIR__.'/../vendor/autoload.php';
$client = new \Symfony\Component\HttpClient\CurlHttpClient();
$response = $client->request('GET', getenv('STOPLANE_UPSTREAM'), [
    'query'=>['id'=>$id,'shape'=>$shape], 'buffer'=>false, 'timeout'=>4, 'max_duration'=>4]);
$seen=false; $bytes=0; $checks=0; $done=false;
event($id, 'upstream_open', ['driver'=>'symfony']);
do {
    foreach ($client->stream($response, $poll) as $chunk) {
        $idle=$chunk->isTimeout(); ++$checks;
        if (stopped($id)) {
            $seen=true; event($id, 'cancel_observed', ['via'=>'symfony_stream']);
            $response->cancel(); break 2;
        }
        if ($idle) break; // Restart stream() after a timeout chunk.
        if ($chunk->isFirst()) { $response->getStatusCode(); continue; }
        if ($chunk->isLast()) { $done=true; break; }
        $body=$chunk->getContent(); $bytes+=strlen($body); echo $body; flush();
    }
} while (!$done);
unset($response, $client);
event($id, 'gateway_end', ['cancelled'=>$seen,'bytes'=>$bytes,'checks'=>$checks,'driver'=>'symfony']);
if (session_status() === PHP_SESSION_ACTIVE) session_write_close();
