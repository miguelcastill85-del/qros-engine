import 'package:flutter/material.dart';
import '../core/verified_demo.dart';

/// TEST_ONLY local credential entry. The token stays in widget memory;
/// no preferences, analytics, file export, logs or print statements.
class VerifiedDemoScreen extends StatefulWidget {
  const VerifiedDemoScreen({super.key, required this.gateway});
  final DemoGateway gateway;
  @override
  State<VerifiedDemoScreen> createState() => _VerifiedDemoScreenState();
}

class _VerifiedDemoScreenState extends State<VerifiedDemoScreen> {
  final _url = TextEditingController();
  final _token = TextEditingController();
  VerifiedDemo? _result;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _url.dispose();
    _token.clear();
    _token.dispose();
    super.dispose();
  }

  Future<void> _fetch() async {
    if (_busy) return;
    setState(() { _busy = true; _error = null; _result = null; });
    try {
      final result = await widget.gateway.fetch(_url.text, _token.text);
      if (!mounted) return;
      setState(() { _result = result; });
    } catch (_) {
      if (!mounted) return;
      // Do not disclose token, host internals, signatures or raw payloads.
      setState(() { _error = 'Verificación rechazada. Comprueba HTTPS, el token y las firmas de la demo.'; });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Demo autenticada')),
    body: ListView(padding: const EdgeInsets.all(18), children: [
      const Text('SOLO LECTURA · TEST_ONLY', style: TextStyle(color: Color(0xFFFBD67A), fontWeight: FontWeight.bold)),
      const SizedBox(height: 12),
      const Text('Consulta una fixture sintética con un recibo firmado y un HEAD fijado. No se conecta a operaciones ni a MT5.'),
      const SizedBox(height: 22),
      TextField(key: const Key('remote-demo-url'), controller: _url,
        keyboardType: TextInputType.url, autocorrect: false,
        decoration: const InputDecoration(labelText: 'Servidor HTTPS', hintText: 'https://demo.example.com')),
      const SizedBox(height: 12),
      TextField(key: const Key('remote-demo-token'), controller: _token,
        obscureText: true, autocorrect: false, enableSuggestions: false,
        decoration: const InputDecoration(labelText: 'Token temporal', hintText: 'No queda almacenado')),
      const SizedBox(height: 16),
      FilledButton.icon(key: const Key('remote-demo-fetch'),
        onPressed: _busy ? null : _fetch, icon: const Icon(Icons.verified_user_outlined),
        label: const Text('Verificar recibo TEST_ONLY')),
      if (_busy) const Padding(padding: EdgeInsets.all(10), child: LinearProgressIndicator()),
      if (_error != null) Padding(padding: const EdgeInsets.only(top: 14),
        child: Text(_error!, key: const Key('remote-demo-failed'), style: const TextStyle(color: Color(0xFFF28F94)))),
      if (_result != null) Card(key: const Key('remote-demo-verified'),
        margin: const EdgeInsets.only(top: 20), child: Padding(padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('RECIBO DE DEMO VERIFICADO', style: TextStyle(color: Color(0xFF36D7B7), fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Text(_result!.projectTitle, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            Text('${_result!.symbol} · ${_result!.side} · ${_result!.timeframe}'),
            const SizedBox(height: 8),
            Text('Estado: ${_result!.state}'),
            Text('Ancla sintética: secuencia ${_result!.anchorSequence}'),
            Text('SHA-256: ${_result!.anchorHash}', style: const TextStyle(fontSize: 10)),
            const SizedBox(height: 8),
            const Text('La firma confirma únicamente la procedencia de esta DEMO. No demuestra rentabilidad ni aprobación científica.',
              style: TextStyle(fontSize: 12, color: Color(0xFFFBD67A))),
          ]),
        ),
      ),
      const SizedBox(height: 24),
      const Text('Sin cuentas de broker, datos reales, transiciones científicas ni almacenamiento de credenciales.',
        style: TextStyle(fontSize: 12)),
    ]),
  );
}
