import 'draft_backup_screen.dart';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/research_store.dart';
import '../core/verified_demo.dart';
import '../core/g5_snapshot.dart';
import '../core/universe_store.dart';
import 'factory_portfolio_screens.dart';
import 'hypothesis_studio_screen.dart';
import 'verified_demo_screen.dart';
import 'g5_snapshot_screen.dart';
import 'new_project_screen.dart';

const qrosBackground = Color(0xFF09111F);
const qrosPanel = Color(0xFF142339);
const qrosStroke = Color(0xFF33485E);
const qrosTeal = Color(0xFF36D7B7);
const qrosMuted = Color(0xFFA7B9CF);
const qrosAmber = Color(0xFFFBD67A);

enum _LegacyDestination { projects, history, security }

class QrosShell extends StatefulWidget {
  const QrosShell({super.key, required this.store,
    required this.universeStore, required this.demoGateway, required this.g5Gateway});
  final ResearchStore store;
  final UniverseSessionStore universeStore;
  final DemoGateway demoGateway;
  final G5SnapshotGateway g5Gateway;

  @override
  State<QrosShell> createState() => _QrosShellState();
}

class _QrosShellState extends State<QrosShell> {
  int _page = 0;

  Future<void> _newProject() async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => NewProjectScreen(store: widget.store)),
    );
    if (!mounted || created != true) return;
    _openLegacy(_LegacyDestination.projects);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Borrador local creado. No está congelado ni validado.')),
    );
  }

  void _openLegacy(_LegacyDestination destination) {
    final title = switch (destination) {
      _LegacyDestination.projects => 'Proyectos',
      _LegacyDestination.history => 'Historial',
      _LegacyDestination.security => 'Seguridad',
    };
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => Scaffold(
      appBar: AppBar(title: Text(title)),
      body: AnimatedBuilder(animation: widget.store, builder: (_, __) => switch (destination) {
        _LegacyDestination.projects => _ProjectsPage(store: widget.store, onNewProject: _newProject),
        _LegacyDestination.history => _HistoryPage(store: widget.store),
        _LegacyDestination.security => _EvidencePage(store: widget.store, onOpenDemo: () =>
          Navigator.of(context).push(MaterialPageRoute(
            builder: (_) => VerifiedDemoScreen(gateway: widget.demoGateway))), onOpenG5: () =>
          Navigator.of(context).push(MaterialPageRoute(
            builder: (_) => G5SnapshotScreen(gateway: widget.g5Gateway)))),
      }),
    )));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 74,
        title: const Row(children: [
          QrosMark(), SizedBox(width: 10),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('QROS', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, letterSpacing: 1)),
            Text('MOBILE RESEARCH STUDIO', style: TextStyle(fontSize: 9, letterSpacing: 1.5, color: qrosMuted)),
          ]),
        ]),
        actions: [
          const Center(child: StatusPill(label: 'TEST_ONLY', color: qrosAmber)),
          PopupMenuButton<_LegacyDestination>(
            key: const Key('more-actions'),
            tooltip: 'Más módulos y seguridad',
            icon: const Icon(Icons.more_vert),
            onSelected: _openLegacy,
            itemBuilder: (_) => const [
              PopupMenuItem(value: _LegacyDestination.projects, child: Text('Proyectos')),
              PopupMenuItem(value: _LegacyDestination.history, child: Text('Historial')),
              PopupMenuItem(value: _LegacyDestination.security, child: Text('Seguridad')),
            ],
          ),
        ],
      ),
      body: AnimatedBuilder(
        animation: Listenable.merge([widget.store, widget.universeStore]),
        builder: (context, _) => switch (_page) {
          0 => _HomePage(store: widget.store, onNewProject: _newProject,
             onOpenProjects: () => _openLegacy(_LegacyDestination.projects),
             onOpenIdea: () => setState(() => _page = 1)),
          1 => HypothesisStudioScreen(store: widget.universeStore,
             onOpenFactory: () => setState(() => _page = 2)),
          2 => UniverseFactoryScreen(store: widget.universeStore,
             onOpenIdea: () => setState(() => _page = 1)),
          3 => _EvidencePage(store: widget.store, onOpenDemo: () =>
             Navigator.of(context).push(MaterialPageRoute(
               builder: (_) => VerifiedDemoScreen(gateway: widget.demoGateway))), onOpenG5: () =>
             Navigator.of(context).push(MaterialPageRoute(
               builder: (_) => G5SnapshotScreen(gateway: widget.g5Gateway)))),
          _ => const PortfolioLabPlaceholder(),
        },
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _page,
        onDestinationSelected: (next) => setState(() => _page = next),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'Inicio'),
          NavigationDestination(icon: Icon(Icons.lightbulb_outline), selectedIcon: Icon(Icons.lightbulb), label: 'Hipótesis'),
          NavigationDestination(icon: Icon(Icons.precision_manufacturing_outlined), selectedIcon: Icon(Icons.precision_manufacturing), label: 'Fábrica'),
          NavigationDestination(icon: Icon(Icons.fact_check_outlined), selectedIcon: Icon(Icons.fact_check), label: 'Evidencias'),
          NavigationDestination(icon: Icon(Icons.hub_outlined), selectedIcon: Icon(Icons.hub), label: 'Portafolio'),
        ],
      ),
    );
  }
}

