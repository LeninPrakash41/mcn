<?php
/**
 * MCN Telemetry — Feedback & Error Log Ingestion Endpoint
 * POST /feedback.php
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

if (!is_array($data) || empty($data['message'])) {
    send_json_response(['error' => 'Message or feedback description is required.'], 400);
}

$email         = filter_var(trim((string)($data['email'] ?? '')), FILTER_VALIDATE_EMAIL) ?: null;
$feedback_type = in_array($data['feedback_type'] ?? '', ['bug', 'feedback', 'feature_request', 'error_crash'])
                 ? $data['feedback_type'] : 'feedback';
$subject       = trim((string)($data['subject'] ?? ''));
$message       = trim((string)$data['message']);
$error_logs    = !empty($data['error_logs']) ? (string)$data['error_logs'] : null;
$system_info   = !empty($data['system_info']) ? json_encode($data['system_info']) : null;
$platform      = trim((string)($data['platform'] ?? 'web'));
$app_version   = trim((string)($data['app_version'] ?? '3.0.0'));

try {
    // Check if user is already registered
    $reg_id = null;
    if ($email) {
        $reg_stmt = $pdo->prepare("SELECT id FROM mcn_registrations WHERE email = :email LIMIT 1");
        $reg_stmt->execute([':email' => $email]);
        $row = $reg_stmt->fetch();
        if ($row) {
            $reg_id = (int)$row['id'];
        }
    }

    $stmt = $pdo->prepare("
        INSERT INTO mcn_feedback_logs 
            (registration_id, email, feedback_type, subject, message, error_logs, system_info, platform, app_version)
        VALUES 
            (:reg_id, :email, :type, :subject, :msg, :logs, :sys_info, :platform, :version)
    ");

    $stmt->execute([
        ':reg_id'   => $reg_id,
        ':email'    => $email,
        ':type'     => $feedback_type,
        ':subject'  => $subject,
        ':msg'      => $message,
        ':logs'     => $error_logs,
        ':sys_info' => $system_info,
        ':platform' => $platform,
        ':version'  => $app_version
    ]);

    $insert_id = (int)$pdo->lastInsertId();

    send_json_response([
        'success'     => true,
        'feedback_id' => $insert_id,
        'message'     => 'Thank you! Your feedback has been received and logged.',
        'timestamp'   => date('c')
    ], 200);

} catch (PDOException $e) {
    send_json_response([
        'success' => false,
        'error'   => 'Database error: ' . $e->getMessage()
    ], 500);
}
