import 'package:flutter/material.dart';
import '../core/research_store.dart';
import 'app_shell.dart';

class NewProjectScreen extends StatefulWidget {
  const NewProjectScreen({super.key, required this.store});
  final ResearchStore store;
  @override
  State<NewProjectScreen> createState() => _NewProjectScreenState();
}

class _NewProjectScreenState extends State<NewProjectScreen> {
  final _formKey = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _thesis = TextEditingController();
  String _symbol = 'XAUUSD';
  String _side = 'BUY';
  String _timeframe = 'M15';

  @override
  void dispose() {
    _title.dispose();
    _thesis.dispose();
    super.dispose();
  }

  void _create() {
    if (!_formKey.currentState!.validate()) return;
    try {
      widget.store.createLocalDraft(
        title: _title.text,
        thesis: _thesis.text,
        symbol: _symbol,
        side: _side,
        timeframe: _timeframe,
      );
      Navigator.of(context).pop(true);
    } on ArgumentError catch (error) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$error')));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Nueva hipótesis')),
    body: Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(18, 12, 18, 32),
        children: [
          const StatusPill(label: 'BORRADOR · TEST_ONLY', color: qrosAmber),
          const SizedBox(height: 18),
          const Text('Define una idea comprobable',
            style: TextStyle(fontSize: 25, height: 1.15, fontWeight: FontWeight.w900)),
          const SizedBox(height: 9),
          const Text('Este formulario guarda un borrador solo durante la sesión. No registra una estrategia ni solicita ejecución.',
            style: TextStyle(color: qrosMuted, height: 1.5, fontSize: 13)),
          const SizedBox(height: 23),
          TextFormField(
            key: const Key('draft-title'),
            controller: _title,
            maxLength: 72,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(labelText: 'Título de la hipótesis', hintText: 'Ej. Recuperación de mínimo M15'),
            validator: (s) => s == null || s.trim().length < 3 ? 'Introduce al menos 3 caracteres.' : null,
          ),
          const SizedBox(height: 14),
          TextFormField(
            key: const Key('draft-thesis'),
            controller: _thesis,
            minLines: 3,
            maxLines: 5,
            maxLength: 500,
            decoration: const InputDecoration(labelText: 'Mecanismo causal propuesto', alignLabelWithHint: true,
              hintText: 'Describe qué condición se observaría antes de la entrada.'),
            validator: (s) => s == null || s.trim().length < 10 ? 'Describe la hipótesis con al menos 10 caracteres.' : null,
          ),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            key: const Key('draft-symbol'),
            initialValue: _symbol,
            decoration: const InputDecoration(labelText: 'Activo'),
            items: [for (final s in ResearchStore.symbols) DropdownMenuItem(value: s, child: Text(s))],
            onChanged: (s) => setState(() => _symbol = s ?? _symbol),
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            key: const Key('draft-side'),
            initialValue: _side,
            decoration: const InputDecoration(labelText: 'Dirección'),
            items: [for (final s in ResearchStore.sides) DropdownMenuItem(value: s, child: Text(s))],
            onChanged: (s) => setState(() => _side = s ?? _side),
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            key: const Key('draft-timeframe'),
            initialValue: _timeframe,
            decoration: const InputDecoration(labelText: 'Timeframe'),
            items: [for (final s in ResearchStore.timeframes) DropdownMenuItem(value: s, child: Text(s))],
            onChanged: (s) => setState(() => _timeframe = s ?? _timeframe),
          ),
          const SizedBox(height: 23),
          Container(
            padding: const EdgeInsets.all(13),
            decoration: BoxDecoration(color: const Color(0xFF302D27), borderRadius: BorderRadius.circular(12)),
            child: const Text('La app NO puede declarar PASS, congelar contratos científicos, abrir holdout ni enviar órdenes.',
              style: TextStyle(color: qrosAmber, fontSize: 12, height: 1.5)),
          ),
          const SizedBox(height: 21),
          FilledButton.icon(
            key: const Key('new-project-submit'),
            onPressed: _create,
            icon: const Icon(Icons.save_outlined),
            label: const Text('Guardar borrador local'),
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
          ),
        ],
      ),
    ),
  );
}