class QrosMark extends StatelessWidget {
  const QrosMark({super.key});
  @override
  Widget build(BuildContext context) => Container(
    width: 40,
    height: 40,
    alignment: Alignment.center,
    decoration: BoxDecoration(
      color: const Color(0xFF173C40),
      border: Border.all(color: qrosTeal),
      borderRadius: BorderRadius.circular(11),
    ),
    child: const Text('Q', style: TextStyle(color: qrosTeal, fontSize: 26, fontWeight: FontWeight.w900)),
  );
}

class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.label, required this.color});
  final String label;
  final Color color;
  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(30),
      border: Border.all(color: color),
      color: const Color(0xFF18283C),
    ),
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      child: Text(label, style: TextStyle(fontSize: 10, letterSpacing: .5, color: color, fontWeight: FontWeight.bold)),
    ),
  );
}

class QrosPanel extends StatelessWidget {
  const QrosPanel({super.key, required this.child, this.padding = const EdgeInsets.all(18)});
  final Widget child;
  final EdgeInsets padding;
  @override
  Widget build(BuildContext context) => Container(
    decoration: BoxDecoration(
      color: qrosPanel,
      borderRadius: BorderRadius.circular(18),
      border: Border.all(color: qrosStroke),
    ),
    padding: padding,
    child: child,
  );
}

class SectionHeading extends StatelessWidget {
  const SectionHeading(this.label, {super.key, this.trailing});
  final String label;
  final String? trailing;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Row(
      children: [
        Expanded(child: Text(label, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800))),
        if (trailing != null) Text(trailing!, style: const TextStyle(color: qrosMuted, fontSize: 11)),
      ],
    ),
  );
}

class _HomePage extends StatelessWidget {
  const _HomePage({required this.store, required this.onNewProject, required this.onOpenProjects, required this.onOpenIdea});
  final ResearchStore store;
  final VoidCallback onNewProject;
  final VoidCallback onOpenProjects;
  final VoidCallback onOpenIdea;

