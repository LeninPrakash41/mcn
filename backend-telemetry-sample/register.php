<?php
/**
 * MCN Telemetry — Developer Registration Endpoint
 * POST /register.php
 */

declare(strict_types=1);

require_once __DIR__ . '/db.php';

// Handle CORS Preflight
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    send_json_response(['status' => 'ok'], 200);
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    send_json_response(['error' => 'Method not allowed. Use POST.'], 405);
}

$raw_input = file_get_contents('php://input');
$data = json_decode($raw_input, true);

if (!is_array($data) || empty($data['email'])) {
    send_json_response(['error' => 'Valid email address is required.'], 400);
}

$email            = filter_var(trim((string)$data['email']), FILTER_VALIDATE_EMAIL);
if (!$email) {
    send_json_response(['error' => 'Invalid email format.'], 400);
}

$name             = trim((string)($data['name'] ?? ''));
$organization     = trim((string)($data['organization'] ?? ''));
$platform         = in_array($data['platform'] ?? '', ['web', 'desktop_mac', 'desktop_win', 'desktop_linux', 'cli']) 
                    ? $data['platform'] : 'web';
$app_version      = trim((string)($data['app_version'] ?? '3.0.0'));
$newsletter_opt_in = !empty($data['newsletter_opt_in']) ? 1 : 0;
$ip_address       = $_SERVER['REMOTE_ADDR'] ?? '';
$user_agent       = $_SERVER['HTTP_USER_AGENT'] ?? '';

try {
    $stmt = $pdo->prepare("
        INSERT INTO mcn_registrations 
            (email, name, organization, platform, app_version, newsletter_opt_in, ip_address, user_agent)
        VALUES 
            (:email, :name, :org, :platform, :version, :opt_in, :ip, :ua)
        ON DUPLICATE KEY UPDATE
            name = IF(VALUES(name) != '', VALUES(name), name),
            organization = IF(VALUES(organization) != '', VALUES(organization), organization),
            platform = VALUES(platform),
            app_version = VALUES(version),
            newsletter_opt_in = VALUES(newsletter_opt_in),
            last_active_at = CURRENT_TIMESTAMP
    ");

    $stmt->execute([
        ':email'    => $email,
        ':name'     => $name,
        ':org'      => $organization,
        ':platform' => $platform,
        ':version'  => $app_version,
        ':opt_in'   => $newsletter_opt_in,
        ':ip'       => $ip_address,
        ':ua'       => $user_agent
    ]);

    send_json_response([
        'success'   => true,
        'message'   => 'Thank you for registering with the MCN Developer Community!',
        'email'     => $email,
        'platform'  => $platform,
        'timestamp' => date('c')
    ], 200);

} catch (PDOException $e) {
    send_json_response([
        'success' => false,
        'error'   => 'Database error: ' . $e->getMessage()
    ], 500);
}
