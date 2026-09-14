# QROS R2T v2.4 checkpoint

- Source run: `20260914_002325_fd75f9c7`.
- Evidence photo SHA-256: `d0cda0cf35420ffb3ccd2603a06a83ec35f9253c7c328c1d5a88aba87ddc59ee`.
- v2.3 runtime control-flow result: runtime checks reached and passed through restart-read/final quiescence; the failure occurred only in `Zip-Evidence()` when Windows PowerShell 5.1 could not load `IO.Compression.FileSystem`.
- Classification: `R2T_RUNTIME_CHECKS=VERIFIED_PASS`, `R2T_EVIDENCE_PACKAGING=FAIL`, promotion withheld pending a rerun that emits a valid evidence ZIP + PASS receipt.
- D15 repair: `System.IO.Compression.FileSystem`, `[System.IO.Compression.ZipFile]`, `[System.IO.Compression.CompressionLevel]`.
- Regression gate: rejects stripped `System.` namespace and preserves D04/D10/D14 controls.
- MQL qualifier SHA-256 unchanged: `89dc345b21e7d294a68b8c1cad2afd2bf07896d275b1132709ea5eee2a3db89e`.
- v2.4 package SHA-256: `f13eb491308b59ce465122b05247a64b35ff9f97495f2e17273b874096c07b60`.
- Candidate3 not executed; deployment prohibited; cert remains 0.
- R2 overall remains unqualified until evidence packaging rerun succeeds and the full R2 sequence is reconciled.