  @override
  Widget build(BuildContext context) => ListView(
    key: const Key('home-screen'),
    padding: const EdgeInsets.fromLTRB(18, 12, 18, 24),
    children: [
      const _OfflineRibbon(),
      const SizedBox(height: 20),
      QrosPanel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('STRATEGY FACTORY · G1 · TEST_ONLY', style: TextStyle(color: qrosTeal, fontSize: 11, letterSpacing: 1.3, fontWeight: FontWeight.w700)),
            const SizedBox(height: 14),
            const Text('Investiga con evidencia,\nno con promesas.', style: TextStyle(fontSize: 26, height: 1.18, fontWeight: FontWeight.w900)),
            const SizedBox(height: 12),
            const Text(
              'Escribe una idea, construye reglas observables y explora un universo sintético finito, sin ejecutar backtests económicos.',
              style: TextStyle(color: qrosMuted, height: 1.5, fontSize: 13),
            ),
            const SizedBox(height: 18),
            FilledButton.icon(
              key: const Key('open-idea-action'),
              onPressed: onOpenIdea,
              icon: const Icon(Icons.account_tree_outlined),
              label: const Text('Explorar una hipótesis'),
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(49)),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              key: const Key('new-project-action'),
              onPressed: onNewProject,
              icon: const Icon(Icons.add_circle_outline),
              label: const Text('Nueva hipótesis'),
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(49)),
            ),
          ],
        ),
      ),
      const SizedBox(height: 24),
      const SectionHeading('Tu laboratorio', trailing: 'Pruebas sintéticas'),
      Row(
        children: [
          Expanded(child: _MetricCard(label: 'Proyectos', value: '${store.projects.length}', footnote: 'Demo y borradores', icon: Icons.folder_open_outlined)),
          const SizedBox(width: 10),
          Expanded(child: _MetricCard(label: 'Backtests reales', value: '0', footnote: 'Motor desconectado', icon: Icons.query_stats_outlined)),
        ],
      ),
      const SizedBox(height: 10),
      const Row(
        children: [
          Expanded(child: _MetricCard(label: 'Holdout', value: 'CERRADO', footnote: 'Sin autorización', icon: Icons.lock_outline)),
          SizedBox(width: 10),
          Expanded(child: _MetricCard(label: 'MT5', value: 'NO', footnote: 'Sin integración', icon: Icons.shield_outlined)),
        ],
      ),
      const SizedBox(height: 24),
      const SectionHeading('Investigación de ejemplo'),
      _ProjectCard(project: store.projects.firstWhere((p) => p.isSample), onTap: onOpenProjects),
      const SizedBox(height: 18),
      const _Notice(text: 'Ninguna pantalla contiene resultados económicos ni constituye una aprobación científica.'),
    ],
  );
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.label, required this.value, required this.footnote, required this.icon});
  final String label;
  final String value;
  final String footnote;
  final IconData icon;
  @override
  Widget build(BuildContext context) => QrosPanel(
    padding: const EdgeInsets.all(14),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(icon, color: qrosTeal, size: 20),
      const SizedBox(height: 12),
      Text(label, style: const TextStyle(color: qrosMuted, fontSize: 12)),
      const SizedBox(height: 5),
      FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text(value, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900))),
      const SizedBox(height: 3),
      Text(footnote, style: const TextStyle(fontSize: 10, color: qrosMuted)),
    ]),
  );
}

class _OfflineRibbon extends StatelessWidget {
  const _OfflineRibbon();
  @override
  Widget build(BuildContext context) => const Row(
    children: [
      Icon(Icons.circle, color: qrosTeal, size: 9),
      SizedBox(width: 8),
      Expanded(child: Text('Modo offline · Sin datos de broker', style: TextStyle(color: qrosMuted, fontSize: 11))),
      Icon(Icons.signal_wifi_off_rounded, color: qrosMuted, size: 17),
    ],
  );
}

class _ProjectsPage extends StatelessWidget {
  const _ProjectsPage({required this.store, required this.onNewProject});
  final ResearchStore store;
  final VoidCallback onNewProject;
  @override
  Widget build(BuildContext context) => ListView(
    key: const Key('projects-screen'),
    padding: const EdgeInsets.fromLTRB(18, 16, 18, 24),
    children: [
      const _OfflineRibbon(),
      const SizedBox(height: 20),
      SectionHeading('Proyectos', trailing: '${store.projects.length} locales / demo'),
      const _Notice(text: 'Los borradores no se guardan al cerrar esta versión de prueba. No equivalen a contratos congelados.'),
      const SizedBox(height: 16),
      FilledButton.icon(
        key: const Key('new-project-action'),
        onPressed: onNewProject,
        icon: const Icon(Icons.add),
        label: const Text('Crear borrador'),
      ),
      const SizedBox(height: 16),
      for (final item in store.projects) ...[
        _ProjectCard(
          project: item,
          onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ProjectDetailsScreen(project: item))),
        ),
        const SizedBox(height: 12),
      ],
    ],
  );
}

