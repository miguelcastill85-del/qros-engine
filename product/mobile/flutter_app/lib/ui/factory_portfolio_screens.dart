import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/universe_store.dart';

const _teal = Color(0xFF36D7B7);
const _muted = Color(0xFFA7B9CF);
const _panel = Color(0xFF142339);

class UniverseFactoryScreen extends StatelessWidget {
  const UniverseFactoryScreen({
    super.key,
    required this.store,
    required this.onOpenIdea,
    required this.onOpenJob,
  });
  final UniverseSessionStore store;
  final VoidCallback onOpenIdea;
  final VoidCallback onOpenJob;

  Future<void> _copyDraft(BuildContext context) async {
    final draft = store.latest;
    if (draft == null) return;
    final contract = await draft.blueprint.contractPreview();
    if (!context.mounted) return;
    final export = {
      'source_class': 'SYNTHETIC_DRAFT_NOT_FROZEN',
      'user_title': draft.title,
      'user_thesis': draft.thesis,
      'typed_universe': draft.blueprint.canonicalObject(),
      'search_space_sha256': draft.searchSpaceSha256,
      'toy_enumeration_sha256': draft.toyEnumerationSha256,
      'strategy_contract_preview': contract,
      'economic_tests': 0,
      'scientific_approval': false,
    };
    await Clipboard.setData(ClipboardData(text: const JsonEncoder.withIndent('  ').convert(export)));
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Solo el borrador sintético fue copiado. Sin recibo científico.'),
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final latest = store.latest;
    return ListView(key: const Key('factory-screen'),padding: const EdgeInsets.fromLTRB(16, 20, 16, 32),children: [
      const Text('STRATEGY FACTORY · G12 TEST_ONLY',style: TextStyle(color: _teal,letterSpacing: 1.2,fontSize: 11,fontWeight:FontWeight.w800)),
      const SizedBox(height: 9),
      const Text('Tu universo, bajo control.',style: TextStyle(fontSize: 27,fontWeight: FontWeight.w900)),
      const SizedBox(height: 12),
      const Text('Las etapas aún no ejecutadas permanecen cerradas. Ningún progreso se inventa.',style:TextStyle(color:_muted,height:1.4)),
      const SizedBox(height: 22),
      if (latest == null) ...[
        _FactoryPanel(child: Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
          const Text('No hay universos analizados en esta sesión.',style:TextStyle(fontWeight:FontWeight.w700)),
          const SizedBox(height:11),
          const Text('La primera acción es definir una hipótesis y sus dominios de búsqueda.',style:TextStyle(color:_muted)),
          const SizedBox(height:16),
          FilledButton.icon(onPressed:onOpenIdea,icon:const Icon(Icons.lightbulb_outline),label:const Text('Crear hipótesis')),
        ])),
      ] else ...[
        _FactoryPanel(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
          const Text('BORRADOR LOCAL · NO CONGELADO',style:TextStyle(color:Color(0xFFFBD67A),fontSize:11,fontWeight:FontWeight.w800)),
          const SizedBox(height:10),
          Text(latest.title,style:const TextStyle(fontSize:20,fontWeight:FontWeight.w800)),
          const SizedBox(height:6),
          Text(latest.thesis,style:const TextStyle(color:_muted,height:1.4)),
          const SizedBox(height:20),
          _row('Nacimiento bruto', '${latest.blueprint.rawBirths}'),
          _row('Únicos tras deduplicación', 'NO CALCULADO'),
          _row('Backtests económicos', '0'),
          _row('Holdout', 'CERRADO'),
          _row('Estado científico', 'NINGUNO'),
          const Divider(height:28),
          const Text('HUELLA DEL UNIVERSO',style: TextStyle(color:_muted,fontSize:10,letterSpacing:1)),
          const SizedBox(height:6),
          SelectableText(latest.searchSpaceSha256,key:const Key('factory-verified-hash'),style:const TextStyle(fontSize:12,color:_teal)),
          const SizedBox(height:13),
          OutlinedButton.icon(key:const Key('g1-export'),onPressed:()=>_copyDraft(context),icon:const Icon(Icons.copy_outlined),label:const Text('Copiar contrato de prueba')),
          const SizedBox(height:10),
          FilledButton.icon(
            key:const Key('g12-open-job'),
            onPressed:onOpenJob,
            icon:const Icon(Icons.cloud_sync_outlined),
            label:const Text('Abrir trabajo sintético G12'),
          ),
        ])),
      ],
      const SizedBox(height:21),
      const _StageRow(number:'01',title:'Contrato tipado',state:'BORRADOR',ready:true),
      const _StageRow(number:'02',title:'Enumerador independiente',state:'G2 PENDIENTE'),
      const _StageRow(number:'03',title:'Auditoría de datos',state:'DATOS SINTÉTICOS'),
      const _StageRow(number:'04',title:'Backtest cronológico',state:'NO EJECUTADO'),
      const _StageRow(number:'05',title:'RISE-Q y holdout',state:'CERRADO'),
      const _StageRow(number:'06',title:'Paridad MT5',state:'NO EJECUTADO'),
      const SizedBox(height:15),
      const Text('G12 sólo prueba infraestructura de trabajos reanudables. Los millones de configuraciones y el motor real siguen cerrados hasta validar escala, costes, autoridad y paridad.',style:TextStyle(fontSize:12,color:_muted,height:1.5)),
    ]);
  }

  Widget _row(String key,String value)=>Padding(padding:const EdgeInsets.symmetric(vertical:7),child:Row(children:[
    Expanded(child:Text(key,style:const TextStyle(color:_muted,fontSize:12))),
    Flexible(child:Text(value,textAlign:TextAlign.right,style:const TextStyle(fontWeight:FontWeight.w700,fontSize:12))),
  ]));
}

