import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/g6_demo_transport.dart';
import '../core/g6_signed_snapshot.dart';

/// Explicit TEST_ONLY, no production endpoint or proof of operationally
/// independent custody. All tokens and test CA material remain in widget RAM.
class G6ProofScreen extends StatefulWidget {
  const G6ProofScreen({super.key,this.transport});
  final G6SyntheticTransport? transport;
  @override State<G6ProofScreen> createState()=>_G6ProofScreenState();
}

class _G6ProofScreenState extends State<G6ProofScreen> {
  late final G6SnapshotGateway _gateway=G6SnapshotGateway(transport:widget.transport);
  final _origin=TextEditingController(),_token=TextEditingController(),
    _tenant=TextEditingController(),_project=TextEditingController(),
    _campaign=TextEditingController(),_wid=TextEditingController(),
    _publicKey=TextEditingController(),_testCa=TextEditingController();
  bool _busy=false; String? _error; G6VerifiedSnapshot? _result;
  @override void dispose(){for(final c in [_origin,_token,_tenant,_project,_campaign,_wid,_publicKey,_testCa]){c.clear();c.dispose();} super.dispose();}

  Future<void> _offline() async {
    if(_busy)return;
    setState((){_busy=true;_result=null;_error=null;});
    try {
      final wire=await rootBundle.load('assets/g6_signed_snapshot.json');
      final trust=await rootBundle.loadString('assets/g6_offline_trust.json');
      final rawTrust=jsonDecode(trust) as Map<String,dynamic>;
      final pin=G6TrustPin.fromOfflineFixture(rawTrust);
      final verifier=G6SnapshotVerifier(trustPin:pin,
        expectedWireSha256:rawTrust['snapshot_wire_sha256'] as String);
      final checked=await verifier.verify(wire.buffer.asUint8List());
      if(mounted)setState(()=>_result=checked);
    } catch (_) {if(mounted)setState(()=>_error='Ejemplo sintético rechazado. Revisa los activos y sus firmas.');}
    finally {if(mounted)setState(()=>_busy=false);}
  }

  Future<void> _fetch() async {
    if(_busy)return;
    setState((){_busy=true;_result=null;_error=null;});
    try {
      final pin=G6TrustPin(tenant:_tenant.text.trim(),project:_project.text.trim(),
        campaign:_campaign.text.trim(),witnessId:_wid.text.trim(),
        publicKeyB64:_publicKey.text.trim());
      final checked=await _gateway.fetch(
        origin:_origin.text,token:_token.text,outOfBandPin:pin,testCaPem:_testCa.text);
      if(mounted)setState(()=>_result=checked);
    } catch (_) {if(mounted)setState(()=>_error='Verificación denegada: TLS, proyecto, pin o recibo inválido.');}
    finally {if(mounted)setState(()=>_busy=false);}
  }

  Widget _field(String id,String label,TextEditingController controller,
     {bool secret=false,int lines=1})=>Padding(padding:const EdgeInsets.only(bottom:12),child:TextField(
      key:Key(id),controller:controller,obscureText:secret,autocorrect:false,
      enableSuggestions:false,maxLines:lines,
      decoration:InputDecoration(labelText:label)));

  @override Widget build(BuildContext context)=>Scaffold(
    appBar:AppBar(title:const Text('Recibos G5 · G6 TEST_ONLY')),
    body:ListView(key:const Key('g6-screen'),padding:const EdgeInsets.all(18),children:[
      const Text('PRUEBA SINTÉTICA · NO ES AUTORIDAD CIENTÍFICA',
        style:TextStyle(color:Color(0xFFFBD67A),fontWeight:FontWeight.bold)),
      const SizedBox(height:12),
      const Text('Verifica localmente una muestra congelada con una firma Ed25519 y un SHA-256 independiente. No contiene claves privadas.'),
      const SizedBox(height:14),
      FilledButton.icon(key:const Key('g6-offline'),onPressed:_busy?null:_offline,
        icon:const Icon(Icons.verified_user_outlined),
        label:const Text('Verificar ejemplo firmado sin red')),
      if(_busy)const LinearProgressIndicator(),
      if(_error!=null)Padding(padding:const EdgeInsets.only(top:12),
        child:Text(_error!,key:const Key('g6-denied'),style:const TextStyle(color:Color(0xFFF28F94)))),
      if(_result!=null)Card(key:const Key('g6-verified'),child:Padding(
        padding:const EdgeInsets.all(16),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
          const Text('RECIBO SINTÉTICO VALIDADO',style:TextStyle(color:Color(0xFF36D7B7),fontWeight:FontWeight.bold)),
          Text('Cliente: ${_result!.tenant} · proyecto: ${_result!.project}'),
          Text('Secuencia: ${_result!.head.sequence}'),
          SelectableText('SHA-256: ${_result!.head.sha256}',style:const TextStyle(fontSize:11)),
          const Text('CUSTODIA EXTERNA: NO DESPLEGADA. 0 backtests económicos. No operar.',
            style:TextStyle(color:Color(0xFFFBD67A))),
        ]))),
      const Divider(height:34),
      const Text('Conexión local voluntaria G5',style:TextStyle(fontSize:17,fontWeight:FontWeight.w700)),
      const SizedBox(height:8),
      const Text('Solo HTTPS localhost o 127.0.0.1. En Android requiere enlace local, certificado de pruebas y pin Ed25519 obtenido por canal independiente. No existe servidor público habilitado.'),
      const SizedBox(height:14),
      _field('g6-origin','Servidor local https://127.0.0.1:puerto',_origin),
      _field('g6-tenant','Cliente',_tenant),
      _field('g6-project','Proyecto',_project),
      _field('g6-campaign','Campaña',_campaign),
      _field('g6-witness','ID testigo',_wid),
      _field('g6-public-key','Clave pública Ed25519, Base64',_publicKey),
      _field('g6-token','Token temporal (no se almacena)',_token,secret:true),
      _field('g6-ca','Certificado CA PEM de pruebas (opcional)',_testCa,lines:3),
      OutlinedButton.icon(key:const Key('g6-connect'),onPressed:_busy?null:_fetch,
         icon:const Icon(Icons.lock_outline),label:const Text('Consultar muestra local firmada')),
      const SizedBox(height:20),
      const Text('Sin datos de broker, órdenes ni aprobación científica.',style:TextStyle(fontSize:12)),
    ]));
}