class _ProjectCard extends StatelessWidget {
  const _ProjectCard({required this.project, required this.onTap});
  final ResearchProject project;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => QrosPanel(
    child: InkWell(
      key: Key('project-${project.id}'),
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(project.id, style: const TextStyle(color: qrosTeal, fontSize: 11, letterSpacing: 1, fontWeight: FontWeight.w600))),
          StatusPill(label: project.isSample ? 'SIMULADO' : 'BORRADOR', color: project.isSample ? qrosAmber : qrosTeal),
        ]),
        const SizedBox(height: 9),
        Text(project.title, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18)),
        const SizedBox(height: 7),
        Text('${project.symbol} · ${project.side} · ${project.timeframe}', style: const TextStyle(color: qrosMuted)),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: Text(project.readableState, style: const TextStyle(color: qrosMuted, fontSize: 11))),
          const Icon(Icons.chevron_right, size: 19, color: qrosTeal),
        ]),
      ]),
    ),
  );
}

class ProjectDetailsScreen extends StatelessWidget {
  const ProjectDetailsScreen({super.key, required this.project});
  final ResearchProject project;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Expediente del proyecto')),
    body: ListView(padding: const EdgeInsets.all(18), children: [
      const _OfflineRibbon(),
      const SizedBox(height: 16),
      QrosPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(project.id, style: const TextStyle(color: qrosTeal, letterSpacing: 1.2)),
        const SizedBox(height: 8),
        Text(project.title, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900)),
        const SizedBox(height: 14),
        StatusPill(label: project.readableState, color: qrosAmber),
        const SizedBox(height: 16),
        _EvidenceLine(label: 'Activo', value: project.symbol),
        _EvidenceLine(label: 'Dirección', value: project.side),
        _EvidenceLine(label: 'Timeframe', value: project.timeframe),
      ])),
      const SizedBox(height: 20),
      const SectionHeading('Hipótesis'),
      QrosPanel(child: Text(project.thesis, style: const TextStyle(height: 1.55))),
      const SizedBox(height: 20),
      const SectionHeading('Verificación pendiente'),
      const QrosPanel(child: Column(children: [
        _EvidenceLine(label: 'Contrato tipado', value: 'NO CONGELADO'),
        _EvidenceLine(label: 'Backtest', value: 'NO EJECUTADO'),
        _EvidenceLine(label: 'Holdout', value: 'CERRADO'),
        _EvidenceLine(label: 'Aprobación', value: 'NINGUNA'),
      ])),
      const SizedBox(height: 20),
      const _Notice(text: 'Pantalla local TEST_ONLY. No existe SHA-256 verificado, certificado de ganancias ni vínculo con el motor QROS.'),
    ]),
  );
}

class _HistoryPage extends StatelessWidget {
  const _HistoryPage({required this.store});
  final ResearchStore store;
  @override
  Widget build(BuildContext context) => ListView(
    key: const Key('history-screen'),
    padding: const EdgeInsets.fromLTRB(18, 18, 18, 24),
    children: [
      const SectionHeading('Historial', trailing: 'Sesión local'),
      const _Notice(text: 'Eventos de interfaz, no recibos de ejecución. No hay registros reales del motor conectado.'),
      const SizedBox(height: 20),
      for (final item in store.projects) ...[
        QrosPanel(child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Icon(Icons.radio_button_checked, color: qrosTeal, size: 19),
          const SizedBox(width: 13),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(item.isSample ? 'Fixture demostrativa' : 'Borrador creado en esta sesión',
              style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 5),
            Text('${item.id} · ${item.title}', style: const TextStyle(color: qrosMuted, fontSize: 12)),
            const SizedBox(height: 7),
            Text(item.isSample ? 'Evento visual simulado' : 'Sin persistencia ni transición científica',
              style: const TextStyle(color: qrosAmber, fontSize: 11)),
          ])),
        ])),
        const SizedBox(height: 11),
      ],
    ],
  );
}

class _EvidencePage extends StatelessWidget {
  const _EvidencePage({required this.store, required this.onOpenDemo, required this.onOpenG5});
  final ResearchStore store;
  final VoidCallback onOpenDemo;
  final VoidCallback onOpenG5;

