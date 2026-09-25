import 'package:flutter/foundation.dart';
import 'universe_ir.dart';

/// In-memory local draft only. No external scientific authority or persistence.
class UniverseSessionStore extends ChangeNotifier {
  UniverseSessionDraft? _latest;
  UniverseSessionDraft? get latest => _latest;

  Future<UniverseSessionDraft> save({
    required String title,
    required String thesis,
    required UniverseBlueprint blueprint,
  }) async {
    final cleanTitle = title.trim();
    final cleanThesis = thesis.trim();
    if (cleanTitle.length < 3 || cleanTitle.length > 72) {
      throw const UniverseValidationError('TITLE_LENGTH');
    }
    if (cleanThesis.length < 10 || cleanThesis.length > 500) {
      throw const UniverseValidationError('THESIS_LENGTH');
    }
    blueprint.validate();
    final draft = UniverseSessionDraft(
      title: cleanTitle,
      thesis: cleanThesis,
      blueprint: blueprint,
      searchSpaceSha256: await blueprint.canonicalSha256(),
      toyEnumerationSha256: await blueprint.toyEnumerationSha256(),
    );
    _latest = draft;
    notifyListeners();
    return draft;
  }
}
