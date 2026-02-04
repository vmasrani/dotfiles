# mutt/msmtp

_Last updated: 2026-01-27_

## Purpose

Configuration for msmtp, a lightweight SMTP client that enables Mutt email client to send mail via Gmail SMTP. Handles email transmission with TLS encryption and password management via external secrets file.

## Key Files

| File | Role | Notable Exports |
|------|------|-----------------|
| `config` | msmtp SMTP configuration | Gmail account setup, SMTP defaults, TLS settings |

## Patterns

- **Credentials externalization**: Passwords sourced from `~/.mutt_secrets` via `passwordeval` to keep sensitive data out of version control
- **Single account configuration**: Gmail account defined as default
- **TLS security**: Explicit TLS enablement with system CA bundle verification

## Dependencies

- **External**: msmtp (SMTP client), Gmail account with SMTP enabled
- **Internal**: `~/.mutt_secrets` (git-ignored secrets file containing Gmail password), `~/.config/msmtp/msmtp.log` (log output)

## Configuration Details

- **SMTP Server**: smtp.gmail.com:587 (TLS)
- **Default Account**: gmail
- **Log Location**: ~/.config/msmtp/msmtp.log
- **CA Certificate**: /etc/ssl/cert.pem (system trust store)
- **Authentication**: Enabled with TLS
- **2FA Note**: App passwords required for accounts with two-factor authentication

## Entry Points

- Symlinked to `~/.msmtprc` during dotfiles setup, enabling Mutt to invoke msmtp for sending emails
