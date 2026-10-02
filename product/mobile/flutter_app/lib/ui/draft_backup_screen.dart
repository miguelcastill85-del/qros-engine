import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/local_vault.dart';
import '../core/research_store.dart';

/// Portable manual backup. Unlike automatic device persistence, this export is
/// deliberately plain JSON so the owner can move it between devices.
class DraftBackupScreen extends StatefulWidget {
  const DraftBackupScreen({super.key, required this.store});
  final ResearchStore store;

  @override
  State<DraftBackupScreen> createState() => _DraftBackupScreenState();
}

class _DraftBackupScreenState extends State<DraftBackupScreen> {
  final _input = TextEditingController();
  String _message = '';
  bool _busy = false;

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _export() async {
    final backup = widget.store.exportDraftBackup();
    try {
      await Clipboard.setData(ClipboardData(text: backup));
      if (!mounted) return;
      setState(() => _message =
          'Respaldo portátil copiado. Es texto sin cifrar: guárdalo de forma privada.');
    } catch (_) {
      if (!mounted) return;
      setState(() => _message =
          'No se pudo copiar. Selecciona el texto del respaldo para guardarlo.');
    }
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Respaldo portátil de borradores'),
        content: SizedBox(
          width: double.maxFinite,
          child: SingleChildScrollView(child: SelectableText(backup)),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cerrar')),
        ],
      ),
    );
  }

  Future<void> _restore() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final count = await widget.store.restoreDraftBackup(_input.text);
      _input.clear();
      if (!mounted) return;
      setState(() => _message = count == 0
          ? 'No se añadieron borradores: el respaldo está vacío o ya estaba importado.'
          : 'Borradores recuperados: $count. Ya quedaron guardados en el almacén seguro del dispositivo.');
    } on FormatException catch (error) {
      if (mounted) setState(() => _message = error.message);
    } on LocalPersistenceException catch (_) {
      if (mounted) {
        setState(() => _message =
            'No se pudo escribir en el almacén seguro. No se importó ningún borrador.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Respaldar y recuperar')),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const Text('Tus proyectos de borrador',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            const Text(
              'QROS G11 guarda automáticamente los borradores en el almacén cifrado del dispositivo. Este respaldo manual sirve para migrar o conservar una copia fuera de la app.',
            ),
            const SizedBox(height: 12),
            const Text(
              'IMPORTANTE: el respaldo portátil contiene títulos e hipótesis en texto JSON sin cifrar. No incluye tokens, recibos firmados, muestra DEMO ni autoridad científica. No lo publiques ni lo envíes al soporte.',
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              key: const Key('export-drafts'),
              onPressed: _export,
              icon: const Icon(Icons.copy),
              label: const Text('Copiar respaldo portátil'),
            ),
            const SizedBox(height: 28),
            const Text('Recuperar desde un respaldo',
                style: TextStyle(fontSize: 18)),
            const SizedBox(height: 12),
            TextField(
              key: const Key('backup-input'),
              controller: _input,
              minLines: 4,
              maxLines: 8,
              maxLength: ResearchStore.maxBackupCharacters,
              autocorrect: false,
              enableSuggestions: false,
              decoration: const InputDecoration(
                  labelText: 'Pega aquí el respaldo JSON', counterText: ''),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              key: const Key('restore-drafts'),
              onPressed: _busy ? null : _restore,
              icon: const Icon(Icons.restore),
              label: Text(_busy ? 'Recuperando…' : 'Recuperar borradores'),
            ),
            const SizedBox(height: 12),
            const Text(
              'La importación se valida completa antes de escribir. Los duplicados se omiten y ningún respaldo concede aprobación científica.',
            ),
            const SizedBox(height: 16),
            Semantics(
              liveRegion: true,
              child: Text(_message, key: const Key('backup-result')),
            ),
          ],
        ),
      );
}
