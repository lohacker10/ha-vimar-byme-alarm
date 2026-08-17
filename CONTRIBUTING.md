# Contributing

Contributions are welcome.

Before opening a pull request:

1. Keep the integration domain as `vimar_alarm`.
2. Do not add unrelated Vimar lights, covers, climate, or media entities.
3. Never commit real credentials, alarm PINs, session IDs, cookies, or raw HAR captures.
4. Keep database access read-only (`SELECT`) unless the operation is the explicit SAI arm/disarm `SETVALUE`.
5. Run the GitHub HACS and Hassfest validation workflows.

Protocol changes should include the Vimar Web Server model/firmware on which they were verified.
