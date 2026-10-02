import 'package:flutter/material.dart';

import '../core/session_client.dart';

class SessionScreen extends StatefulWidget {
  const SessionScreen({super.key, required this.store});
  final SessionStore store;

  @override
  State<SessionScreen> createState() => _SessionScreenState();
}

class _SessionScreenState extends State<SessionScreen> {
  final _origin = TextEditingController();
  final _bootstrap = TextEditingController();
  bool _busy = false;
  String? _message;

  @override
  void dispose() {
    _origin.dispose();
    _bootstrap.clear();
    _bootstrap.dispose();
    super.dispose();
  }

  Future<void> _enroll() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await widget.store.enroll(_origin.text, _bootstrap.text);
      _bootstrap.clear();
      if (mounted) {
        setState(() => _message =
            'Dispositivo vinculado. El bootstrap fue de un solo uso y no quedó guardado.');
      }
    } catch (_) {
      if (mounted) {
        setState(() => _message =
            'No se pudo crear la sesión. Revisa HTTPS y el bootstrap temporal.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _renew() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await widget.store.renew();
      if (mounted) setState(() => _message = 'Sesión renovada y rotada.');
    } catch (_) {
      if (mounted) {
        setState(() => _message =
            'La renovación fue rechazada. El bootstrap no se reutiliza.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _signOut() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    await widget.store.signOut();
    if (mounted) {
      setState(() {
        _busy = false;
        _message = 'Sesión local eliminada. La revocación remota se intentó una sola vez.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = widget.store.session;
    return Scaffold(
      appBar: AppBar(title: const Text('Identidad del dispositivo')),
      body: AnimatedBuilder(
        animation: widget.store,
        builder: (context, _) => ListView(
          padding: const EdgeInsets.all(18),
          children: [
            const Text(
              'G12 · SESIÓN TEST_ONLY',
              style: TextStyle(
                color: Color(0xFFFBD67A),
                fontWeight: FontWeight.bold,
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              'La identidad está vinculada a este dispositivo. Los tokens de sesión se guardan únicamente en el almacenamiento seguro del teléfono.',
            ),
            const SizedBox(height: 18),
            if (widget.store.warning != null)
              Text(
                'Alerta local: ${widget.store.warning}',
                style: const TextStyle(color: Color(0xFFF28F94)),
              ),
            if (session == null) ...[
              TextField(
                key: const Key('g12-origin'),
                controller: _origin,
                autocorrect: false,
                keyboardType: TextInputType.url,
                decoration: const InputDecoration(
                  labelText: 'Servidor HTTPS G12',
                  hintText: 'https://qros-mobile-g12-test-only.example.workers.dev',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('g12-bootstrap'),
                controller: _bootstrap,
                obscureText: true,
                autocorrect: false,
                enableSuggestions: false,
                decoration: const InputDecoration(
                  labelText: 'Bootstrap temporal de un solo uso',
                ),
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                key: const Key('g12-enroll'),
                onPressed: _busy ? null : _enroll,
                icon: const Icon(Icons.phonelink_lock_outlined),
                label: Text(_busy ? 'Vinculando…' : 'Vincular dispositivo'),
              ),
            ] else ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'SESIÓN ACTIVA',
                        style: TextStyle(
                          color: Color(0xFF36D7B7),
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 12),
                      SelectableText(
                        session.clientId,
                        key: const Key('g12-client-id'),
                      ),
                      const SizedBox(height: 8),
                      Text('Servidor: ${session.origin}'),
                      Text('Access expira: ${DateTime.fromMillisecondsSinceEpoch(session.accessExpiresAt * 1000, isUtc: true).toIso8601String()}'),
                      Text('Refresh expira: ${DateTime.fromMillisecondsSinceEpoch(session.refreshExpiresAt * 1000, isUtc: true).toIso8601String()}'),
                      const SizedBox(height: 12),
                      const Text(
                        'Scope: synthetic:jobs · autoridad científica: NINGUNA',
                        style: TextStyle(color: Color(0xFFFBD67A)),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 14),
              OutlinedButton.icon(
                key: const Key('g12-renew'),
                onPressed: _busy ? null : _renew,
                icon: const Icon(Icons.refresh),
                label: const Text('Rotar sesión ahora'),
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                key: const Key('g12-signout'),
                onPressed: _busy ? null : _signOut,
                icon: const Icon(Icons.logout),
                label: const Text('Cerrar y revocar sesión'),
              ),
            ],
            if (_busy)
              const Padding(
                padding: EdgeInsets.only(top: 14),
                child: LinearProgressIndicator(),
              ),
            if (_message != null)
              Padding(
                padding: const EdgeInsets.only(top: 14),
                child: Text(_message!, key: const Key('g12-session-message')),
              ),
            const SizedBox(height: 24),
            const Text(
              'Esta sesión no puede abrir holdout, declarar PASS, acceder a MT5 ni enviar órdenes.',
              style: TextStyle(fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}
