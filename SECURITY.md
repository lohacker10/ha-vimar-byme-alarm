# Security policy

## Sensitive data

Please **never** publish any of the following in an issue, discussion, screenshot, HAR file, or debug log:

- Vimar SAI alarm PIN
- Vimar Web Server username/password
- `sessionid`
- cookies or authorization headers
- SOAP `<hashcode>` values when they contain the SAI PIN
- unsanitized network captures

If you accidentally publish an alarm PIN or Web Server credential, rotate it immediately.

## Security reports

For security-sensitive reports, contact the repository owner privately instead of opening a public issue.
