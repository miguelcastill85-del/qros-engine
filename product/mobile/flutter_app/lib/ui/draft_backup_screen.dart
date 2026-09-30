import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/research_store.dart';

/// Explicit local backup. No automatic upload or scientific receipt import.
class DraftBackupScreen extends StatefulWidget {
  const DraftBackupScreen({super.key, required this.store});
  final ResearchStore store;
  @override
  State<DraftBackupScreen> createState() => _DraftBackupScreenState();
}

class _DraftBackupScreenState extends State<DraftBackupScreen> {
  final _input = TextEditingController();
  String _message = '';
  @override
  void dispose() { _input.dispose(); super.dispose(); }

  Future<void> _export() async {
    final backup = widget.store.exportDraftBackup();
    try {
      await Clipboard.setData(ClipboardData(text: backup));
      if (!mounted) return;
      setState(() => _message = 'Respaldo copiado. Guárdalo en un archivo privado antes de cerrar la app.');
    } catch (_) {
      if (!mounted) return;
      setState(() => _message = 'No se pudo copiar. Selecciona el texto del respaldo para guardarlo.');
    }
    if (!mounted) return;
    await showDialog<void>(context: context, builder: (context) => AlertDialog(
      title: const Text('Respaldo de borradores'),
      content: SizedBox(width: double.maxFinite, child: SingleChildScrollView(
        child: SelectableText(backup))),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cerrar'))],
    ));
  }

  void _restore() {
    try {
      final count = widget.store.restoreDraftBackup(_input.text);
      _input.clear();
      setState(() => _message = count == 0
        ? 'No se añadieron borradores: el respaldo está vacío o ya estaba importado.'
        : 'Borradores recuperados: $count. Permanecen como borradores locales.');
    } on FormatException catch (error) {
      setState(() => _message = error.message);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Respaldar y recuperar')),
    body: ListView(padding: const EdgeInsets.all(20), children: [
      const Text('Tus proyectos de borrador', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
      const SizedBox(height: 12),
      const Text('Esta versión no guarda automáticamente al cerrar. Copia el respaldo y guárdalo en un archivo privado para recuperarlo después.'),
      const SizedBox(height: 12),
      const Text('Incluye títulos e hipótesis escritos por ti, en texto sin cifrar. No incluye el editor de universos, tokens ni recibos firmados. No lo publiques ni lo envíes al soporte.'),
      const SizedBox(height: 20),
      FilledButton.icon(key: const Key('export-drafts'), onPressed: _export,
        icon: const Icon(Icons.copy), label: const Text('Copiar respaldo')),
      const SizedBox(height: 28),
      const Text('Recuperar desde un respaldo', style: TextStyle(fontSize: 18)),
      const SizedBox(height: 12),
      TextField(key: const Key('backup-input'), controller: _input,
        minLines: 4, maxLines: 8, maxLength: ResearchStore.maxBackupCharacters,
        autocorrect: false, enableSuggestions: false,
        decoration: const InputDecoration(labelText: 'Pega aquí el respaldo JSON', counterText: '')),
      const SizedBox(height: 12),
      OutlinedButton.icon(key: const Key('restore-drafts'), onPressed: _restore,
        icon: const Icon(Icons.restore), label: const Text('Recuperar borradores')),
      const SizedBox(height: 12),
      const Text('No reemplaza tus proyectos actuales. Los duplicados se omiten. Ningún respaldo concede aprobación científica.'),
      const SizedBox(height: 16),
      Semantics(liveRegion: true, child: Text(_message, key: const Key('backup-result'))),
    ]),
  );
}
