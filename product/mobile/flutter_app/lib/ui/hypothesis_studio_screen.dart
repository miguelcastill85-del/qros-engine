import 'package:flutter/material.dart';
import '../core/universe_ir.dart';
import '../core/universe_store.dart';

const _teal = Color(0xFF36D7B7);
const _muted = Color(0xFFA7B9CF);
const _panel = Color(0xFF142339);
const _outline = Color(0xFF33485E);

class HypothesisStudioScreen extends StatefulWidget {
  const HypothesisStudioScreen({super.key, required this.store, required this.onOpenFactory});
  final UniverseSessionStore store;
  final VoidCallback onOpenFactory;
  @override
  State<HypothesisStudioScreen> createState() => _HypothesisStudioScreenState();
}

class _HypothesisStudioScreenState extends State<HypothesisStudioScreen> {
  final _title = TextEditingController(text: 'Compresión y ruptura intradiaria');
  final _thesis = TextEditingController(
    text: 'Investigar si una compresión cerrada seguida de ruptura presenta continuidad tras costes.',
  );
  String _symbol = 'SIM_XAUUSD';
  final _sides = <String>{'BUY', 'SELL'};
  final _tfs = <String>{'M5', 'M15'};
  final _lookbacks = <int>{5, 10, 15};
  final _confirmations = <int>{1, 2};
  final _stops = <String>{'1/1', '3/2', '2/1'};
  final _exits = <int>{8, 12};
  bool _busy = false;
  String? _error;
  UniverseSessionDraft? _lastSaved;

  @override
  void dispose() {
    _title.dispose();
    _thesis.dispose();
    super.dispose();
  }

  UniverseBlueprint get _draft => UniverseBlueprint(
    symbol: _symbol,
    sides: _sides.toList(),
    timeframes: _tfs.toList(),
    lookbackBars: _lookbacks.toList(),
    confirmationBars: _confirmations.toList(),
    stopRatios: _stops.toList(),
    maximumHoldingBars: _exits.toList(),
  );