class _FactoryPanel extends StatelessWidget {
  const _FactoryPanel({required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context)=>Container(
    padding:const EdgeInsets.all(19),
    decoration:BoxDecoration(color:_panel,border:Border.all(color:const Color(0xFF33485E)),borderRadius:BorderRadius.circular(20)),child:child);
}

class _StageRow extends StatelessWidget {
  const _StageRow({required this.number,required this.title,required this.state,this.ready=false});
  final String number,title,state;
  final bool ready;
  @override
  Widget build(BuildContext context)=>Padding(padding:const EdgeInsets.only(bottom:9),child:_FactoryPanel(child:Row(children:[
    Text(number,style:TextStyle(color:ready?_teal:_muted,fontSize:14,fontWeight:FontWeight.w900)),
    const SizedBox(width:13),
    Expanded(child:Text(title,style:const TextStyle(fontWeight:FontWeight.w600))),
    const SizedBox(width:8),
    Text(state,style:TextStyle(color:ready?_teal:_muted,fontWeight:FontWeight.w700,fontSize:10)),
  ])));
}

class PortfolioLabPlaceholder extends StatelessWidget {
  const PortfolioLabPlaceholder({super.key});
  @override
  Widget build(BuildContext context)=>ListView(key:const Key('portfolio-screen'),padding:const EdgeInsets.all(18),children:[
    const Text('PORTFOLIO LAB',style:TextStyle(color:_teal,fontSize:11,letterSpacing:1.3,fontWeight:FontWeight.w800)),
    const SizedBox(height:9),
    const Text('Alfa marginal.',style:TextStyle(fontWeight:FontWeight.w900,fontSize:29)),
    const SizedBox(height:12),
    const Text('Aquí compararemos genealogías, solapamiento de operaciones, concentración, riesgo y aporte incremental.',style:TextStyle(color:_muted,height:1.5)),
    const SizedBox(height:25),
    const _FactoryPanel(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
      Text('NINGÚN CANDIDATO APROBADO',style:TextStyle(color:Color(0xFFFBD67A),fontSize:11,fontWeight:FontWeight.w800)),
      SizedBox(height:15),
      Icon(Icons.hub_outlined,color:_teal,size:35),
      SizedBox(height:15),
      Text('El análisis marginal requiere señales ejecutadas, trades verificados y períodos adecuados.',style:TextStyle(height:1.5)),
      SizedBox(height:13),
      Text('No asigna riesgo ni realiza órdenes. Módulo pendiente de integración.',style:TextStyle(color:_muted,fontSize:12)),
    ])),
  ]);
}
