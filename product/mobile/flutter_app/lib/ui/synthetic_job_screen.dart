import 'package:flutter/material.dart';

import '../core/session_client.dart';
import '../core/universe_store.dart';

class SyntheticJobScreen extends StatefulWidget {
  const SyntheticJobScreen({
    super.key,
    required this.universeStore,
    required this.sessionStore,
    required this.jobStore,
  });

  final UniverseSessionStore universeStore;
  final SessionStore sessionStore;
  final SyntheticJobStore jobStore;

  @override
  State<SyntheticJobScreen> createState() => _SyntheticJobScreenState();
}

class _SyntheticJobScreenState extends State<SyntheticJobScreen> {
  bool _busy = false;
  String? _message;

  Future<void> _start() async {
    final draft = widget.universeStore.latest;
    if (_busy || draft == null) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await widget.jobStore.start(draft);
      if (mounted) {
        setState(() => _message =
            'Trabajo creado o recuperado. Puedes reanudarlo sin repetir el inicio.');
      }
    } catch (_) {
      if (mounted) {
        setState(() => _message =
            'No se pudo crear el trabajo. Se requiere sesión G12 válida.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resume() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final job = await widget.jobStore.resume();
      if (mounted) {
        setState(() => _message = job.complete
            ? 'Trabajo sintético completo. El resultado sigue sin PnL ni autoridad científica.'
            : 'Checkpoint remoto confirmado: ${job.state}.');
      }
    } catch (_) {
      if (mounted) {
        setState(() => _message =
            'No se pudo reanudar. El job_id local se conserva para un nuevo intento.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _sync() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await widget.jobStore.sync();
      if (mounted) setState(() => _message = 'Estado remoto sincronizado.');
    } catch (_) {
      if (mounted) {
        setState(() => _message =
            'Sincronización rechazada. No se modificó el universo local.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final draft = widget.universeStore.latest;
    return Scaffold(
      appBar: AppBar(title: const Text('Trabajo sintético reanudable')),
      body: AnimatedBuilder(
        animation: Listenable.merge([
          widget.universeStore,
          widget.sessionStore,
          widget.jobStore,
        ]),
        builder: (context, _) {
          final job = widget.jobStore.job;
          return ListView(
            padding: const EdgeInsets.all(18),
            children: [
              const Text(
                'G12 · INFRAESTRUCTURA TEST_ONLY',
                style: TextStyle(
                  color: Color(0xFFFBD67A),
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1,
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                'Este flujo prueba creación, persistencia, reanudación y recuperación de un trabajo remoto. No ejecuta backtesting económico.',
              ),
              const SizedBox(height: 18),
              if (draft == null)
                const Text('Primero crea y guarda un universo sintético en Hipótesis.')
              else ...[
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          draft.title,
                          style: const TextStyle(
                              fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        Text('Nacimientos brutos: ${draft.blueprint.rawBirths}'),
                        Text(
                          'SHA universo: ${draft.searchSpaceSha256}',
                          style: const TextStyle(fontSize: 10),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                if (!widget.sessionStore.enrolled)
                  const Text(
                    'Falta una sesión G12. Configúrala desde Evidencias → Identidad del dispositivo.',
                    style: TextStyle(color: Color(0xFFF28F94)),
                  )
                else if (job == null ||
                    job.searchSpaceSha256 != draft.searchSpaceSha256) ...[
                  FilledButton.icon(
                    key: const Key('g12-job-start'),
                    onPressed: _busy ? null : _start,
                    icon: const Icon(Icons.play_circle_outline),
                    label: const Text('Crear trabajo sintético'),
                  ),
                ] else ...[
                  Card(
                    key: const Key('g12-job-card'),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Estado: ${job.state}'),
                          Text('Progreso: ${job.progress}%'),
                          SelectableText(
                            'job_id: ${job.jobId}',
                            style: const TextStyle(fontSize: 11),
                          ),
                          const SizedBox(height: 12),
                          LinearProgressIndicator(value: job.progress / 100),
                          if (job.resultSha256 != null) ...[
                            const SizedBox(height: 12),
                            SelectableText(
                              'Resultado SHA-256: ${job.resultSha256}',
                              key: const Key('g12-result-sha'),
                              style: const TextStyle(fontSize: 10),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (!job.complete)
                    FilledButton.icon(
                      key: const Key('g12-job-resume'),
                      onPressed: _busy ? null : _resume,
                      icon: const Icon(Icons.resume_outlined),
                      label: const Text('Reanudar siguiente checkpoint'),
                    ),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    key: const Key('g12-job-sync'),
                    onPressed: _busy ? null : _sync,
                    icon: const Icon(Icons.sync),
                    label: const Text('Sincronizar estado'),
                  ),
                ],
              ],
              if (_busy)
                const Padding(
                  padding: EdgeInsets.only(top: 14),
                  child: LinearProgressIndicator(),
                ),
              if (_message != null)
                Padding(
                  padding: const EdgeInsets.only(top: 14),
                  child: Text(_message!, key: const Key('g12-job-message')),
                ),
              const SizedBox(height: 24),
              const Text(
                'economic_tests=0 · holdout cerrado · GA2 cerrado · MT5 no ejecutado · scientific_approval=false',
                style: TextStyle(fontSize: 12, color: Color(0xFFFBD67A)),
              ),
            ],
          );
        },
      ),
    );
  }
}
