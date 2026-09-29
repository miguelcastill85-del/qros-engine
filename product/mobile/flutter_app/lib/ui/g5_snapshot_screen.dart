import 'package:flutter/material.dart';
import '../core/g5_snapshot.dart';

class G5SnapshotScreen extends StatefulWidget {
  const G5SnapshotScreen({super.key, required this.gateway});
  final G5SnapshotGateway gateway;
  @override
  State<G5SnapshotScreen> createState() => _G5SnapshotScreenState();
}

class _G5SnapshotScreenState extends State<G5SnapshotScreen> {
  final _origin = TextEditingController(text: G9LiveTrust.origin);
  final _token = TextEditingController();
  VerifiedG5Snapshot? _snapshot;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _origin.dispose();
    _token.clear();
    _token.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (_busy) return;
    setState(() { _busy = true; _error = null; _snapshot = null; });
    try {
      final value = await widget.gateway.fetch(_origin.text, _token.text);
      if (mounted) setState(() => _snapshot = value);
    } catch (_) {
      if (mounted) setState(() => _error = 'Prueba rechazada. No se aceptó el servidor, token o cadena firmada.');
    } finally {
      if (mounted) {
        _token.clear();
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Recibo G5 verificado')),
    body: ListView(padding: const EdgeInsets.all(18), children: [
      const Text('G9 · TEST_ONLY · SOLO LECTURA', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFFFBD67A))),
      const SizedBox(height: 10),
      const Text('El APK verifica una raíz pública sintética fijada fuera de la respuesta. No concede autoridad científica ni conecta trading.'),
      const SizedBox(height: 18),
      TextField(key: const Key('g6-origin'), controller: _origin, readOnly: true, autocorrect: false,
        decoration: const InputDecoration(labelText: 'Origen HTTPS', hintText: 'https://...')),
      const SizedBox(height: 12),
      TextField(key: const Key('g6-token'), controller: _token, obscureText: true, autocorrect: false, enableSuggestions: false,
        decoration: const InputDecoration(labelText: 'Token temporal')),
      const SizedBox(height: 16),
      FilledButton.icon(key: const Key('g6-fetch'), onPressed: _busy ? null : _load,
        icon: const Icon(Icons.verified_user_outlined), label: const Text('Verificar snapshot firmado')),
      if (_busy) const Padding(padding: EdgeInsets.all(10), child: LinearProgressIndicator()),
      if (_error != null) Padding(padding: const EdgeInsets.only(top: 14),
        child: Text(_error!, key: const Key('g6-error'), style: const TextStyle(color: Color(0xFFF28F94)))),
      if (_snapshot != null) Card(key: const Key('g6-verified'), margin: const EdgeInsets.only(top: 18),
        child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('CADENA SINTÉTICA VERIFICADA', style: TextStyle(color: Color(0xFF36D7B7), fontWeight: FontWeight.bold)),
          const SizedBox(height: 10),
          Text('${_snapshot!.tenant} / ${_snapshot!.project}'),
          Text('Campaña: ${_snapshot!.campaign}'),
          Text('Filas auditadas: ${_snapshot!.rows}'),
          Text('Timezone: ${_snapshot!.brokerTimezone}'),
          Text('Secuencia: ${_snapshot!.sequence}'),
          Text('HEAD: ${_snapshot!.headSha256}', style: const TextStyle(fontSize: 10)),
          const SizedBox(height: 8),
          const Text('No demuestra rentabilidad, licencia real ni custodia externa de producción.',
            style: TextStyle(color: Color(0xFFFBD67A), fontSize: 12)),
        ]))),
      const SizedBox(height: 18),
      const Text('Las credenciales permanecen en memoria de esta pantalla y no se guardan.', style: TextStyle(fontSize: 12)),
    ]),
  );
}
