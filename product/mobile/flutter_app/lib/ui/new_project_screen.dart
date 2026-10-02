import 'package:flutter/material.dart';

import '../core/local_vault.dart';
import '../core/research_store.dart';
import 'app_shell.dart';

class NewProjectScreen extends StatefulWidget {
  const NewProjectScreen({
    super.key,
    required this.store,
    this.existing,
  });

  final ResearchStore store;
  final ResearchProject? existing;

  @override
  State<NewProjectScreen> createState() => _NewProjectScreenState();
}

class _NewProjectScreenState extends State<NewProjectScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _title;
  late final TextEditingController _thesis;
  late String _symbol;
  late String _side;
  late String _timeframe;
  bool _busy = false;

  bool get _editing => widget.existing != null;

  @override
  void initState() {
    super.initState();
    final p = widget.existing;
    _title = TextEditingController(text: p?.title ?? '');
    _thesis = TextEditingController(text: p?.thesis ?? '');
    _symbol = p?.symbol ?? 'XAUUSD';
    _side = p?.side ?? 'BUY';
    _timeframe = p?.timeframe ?? 'M15';
  }

  @override
  void dispose() {
    _title.dispose();
    _thesis.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_busy || !_formKey.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      if (_editing) {
        await widget.store.updateLocalDraft(
          id: widget.existing!.id,
          title: _title.text,
          thesis: _thesis.text,
          symbol: _symbol,
          side: _side,
          timeframe: _timeframe,
        );
      } else {
        await widget.store.createLocalDraft(
          title: _title.text,
          thesis: _thesis.text,
          symbol: _symbol,
          side: _side,
          timeframe: _timeframe,
        );
      }
      if (mounted) Navigator.of(context).pop(true);
    } on ArgumentError catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message.toString())));
      }
    } on LocalPersistenceException catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text(
            'No se pudo guardar de forma segura. No se aplicó ningún cambio.',
          ),
        ));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
            title: Text(_editing ? 'Editar hipótesis' : 'Nueva hipótesis')),
        body: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(18, 12, 18, 32),
            children: [
              const StatusPill(
                  label: 'BORRADOR · TEST_ONLY', color: qrosAmber),
              const SizedBox(height: 18),
              Text(
                _editing
                    ? 'Actualiza tu borrador'
                    : 'Define una idea comprobable',
                style: const TextStyle(
                    fontSize: 25, height: 1.15, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 9),
              const Text(
                'Se guarda cifrado en el almacén seguro del dispositivo. Sigue siendo un borrador local: no registra una estrategia ni solicita ejecución.',
                style:
                    TextStyle(color: qrosMuted, height: 1.5, fontSize: 13),
              ),
              const SizedBox(height: 23),
              TextFormField(
                key: const Key('draft-title'),
                controller: _title,
                maxLength: 72,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                    labelText: 'Título de la hipótesis',
                    hintText: 'Ej. Recuperación de mínimo M15'),
                validator: (s) => s == null || s.trim().length < 3
                    ? 'Introduce al menos 3 caracteres.'
                    : null,
              ),
              const SizedBox(height: 14),
              TextFormField(
                key: const Key('draft-thesis'),
                controller: _thesis,
                minLines: 3,
                maxLines: 5,
                maxLength: 500,
                decoration: const InputDecoration(
                  labelText: 'Mecanismo causal propuesto',
                  alignLabelWithHint: true,
                  hintText:
                      'Describe qué condición se observaría antes de la entrada.',
                ),
                validator: (s) => s == null || s.trim().length < 10
                    ? 'Describe la hipótesis con al menos 10 caracteres.'
                    : null,
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                key: const Key('draft-symbol'),
                initialValue: _symbol,
                decoration: const InputDecoration(labelText: 'Activo'),
                items: [
                  for (final s in ResearchStore.symbols)
                    DropdownMenuItem(value: s, child: Text(s)),
                ],
                onChanged: (s) => setState(() => _symbol = s ?? _symbol),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                key: const Key('draft-side'),
                initialValue: _side,
                decoration: const InputDecoration(labelText: 'Dirección'),
                items: [
                  for (final s in ResearchStore.sides)
                    DropdownMenuItem(value: s, child: Text(s)),
                ],
                onChanged: (s) => setState(() => _side = s ?? _side),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                key: const Key('draft-timeframe'),
                initialValue: _timeframe,
                decoration: const InputDecoration(labelText: 'Timeframe'),
                items: [
                  for (final s in ResearchStore.timeframes)
                    DropdownMenuItem(value: s, child: Text(s)),
                ],
                onChanged: (s) =>
                    setState(() => _timeframe = s ?? _timeframe),
              ),
              const SizedBox(height: 23),
              Container(
                padding: const EdgeInsets.all(13),
                decoration: BoxDecoration(
                    color: const Color(0xFF302D27),
                    borderRadius: BorderRadius.circular(12)),
                child: const Text(
                  'La app NO puede declarar PASS, congelar contratos científicos, abrir holdout ni enviar órdenes.',
                  style:
                      TextStyle(color: qrosAmber, fontSize: 12, height: 1.5),
                ),
              ),
              const SizedBox(height: 21),
              FilledButton.icon(
                key: const Key('new-project-submit'),
                onPressed: _busy ? null : _save,
                icon: Icon(_editing ? Icons.save_as_outlined : Icons.save_outlined),
                label: Text(_busy
                    ? 'Guardando…'
                    : _editing
                        ? 'Guardar cambios'
                        : 'Guardar borrador local'),
                style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(52)),
              ),
            ],
          ),
        ),
      );
}