  Future<void> _copyEvidence(BuildContext context) async {
    final contents = const JsonEncoder.withIndent('  ').convert(store.exportSyntheticEvidence());
    await Clipboard.setData(ClipboardData(text: contents));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('JSON TEST_ONLY copiado. No es un recibo científico.')),
    );
  }

  @override
  Widget build(BuildContext context) => ListView(
    key: const Key('security-screen'),
    padding: const EdgeInsets.fromLTRB(18, 18, 18, 24),
    children: [
      const SectionHeading('Seguridad y evidencia'),
      const _Notice(text: 'El teléfono no tiene autoridad científica. Esta versión no se conecta con MT5 ni con servicios de pago.'),
      const SizedBox(height: 19),
      const QrosPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Contrato de seguridad', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17)),
        SizedBox(height: 17),
        _EvidenceLine(label: 'Motor conectado', value: 'NO'),
        _EvidenceLine(label: 'Datos de broker', value: 'NINGUNO'),
        _EvidenceLine(label: 'Permisos científicos', value: 'NINGUNO'),
        _EvidenceLine(label: 'HEAD externo confiable', value: 'PENDIENTE'),
        _EvidenceLine(label: 'Recibos autenticados', value: 'PENDIENTE'),
        _EvidenceLine(label: 'Holdout', value: 'CERRADO'),
        _EvidenceLine(label: 'Trading automático', value: 'DESACTIVADO'),
      ])),
      const SizedBox(height: 20),
      const SectionHeading('Consulta remota DEMO'),
      QrosPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Conectar solo lectura', style: TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        const Text('Requiere HTTPS, un token temporal y dos firmas criptográficas válidas. No abre permisos científicos.',
          style: TextStyle(fontSize: 12, color: qrosMuted)),
        const SizedBox(height: 14),
        OutlinedButton.icon(key: const Key('open-remote-demo'), onPressed: onOpenDemo,
          icon: const Icon(Icons.security_outlined), label: const Text('Consultar demo firmada')),
        const SizedBox(height: 10),
        FilledButton.icon(key: const Key('open-g6-snapshot'), onPressed: onOpenG5,
          icon: const Icon(Icons.verified_user_outlined), label: const Text('Verificar snapshot G5 · G9')),
      ])), 
      const SizedBox(height: 20),
      FilledButton.icon(
        key: const Key('open-draft-backup'),
        onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
          builder: (_) => DraftBackupScreen(store: store))),
        icon: const Icon(Icons.backup_outlined),
        label: const Text('Respaldar y recuperar borradores')),
      const SizedBox(height: 20),
      const SectionHeading('Exportación demostrativa'),
      QrosPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('JSON local de prueba', style: TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        const Text('Contiene solo la fixture y borradores introducidos en esta sesión. No incluye operaciones, claves ni métricas económicas.',
          style: TextStyle(color: qrosMuted, height: 1.5, fontSize: 13)),
        const SizedBox(height: 17),
        OutlinedButton.icon(
          key: const Key('copy-evidence-action'),
          onPressed: () => _copyEvidence(context),
          icon: const Icon(Icons.copy),
          label: const Text('Copiar JSON TEST_ONLY'),
        ),
      ])),
      const SizedBox(height: 18),
      const Text('QROS Mobile G9 · TEST_ONLY · No utilizar para operar.',
        style: TextStyle(color: qrosMuted, fontSize: 11, height: 1.5),
      ),
    ],
  );
}

class _EvidenceLine extends StatelessWidget {
  const _EvidenceLine({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Expanded(child: Text(label, style: const TextStyle(fontSize: 12, color: qrosMuted))),
      const SizedBox(width: 12),
      Flexible(child: Text(value, textAlign: TextAlign.end, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700))),
    ]),
  );
}

class _Notice extends StatelessWidget {
  const _Notice({required this.text});
  final String text;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(
      color: const Color(0xFF302D27),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: const Color(0xFF756142)),
    ),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Icon(Icons.info_outline, size: 19, color: qrosAmber),
      const SizedBox(width: 9),
      Expanded(child: Text(text, style: const TextStyle(fontSize: 12, height: 1.45, color: Color(0xFFEFE0BF)))),
    ]),
  );
}
