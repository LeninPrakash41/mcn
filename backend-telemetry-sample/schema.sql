-- =============================================================================
-- MCN Community Telemetry & Feedback Database Schema
-- Database: MySQL 8.0+ / MariaDB 10.5+
-- =============================================================================

CREATE DATABASE IF NOT EXISTS mcn_telemetry 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

USE mcn_telemetry;

-- 1. Developer Registrations Table
CREATE TABLE IF NOT EXISTS mcn_registrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) DEFAULT '',
    organization VARCHAR(255) DEFAULT '',
    platform ENUM('web', 'desktop_mac', 'desktop_win', 'desktop_linux', 'cli') NOT NULL DEFAULT 'web',
    app_version VARCHAR(50) DEFAULT '3.0.0',
    newsletter_opt_in TINYINT(1) DEFAULT 1,
    ip_address VARCHAR(45) DEFAULT '',
    user_agent TEXT,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_email (email),
    INDEX idx_platform (platform),
    INDEX idx_registered_at (registered_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Feedback & Error Logs Table
CREATE TABLE IF NOT EXISTS mcn_feedback_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    registration_id INT NULL,
    email VARCHAR(255) DEFAULT '',
    feedback_type ENUM('bug', 'feedback', 'feature_request', 'error_crash') NOT NULL DEFAULT 'feedback',
    subject VARCHAR(255) DEFAULT '',
    message TEXT NOT NULL,
    error_logs LONGTEXT NULL,
    system_info JSON NULL,
    platform VARCHAR(50) DEFAULT 'web',
    app_version VARCHAR(50) DEFAULT '3.0.0',
    status ENUM('new', 'in_review', 'resolved', 'closed') DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (registration_id) REFERENCES mcn_registrations(id) ON DELETE SET NULL,
    INDEX idx_feedback_type (feedback_type),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
