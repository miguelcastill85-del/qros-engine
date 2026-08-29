# Arquitectura QROS ENGINE v0.3

```text
QDATA Authority
  ├─ ticks bytes + SHA-256
  ├─ session map + SHA-256
  ├─ manifest
  ├─ timezone evidence receipt
  └─ source evidence receipt
          │
          ▼
QDATA audit streaming
          │
          ├─ TEST_READY (sólo fixtures/infraestructura)
          └─ RESEARCH_READY (bloqueado en v0.3)
          │
          ▼
QROS Intent V2
  ├─ exact signal record
  ├─ exact authority hashes
  ├─ event contract hash
  └─ execution policy hash
          │
          ▼
Native streaming replay
  ├─ fixed-point
  ├─ seq causal authority
  ├─ Bid/Ask
  ├─ SL-first
  ├─ gap first observed quote
  └─ authoritative session close
          │
          ▼
Immutable ledger + receipt
  ├─ source_root SHA-256
  ├─ build_contract SHA-256
  ├─ executable SHA-256
  ├─ authority SHA-256s
  └─ ledger SHA-256
```

## Capas futuras, todavía no implementadas

`Production QDATA Verifier → Feature Graph → Universe Compiler → Native Miner → Gates/Supergate → Holdout Vault → Portfolio Engine → MT5 Bridge`.

Python permanece como implementación independiente de referencia, no como dependencia del binario estático.