  Future<void> _analyze() async {
    if (_busy) return;
    setState(() { _busy = true; _error = null; });
    try {
      final saved = await widget.store.save(
        title: _title.text, thesis: _thesis.text, blueprint: _draft,
      );
      if (!mounted) return;
      setState(() { _lastSaved = saved; });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text(
        'Universo sintáctico calculado y borrador creado. Sin backtesting.',
      )));
    } on UniverseValidationError catch (e) {
      if (mounted) setState(() => _error = _readableError(e.code));
    } catch (_) {
      if (mounted) setState(() => _error = 'No se pudo calcular el universo. Ningún estado fue aprobado.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  static String _readableError(String code) {
    if (code.startsWith('EMPTY_')) return 'Selecciona al menos un valor por eje.';
    if (code == 'THESIS_LENGTH') return 'Escribe una hipótesis entre 10 y 500 caracteres.';
    if (code == 'TITLE_LENGTH') return 'El título debe tener entre 3 y 72 caracteres.';
    return 'Contrato rechazado por el validador tipado: $code';
  }

  Widget _section(String number, String title, String subtitle, Widget child) =>
    Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(color: _panel, borderRadius: BorderRadius.circular(20), border: Border.all(color: _outline)),
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            height: 27, width: 27, alignment: Alignment.center,
            decoration: BoxDecoration(color: const Color(0xFF194D49), borderRadius: BorderRadius.circular(9)),
            child: Text(number, style: const TextStyle(color: _teal, fontWeight: FontWeight.w800)),
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800))),
        ]),
        const SizedBox(height: 6),
        Text(subtitle, style: const TextStyle(color: _muted, fontSize: 12, height: 1.4)),
        const SizedBox(height: 15),
        child,
      ]),
    );

  Widget _chips<T>(String keyPrefix, Iterable<T> all, Set<T> selected,
      String Function(T) label) => Wrap(
    spacing: 7, runSpacing: 8,
    children: [for (final value in all)
      FilterChip(
        key: Key('$keyPrefix-$value'),
        label: Text(label(value)),
        selected: selected.contains(value),
        showCheckmark: true,
        selectedColor: const Color(0xFF20544F),
        checkmarkColor: _teal,
        onSelected: (checked) => setState(() {
          if (checked) { selected.add(value); } else { selected.remove(value); }
          _lastSaved = null;
        }),
      ),
    ],
  );

  Widget _axis(String label, Widget child) => Padding(
    padding: const EdgeInsets.only(bottom: 13),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: const TextStyle(fontWeight: FontWeight.w700, color: _muted, fontSize: 12)),
      const SizedBox(height: 7), child,
    ]),
  );

  @override
  Widget build(BuildContext context) {
    final rawBirths = _draft.rawBirths;
    final empty = _sides.isEmpty || _tfs.isEmpty || _lookbacks.isEmpty ||
      _confirmations.isEmpty || _stops.isEmpty || _exits.isEmpty;
    return ListView(
      key: const Key('hypothesis-studio-screen'),
      padding: const EdgeInsets.fromLTRB(16, 13, 16, 36),
      children: [
        const Text('HYPOTHESIS STUDIO · G1', style: TextStyle(color: _teal, letterSpacing: 1.3, fontSize: 11, fontWeight: FontWeight.w800)),
        const SizedBox(height: 8),
        const Text('De una idea a un universo.', style: TextStyle(fontSize: 27, height: 1.15, fontWeight: FontWeight.w900)),
        const SizedBox(height: 10),
        const Text('Define reglas observables, cruza dominios finitos y conoce el tamaño del experimento antes de investigar.',
          style: TextStyle(color: _muted, height: 1.5)),
        const SizedBox(height: 13),
        const _TrustLine(label: 'SOLO SINTÉTICO · SIN PnL · HOLDOUT CERRADO'),
        const SizedBox(height: 20),
        _section('1', 'Hipótesis', 'El texto explica tu idea. No se congela ni se incluye todavía en el hash técnico.',
          Column(children: [
            TextField(key: const Key('g1-title'), controller: _title, maxLength: 72,
              onChanged: (_) => setState(() => _lastSaved = null),
              decoration: const InputDecoration(labelText: 'Nombre del experimento')),
            const SizedBox(height: 12),
            TextField(key: const Key('g1-thesis'), controller: _thesis,
              minLines: 3, maxLines: 5, maxLength: 500,
              onChanged: (_) => setState(() => _lastSaved = null),
              decoration: const InputDecoration(labelText: 'Hipótesis que intentaremos refutar')),
          ]),
        ),
        _section('2', 'Contexto y señales', 'Cualquier observación debe provenir de la última vela cerrada.',
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _axis('Activo de demostración', DropdownButtonFormField<String>(
              key: const Key('g1-symbol'), initialValue: _symbol,
              items: const [
                DropdownMenuItem(value: 'SIM_XAUUSD', child: Text('XAUUSD · sintético')),
                DropdownMenuItem(value: 'SIM_NQX', child: Text('NQX · sintético')),
              ],
              onChanged: (x) { if (x != null) setState(() { _symbol = x; _lastSaved = null; }); },
            )),
            _axis('Dirección', _chips('g1-side', const ['BUY', 'SELL'], _sides, (x) => x)),
            _axis('Temporalidades', _chips('g1-tf', const ['M5', 'M15'], _tfs, (x) => x)),
            _axis('Compresión: velas anteriores', _chips('g1-lookback', const [5,10,15], _lookbacks, (x) => '$x barras')),
            _axis('Confirmación: velas cerradas', _chips('g1-confirmation', const [1,2], _confirmations, (x) => '$x')),
          ]),
        ),
        _section('3', 'Riesgo y salida', 'Rangos discretos racionales. Entradas BUY Ask y SELL Bid; nunca overnight.',
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _axis('Stop ATR · múltiplo racional', _chips('g1-stop', const ['1/1','3/2','2/1'], _stops, (x) => '$x ATR')),
            _axis('Salida máxima en barras', _chips('g1-exit', const [8,12], _exits, (x) => '$x')),
          ]),
        ),
        _section('4', 'Arquitecto del universo', 'Solo contamos combinaciones sintácticas, no estrategias únicas ni backtests.',
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(color: const Color(0xFF0B192C), borderRadius: BorderRadius.circular(16)),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('NACIMIENTOS BRUTOS', style: TextStyle(color: _muted, letterSpacing: 1, fontSize: 10)),
                const SizedBox(height: 6),
                Text(empty ? '—' : '$rawBirths', key: const Key('g1-raw-count'),
                  style: const TextStyle(color: _teal, fontSize: 35, fontWeight: FontWeight.w900)),
                const SizedBox(height: 7),
                const Text('Únicos reales: pendiente · Pruebas económicas: 0',
                  style: TextStyle(color: _muted, fontSize: 11)),
              ]),
            ),
            const SizedBox(height: 13),
            const _TrustLine(label: 'UNIVERSO NO CONGELADO · SIN APROBACIÓN'),
            if (_error != null) ...[
              const SizedBox(height: 13),
              Text(_error!, key: const Key('g1-error'), style: const TextStyle(color: Color(0xFFF28F94))),
            ],
            const SizedBox(height: 17),
            FilledButton.icon(
              key: const Key('g1-analyze'),
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(50)),
              onPressed: _busy ? null : _analyze,
              icon: const Icon(Icons.account_tree_outlined),
              label: Text(_busy ? 'Validando…' : 'Analizar y guardar borrador'),
            ),
            if (_lastSaved != null) ...[
              const SizedBox(height: 16),
              Text('SHA-256 del universo sintáctico: ${_lastSaved!.searchSpaceSha256}',
                key: const Key('g1-saved-hash'), style: const TextStyle(color: _muted, fontSize: 11)),
              const SizedBox(height: 10),
              OutlinedButton.icon(key: const Key('g1-open-factory'),
                onPressed: widget.onOpenFactory,
                icon: const Icon(Icons.precision_manufacturing_outlined),
                label: const Text('Abrir Fábrica')),
            ],
          ]),
        ),
      ],
    );
  }
}

class _TrustLine extends StatelessWidget {
  const _TrustLine({required this.label});
  final String label;
  @override
  Widget build(BuildContext context) => Row(children: [
    const Icon(Icons.verified_user_outlined, color: Color(0xFFFBD67A), size: 16),
    const SizedBox(width: 8),
    Expanded(child: Text(label, style: const TextStyle(color: Color(0xFFFBD67A), fontSize: 10, fontWeight: FontWeight.w700))),
  ]);
}
