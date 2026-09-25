import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qros_mobile_studio/core/g5_snapshot.dart';
import 'package:qros_mobile_studio/ui/g5_snapshot_screen.dart';

class FixtureGateway implements G5SnapshotGateway {
  @override
  Future<VerifiedG5Snapshot> fetch(String origin,String token) async {
    if(origin!='https://example.invalid'||token!=List.filled(43,'A').join()) throw const G5SnapshotReject('INPUT');
    final f=jsonDecode(File('../g6/tests/fixtures/g5_signed_snapshot_fixture.json').readAsStringSync()) as Map<String,dynamic>;
    return const G5SnapshotVerifier(G6SyntheticTrust.profile).verify(f['payload'] as Map<String,dynamic>);
  }
}

void main(){
  testWidgets('G6 screen displays only cryptographically verified synthetic snapshot',(tester) async{
    await tester.pumpWidget(MaterialApp(home:G5SnapshotScreen(gateway:FixtureGateway())));
    await tester.enterText(find.byKey(const Key('g6-origin')),'https://example.invalid');
    await tester.enterText(find.byKey(const Key('g6-token')),List.filled(43,'A').join());
    await tester.tap(find.byKey(const Key('g6-fetch'))); await tester.pumpAndSettle();
    expect(find.byKey(const Key('g6-verified')),findsOneWidget);
    expect(find.textContaining('No demuestra rentabilidad'),findsOneWidget);
  });
}
